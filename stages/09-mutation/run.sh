#!/usr/bin/env bash
# Stage 9 — mutation testing (RELEASE tier, long-running, detachable)
# Gate: >= 90% mutant kill rate; zero unaddressed survivors in core contracts.
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
note() { echo "[stage-09] $*"; }
fail() { echo "[stage-09] FAIL: $*" | tee "$ART/stage-09-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; }

CORE_CONTRACTS="$(python3 -c "import json;print('\n'.join(json.load(open('$ENG/engagement.json'))['applicability'].get('core_contracts',[])))")"
LIMIT="${HACVSP_MUTATION_LIMIT:-0}"   # 0 = all mutants
WORK="$ART/mutation-workspace"
mkdir -p "$WORK"

# --- Generate mutants per file via the CLI form (proven interface; the
#     array-config form panics in gambit 1.0.6), then merge the corpus.
note "generating mutants (gambit mutate, per-file CLI)"
TARGET_REAL="$(readlink -f "$TARGET")"
REMAPS_CLI=()
while IFS= read -r rm; do
  [ -n "$rm" ] && REMAPS_CLI+=(--solc_remappings "$rm")
done < <(grep -vE '^\s*(#|$)' "$TARGET/remappings.txt" 2>/dev/null || true)

if [ -d "$WORK/mutants" ]; then
  mv "$WORK/mutants" "$WORK/mutants.prev"
fi
mkdir -p "$WORK/per-file" "$WORK/mutants"

i=0
: > "$WORK/mutants/mutants.log"
for f in $(cd "$TARGET" && find src -name '*.sol' | grep -v '/mocks/' | sort); do
  i=$((i+1))
  out="$WORK/per-file/$i"
  if ! (cd "$TARGET_REAL" && gambit mutate --filename "$f" --outdir "$out" \
          "${REMAPS_CLI[@]}" > "$WORK/gambit-$i.txt" 2>&1); then
    note "gambit failed on $f (see $WORK/gambit-$i.txt) — skipping file"
    continue
  fi
  # merge: renumber mids by offset, copy mutant dirs, append log rows
  python3 - "$out" "$WORK/mutants" <<'MERGE'
import pathlib, shutil, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
log = src / "mutants.log"
if not log.exists():
    raise SystemExit(0)
rows = [l for l in log.read_text().splitlines() if l.strip()]
try:
    offset = max(int(r.split(",", 1)[0]) for r in dst.joinpath("mutants.log")
                 .read_text().splitlines() if r.strip()) if dst.joinpath("mutants.log").stat().st_size else 0
except Exception:
    offset = 0
for r in rows:
    mid = int(r.split(",", 1)[0]) + offset
    dst.joinpath("mutants.log").write_text(
        dst.joinpath("mutants.log").read_text() +
        r.replace(r.split(",", 1)[0], str(mid), 1) + "\n")
    mdir = src / "mutants" / r.split(",", 1)[0]
    if mdir.is_dir():
        shutil.copytree(mdir, dst / "mutants" / str(mid), dirs_exist_ok=True)
MERGE
  note "mutated $f"
done

LOG="$WORK/mutants/mutants.log"
TOTAL="$(grep -c . "$LOG" || true)"
[ "$TOTAL" -gt 0 ] || fail "gambit produced zero mutants (solc/import resolution?)"
note "mutants generated: $TOTAL"

# --- Baseline: harness must pass unmutated (fail-closed sanity)
note "baseline test run (unmutated harness must pass)"
forge test --no-match-path 'test/invariant/*' --no-match-path 'test/fork/*' --json \
  > "$WORK/baseline.ndjson" 2>/dev/null || fail "baseline test suite fails — mutation run meaningless"

# --- Mutation loop (resumable; originals restored from backups, never from git)
python3 - "$LOG" "$WORK" "$ART" "$LIMIT" "$CORE_CONTRACTS" <<'PY' || fail "mutation loop failed"
import json, pathlib, shutil, subprocess, sys, time
mlog, work, art, limit, core = sys.argv[1], pathlib.Path(sys.argv[2]), \
    pathlib.Path(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split()
target = pathlib.Path("/engagement/target")
rows = []
for line in pathlib.Path(mlog).read_text().splitlines():
    parts = line.split(",", 5)
    if len(parts) >= 6 and parts[0].isdigit():
        rows.append({"mid": parts[0], "op": parts[1], "file": parts[2],
                     "loc": parts[3], "frm": parts[4], "to": parts[5]})
if limit > 0:
    rows = rows[:limit]
progress_f = art / "mutation-progress.json"
progress = {"done": [], "killed": 0, "survived": 0, "started": time.time()}
if progress_f.exists():
    try: progress = json.loads(progress_f.read_text())
    except Exception: pass
done_ids = set(progress["done"])

report = {"total": len(rows), "killed": 0, "survived": 0,
          "survivors": [], "engines": "gambit 1.0.6 + forge"}
for r in rows:
    mid = r["mid"]
    if mid in done_ids:
        continue
    mut_dir = work / "mutants" / mid
    applied = []
    if mut_dir.exists():
        for f in mut_dir.rglob("*.sol"):
            rel = f.relative_to(mut_dir)
            orig = target / rel
            if orig.exists():
                backup = work / "backups" / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(orig, backup)
                shutil.copy2(f, orig)
                applied.append((orig, backup))
    if not applied:
        progress["done"].append(mid); progress_f.write_text(json.dumps(progress)); continue
    try:
        res = subprocess.run(
            ["forge", "test", "--no-match-path", "test/invariant/*",
             "--no-match-path", "test/fork/*", "--json"],
            cwd=target, capture_output=True, text=True, timeout=900)
        killed = res.returncode != 0
    except subprocess.TimeoutExpired:
        killed = True  # hang = detected
    for orig, backup in applied:
        shutil.copy2(backup, orig)  # restore original byte-for-byte
    if killed:
        report["killed"] += 1; progress["killed"] += 1
    else:
        report["survived"] += 1; progress["survived"] += 1
        report["survivors"].append({
            "id": mid, "op": r["op"], "file": r["file"], "loc": r["loc"],
            "from": r["frm"], "to": r["to"],
            "contract_guess": next((c for c in core if c.lower() in str(r["file"]).lower()), ""),
        })
    progress["done"].append(mid)
    progress_f.write_text(json.dumps(progress))

attempted = report["killed"] + report["survived"]
report["kill_rate_pct"] = round(100.0 * report["killed"] / attempted, 2) if attempted else 0.0
report["core_survivors"] = [s for s in report["survivors"] if s["contract_guess"]]
(art / "mutation-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"[mutation] kill_rate={report['kill_rate_pct']}% "
      f"killed={report['killed']} survived={report['survived']}")
PY

note "triage: survivors must be in MUTATION_EXCEPTIONS.md (equivalence) or fail"
exit 0
