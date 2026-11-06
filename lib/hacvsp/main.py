"""hacvsp — the pipeline CLI.

Commands:
  init NAME [--dir DIR]            scaffold a pipeline-compliant Foundry project
  audit REPO [--commit SHA] [--name SLUG]
                                   bootstrap an engagement (clone + intake)
  stage N --engagement SLUG [--detach] [--force]
                                   run stage N runner in its pinned container,
                                   then evaluate its gate -> binary verdict
  gate N --engagement SLUG         re-evaluate a stage gate (e.g. after fixes)
  status [--engagement SLUG]       gate ledger table + cadence rollup
  logs N --engagement SLUG         follow a (detached) stage log
  doctor [--allow-unpinned] [--allow-missing-images]
                                   fail-closed hermetic-environment check
  verify                           the spec audits the pipeline (SPEC.json concordance)
  gates                            emit derived gates.json
  report --engagement SLUG         render SECURITY_ASSURANCE.md draft from ledger
  list                             list engagements
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__, docker, engagement as eng_mod, ledger, spec


def die(msg: str, code: int = 1) -> None:
    print(f"!! {msg}", file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------- commands --

def cmd_init(args) -> None:
    tpl = spec.REPO_ROOT / "templates" / "workstation"
    if not tpl.is_dir():
        die("templates/workstation missing")
    dest = Path(args.dir or args.name).resolve()
    if dest.exists():
        die(f"destination already exists: {dest}")
    subprocess.run(["cp", "-r", str(tpl), str(dest)], check=True)
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    print(f"==> pipeline-compliant Foundry scaffold created at {dest}")
    print("    next: add contracts under src/, wire test/* suites, commit,")
    print("    then audit via: hacvsp audit <repo> (or the /audit command)")


def cmd_audit(args) -> None:
    name = args.name or Path(args.repo.rstrip("/")).name
    eng_mod.create(name, args.repo, args.commit, subdir=args.subdir)


def _gate_eval(eng_dir: Path, n: int) -> dict:
    """Execute stages/NN-*/gate.py on the host. Fail-closed on any error."""
    s = spec.stage_by_order(n)
    gate_py = spec.stage_dir(n) / "gate.py"
    try:
        res = subprocess.run(
            [sys.executable, str(gate_py), "--engagement-dir", str(eng_dir)],
            capture_output=True, text=True, timeout=600,
        )
        if res.returncode != 0:
            return {
                "decision": "NO_GO",
                "failures": [f"gate evaluator exited {res.returncode}: {res.stderr.strip()[:400]}"],
            }
        return json.loads(res.stdout)
    except Exception as exc:  # noqa: BLE001 — fail-closed by design
        return {"decision": "NO_GO", "failures": [f"gate evaluator error: {exc}"]}


def _check_ordering(eng_dir: Path, n: int, force: bool) -> None:
    cadence = spec.stage_by_order(n)["cadence"]
    led = ledger.load(eng_dir)
    for prior in spec.cadence_stages(cadence):
        if prior >= n:
            break
        v = ledger.latest(led, prior)
        if v is None or v["decision"] != "GO":
            if force:
                print(f"!! --force: running stage {n} despite stage {prior} "
                      f"{'missing' if v is None else 'NO_GO'} (recorded in verdict)")
                return
            die(f"stage {prior} is {'not yet run' if v is None else 'NO_GO'} — "
                f"fix that first or use --force (fail-closed ordering)")


def cmd_stage(args) -> None:
    n = args.stage
    eng_dir = eng_mod.path(args.engagement)
    _check_ordering(eng_dir, n, args.force)

    if not args.no_doctor:
        failures = docker.doctor(
            allow_unpinned=args.allow_unpinned, allow_missing_images=False
        )
        if failures:
            die("doctor failed (fail-closed): " + "; ".join(failures))

    rc = docker.run_stage(eng_dir, n, detach=args.detach)
    if args.detach:
        print("==> detached; when the run completes, evaluate with:")
        print(f"    hacvsp gate {n} --engagement {args.engagement}")
        return

    verdict = _gate_eval(eng_dir, n)
    s = spec.stage_by_order(n)
    record = {
        "stage": n,
        "stage_name": s["stage"],
        "cadence": s["cadence"],
        "decision": verdict["decision"],
        "criteria": s.get("gate", {}).get("criteria"),
        "failures": verdict.get("failures", []),
        "evidence": verdict.get("evidence", []),
        "details": verdict.get("details", {}),
        "runner_exit": rc,
        "forced": args.force,
        "commit": ledger.target_commit(eng_dir),
    }
    if rc != 0:
        record["failures"] = record["failures"] + [f"runner exit code {rc}"]
        record["decision"] = "NO_GO"
    led = ledger.append(eng_dir, record)
    print(ledger.render_table(led))
    if record["decision"] != "GO":
        raise SystemExit(1)


def cmd_gate(args) -> None:
    eng_dir = eng_mod.path(args.engagement)
    n = args.stage
    s = spec.stage_by_order(n)
    verdict = _gate_eval(eng_dir, n)
    record = {
        "stage": n,
        "stage_name": s["stage"],
        "cadence": s["cadence"],
        "decision": verdict["decision"],
        "criteria": s.get("gate", {}).get("criteria"),
        "failures": verdict.get("failures", []),
        "evidence": verdict.get("evidence", []),
        "details": verdict.get("details", {}),
        "runner_exit": None,
        "commit": ledger.target_commit(eng_dir),
    }
    led = ledger.append(eng_dir, record)
    print(ledger.render_table(led))
    if record["decision"] != "GO":
        raise SystemExit(1)


def cmd_status(args) -> None:
    if args.engagement:
        dirs = [eng_mod.path(args.engagement)]
    else:
        slugs = eng_mod.list_engagements()
        if not slugs:
            print("no engagements (create one: hacvsp audit <repo>)")
            return
        dirs = [eng_mod.path(s) for s in slugs]
    for d in dirs:
        led = ledger.load(d)
        print(f"\n== engagement: {d.name} (target @ {ledger.target_commit(d)})")
        print(ledger.render_table(led))


def cmd_doctor(args) -> None:
    failures = docker.doctor(
        allow_unpinned=args.allow_unpinned,
        allow_missing_images=args.allow_missing_images,
    )
    if failures:
        print("DOCTOR: NO_GO")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print("DOCTOR: GO — hermetic toolchain verified (digest-pinned, images match)")


def cmd_verify(args) -> None:
    failures = spec.verify_concordance()
    if failures:
        print("VERIFY: NO_GO — pipeline drifted from SPEC.json")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"VERIFY: GO — implementation matches SPEC.json "
          f"({len(spec.stages())} stages, all gates/artifacts/pins concordant)")


def cmd_gates(args) -> None:
    print(json.dumps({"version": spec.load_spec()["version"],
                      "gates": spec.derive_gates()}, indent=2))


def cmd_logs(args) -> None:
    eng_dir = eng_mod.path(args.engagement)
    raise SystemExit(docker.follow_logs(eng_dir, args.stage))


def cmd_report(args) -> None:
    from .report import render_draft
    eng_dir = eng_mod.path(args.engagement)
    out = render_draft(eng_dir)
    print(f"==> draft rendered: {out}")


def cmd_repin(args) -> None:
    eng_mod.repin(args.engagement, args.commit)


def cmd_fleet(args) -> None:
    from . import insights
    data = insights.fleet_data()
    if args.json:
        print(json.dumps(data, indent=2)); return
    for e in data:
        print(f"{e['slug']:<20} PR:{e['pr_tier']:<6} REL:{e['release_tier']:<6} "
              f"{e['stages_go']}G/{e['stages_nogo']}N/{e['stages_pending']}P  {e['last_activity']}")


def cmd_findings(args) -> None:
    from . import insights
    items = insights.findings_data(args.engagement)
    if args.json:
        print(json.dumps(items, indent=2)); return
    for f in items:
        print(f"[{f['severity']:<8}] {f['id']:<12} {f['title']}  {f['where']}")
    if not items:
        print("(inbox empty)")


def cmd_pending(args) -> None:
    from . import insights
    p = insights.pending_data(args.engagement)
    if args.json:
        print(json.dumps(p, indent=2)); return
    print(json.dumps(p, indent=2))


def cmd_ui(args) -> None:
    from .ui.server import serve
    if args.bind not in ("127.0.0.1", "localhost", "::1"):
        print("!! WARNING: binding off-localhost exposes audit evidence and sign actions")
    serve(port=args.port, bind=args.bind)


def cmd_list(args) -> None:
    for s in eng_mod.list_engagements():
        print(s)


# -------------------------------------------------------------------- main --

def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="hacvsp", description=__doc__)
    p.add_argument("--version", action="version", version=f"hacvsp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="scaffold a pipeline-compliant Foundry project")
    sp.add_argument("name")
    sp.add_argument("--dir")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("audit", help="bootstrap an engagement for a repo")
    sp.add_argument("repo")
    sp.add_argument("--commit")
    sp.add_argument("--name")
    sp.add_argument("--subdir", default=None,
                    help="monorepo path to the Foundry root, e.g. contracts/")
    sp.set_defaults(fn=cmd_audit)

    sp = sub.add_parser("stage", help="run stage N + gate")
    sp.add_argument("stage", type=int)
    sp.add_argument("--engagement", required=True)
    sp.add_argument("--detach", action="store_true")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--no-doctor", action="store_true")
    sp.add_argument("--allow-unpinned", action="store_true")
    sp.set_defaults(fn=cmd_stage)

    sp = sub.add_parser("gate", help="re-evaluate stage N gate")
    sp.add_argument("stage", type=int)
    sp.add_argument("--engagement", required=True)
    sp.set_defaults(fn=cmd_gate)

    sp = sub.add_parser("status", help="gate ledger status")
    sp.add_argument("--engagement")
    sp.set_defaults(fn=cmd_status)

    sp = sub.add_parser("doctor", help="fail-closed environment check")
    sp.add_argument("--allow-unpinned", action="store_true")
    sp.add_argument("--allow-missing-images", action="store_true")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("verify", help="pipeline <-> SPEC.json concordance")
    sp.set_defaults(fn=cmd_verify)

    sp = sub.add_parser("gates", help="emit derived gates.json")
    sp.set_defaults(fn=cmd_gates)

    sp = sub.add_parser("logs", help="follow stage log")
    sp.add_argument("stage", type=int)
    sp.add_argument("--engagement", required=True)
    sp.set_defaults(fn=cmd_logs)

    sp = sub.add_parser("report", help="render SECURITY_ASSURANCE.md draft")
    sp.add_argument("--engagement", required=True)
    sp.set_defaults(fn=cmd_report)

    sp = sub.add_parser("repin", help="move engagement to a new target commit")
    sp.add_argument("--engagement", required=True)
    sp.add_argument("--commit", default=None)
    sp.set_defaults(fn=cmd_repin)

    sp = sub.add_parser("fleet", help="all engagements + rollups (--json)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_fleet)

    sp = sub.add_parser("findings", help="triage inbox for an engagement")
    sp.add_argument("--engagement", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_findings)

    sp = sub.add_parser("pending", help="stage-13 ratification queue")
    sp.add_argument("--engagement", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_pending)

    sp = sub.add_parser("ui", help="operator dashboard (localhost web app)")
    sp.add_argument("--port", type=int, default=8787)
    sp.add_argument("--bind", default="127.0.0.1")
    sp.set_defaults(fn=cmd_ui)

    sp = sub.add_parser("list", help="list engagements")
    sp.set_defaults(fn=cmd_list)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
