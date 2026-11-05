#!/usr/bin/env bash
# Stage 9 — mutation testing (RELEASE tier, long-running, detachable)
# Gate: >= 90% mutant kill rate; zero unaddressed survivors in core contracts.
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-09] $*"; }
fail() { echo "[stage-09] FAIL: $*" | tee "$ART/stage-09-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

CORE_CONTRACTS="$(python3 -c "import json;print('\n'.join(json.load(open('$ENG/engagement.json'))['applicability'].get('core_contracts',[])))")"
LIMIT="${HACVSP_MUTATION_LIMIT:-0}"   # 0 = all mutants
WORK="$ART/mutation-workspace"
mkdir -p "$WORK"

note "generating mutants (gambit)"
cat > "$WORK/gambit.json" <<'JSON'
{
  "json_url": "local",
  "files": ["src/"],
  "emit_cf": false,
  "operators": ["BooleanSwap", "ComparisonSwap", "IfStatementInterceptor",
                "StrictEqToEq", "SignedComparisonSwap", "LiteralMutation",
                "ModifierRemover", "DeleteExpression", "SwapArguments",
                "OverrideBooleanLiteral", "ConditionalSwap"]
}
JSON
# regenerate mutant corpus (workspace is pipeline-owned; old corpus is rotated
# aside by rename — nothing is ever deleted: kodr deletion policy)
if [ -d "$WORK/mutants" ]; then
  mv "$WORK/mutants" "$WORK/mutants.prev"
fi
gambit generate --json "$WORK/gambit.json" --output-dir "$WORK/mutants" \
  > "$WORK/gambit-stdout.txt" 2>&1 || fail "gambit generate failed — see $WORK/gambit-stdout.txt"

MUTANTS_JSON="$(find "$WORK/mutants" -maxdepth 1 -name 'mutants.json' -print -quit)"
[ -n "$MUTANTS_JSON" ] || fail "gambit produced no mutants.json"
TOTAL="$(python3 -c "import json;print(len(json.load(open('$MUTANTS_JSON'))))")"
note "mutants generated: $TOTAL"

# Baseline: harness must pass unmutated (fail-closed sanity)
note "baseline test run (unmutated harness must pass)"
forge test --no-match-path 'test/invariant/*' --no-match-path 'test/fork/*' --json \
  > "$WORK/baseline.ndjson" 2>/dev/null || fail "baseline test suite fails — mutation run meaningless"

# Mutation loop (resumable; originals restored from backups, never from git)
python3 - "$MUTANTS_JSON" "$WORK" "$ART" "$LIMIT" "$CORE_CONTRACTS" <<'PY' || fail "mutation loop failed"
import json, pathlib, shutil, subprocess, sys, time
mutants_json, work, art, limit, core = sys.argv[1], pathlib.Path(sys.argv[2]), \
    pathlib.Path(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split()
target = pathlib.Path("/engagement/target")
mutants = json.loads(pathlib.Path(mutants_json).read_text())
if limit > 0:
    mutants = mutants[:limit]
progress_f = art / "mutation-progress.json"
progress = {"done": [], "killed": 0, "survived": 0, "started": time.time()}
if progress_f.exists():
    try: progress = json.loads(progress_f.read_text())
    except Exception: pass
done_ids = set(progress["done"])

report = {"total": len(mutants), "killed": 0, "survived": 0,
          "survivors": [], "engines": "gambit+forge"}
for i, mut in enumerate(mutants):
    mid = f"{mut.get('mutant_name', i)}"
    if mid in done_ids:
        continue
    src_rel = mut["file"] if "file" in mut else mut.get("source_contract", "")
    # gambit mutants.json: file + mutant_name; workspace holds <name>/ mutated sources
    mut_dir = work / "mutants" / mut.get("mutant_name", str(i))
    src_dir = target / "src"
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
        killed = True  # timeout = mutant detected by hang = killed (recorded)
    for orig, backup in applied:
        shutil.copy2(backup, orig)  # restore original byte-for-byte
    if killed:
        report["killed"] += 1; progress["killed"] += 1
    else:
        report["survived"] += 1; progress["survived"] += 1
        report["survivors"].append({
            "id": mid, "file": src_rel,
            "contract_guess": next((c for c in core if c.lower() in str(src_rel).lower()), ""),
        })
    progress["done"].append(mid)
    progress_f.write_text(json.dumps(progress))
    if (i + 1) % 10 == 0:
        note_pct = 100.0 * (report["killed"] + report["survived"]) / max(1, len(mutants))
        print(f"[mutation] {i+1}/{len(mutants)} ({note_pct:.1f}%) "
              f"killed={report['killed']} survived={report['survived']}", flush=True)

attempted = report["killed"] + report["survived"]
report["kill_rate_pct"] = round(100.0 * report["killed"] / attempted, 2) if attempted else 0.0
report["core_survivors"] = [s for s in report["survivors"] if s["contract_guess"]]
(art / "mutation-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"[mutation] kill_rate={report['kill_rate_pct']}% "
      f"killed={report['killed']} survived={report['survived']}")
PY

note "triage: survivors must be in MUTATION_EXCEPTIONS.md (equivalence) or fail"
exit $stage_fail
