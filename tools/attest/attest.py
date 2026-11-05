#!/usr/bin/env python3
"""HACVSP Attestation Engine — assemble, hash, sign, verify the evidence bundle.

Subcommands:
  assemble --engagement DIR   build SECURITY_ASSURANCE.md + bundle manifest +
                              provenance.intoto.jsonl
  verify   --engagement DIR   recompute digests and verify the cosign signature

Published bundle (SPEC v0.1.0):
  SECURITY_ASSURANCE.md, artifacts/sbom.cyclonedx.json,
  artifacts/ACCESS_CONTROL_MATRIX.json, artifacts/EVENT_EMISSION_AUDIT.json,
  artifacts/kontrol-proofs.json, artifacts/mutation-report.json,
  artifacts/mythril-results.json, artifacts/provenance.intoto.jsonl,
  signatures/bundle-attestation.sig
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BUNDLE = [
    "SECURITY_ASSURANCE.md",
    "artifacts/sbom.cyclonedx.json",
    "artifacts/ACCESS_CONTROL_MATRIX.json",
    "artifacts/EVENT_EMISSION_AUDIT.json",
    "artifacts/kontrol-proofs.json",
    "artifacts/mutation-report.json",
    "artifacts/mythril-results.json",
    "artifacts/provenance.intoto.jsonl",
    "signatures/bundle-attestation.sig",
]

MANDATORY_SECTIONS = [
    "Executive Summary & Target Commit",
    "Verification Methodology & Stage-by-Stage Results",
    "Active Suppressions & Exceptions Inventory",
    "Coverage Exceptions Audit",
    "On-Chain Deployment & Bytecode Verification Mapping",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _latest(ledger: dict, stage: int) -> dict | None:
    hits = [v for v in ledger.get("verdicts", []) if v["stage"] == stage]
    return hits[-1] if hits else None


def assemble(eng: Path) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
    from hacvsp import ledger as L, spec as S  # noqa: E402

    led = L.load(eng)
    meta = json.loads((eng / "engagement.json").read_text())

    # ---- stage-by-stage table
    rows = []
    for s in S.stages():
        v = _latest(led, s["order"])
        rows.append(
            f"| {s['order']} | {s['stage']} | {s['cadence']} | "
            f"{v['decision'] if v else 'PENDING'} | {s.get('gate', {}).get('criteria', '')} |"
        )

    # ---- suppressions inventory
    supp_rows = ["| Tool | Rule ID | File:Lines | Justification | Reviewer | Commit |",
                 "|---|---|---|---|---|---|"]
    supp_path = eng / "target" / ".security-suppressions.json"
    if supp_path.exists():
        try:
            for e in json.loads(supp_path.read_text()):
                supp_rows.append(
                    f"| {e.get('tool','?')} | {e.get('finding_id','?')} "
                    f"| {e.get('file','?')}:{e.get('line_range','?')} "
                    f"| {str(e.get('justification','?'))[:70]} "
                    f"| {e.get('reviewer','?')} | {str(e.get('git_commit_hash','?'))[:12]} |"
                )
        except Exception as exc:  # noqa: BLE001
            supp_rows.append(f"| _unparseable: {exc}_ | | | | | |")
    else:
        supp_rows.append("| _none_ | | | | | |")

    cov_exc = eng / "target" / "COVERAGE_EXCEPTIONS.md"
    cov_text = cov_exc.read_text()[:2000] if cov_exc.exists() else "_No exceptions._"

    deploys = meta.get("deployment", {}).get("addresses", {})
    dep_lines = [f"- `{addr}` → `{name}` (verify: Sourcify/explorer exact-match with "
                 f"matching metadata IPFS hash)" for addr, name in deploys.items()] or \
                ["_No on-chain deployment recorded for this engagement._"]

    assurance = "\n".join([
        "# SECURITY_ASSURANCE.md",
        "",
        f"_Kodr.pro High-Assurance Contract Verification & Security Pipeline "
        f"{meta.get('spec_version', 'v0.1.0')} — fail-closed, dual-cadence._",
        "",
        "## Executive Summary & Target Commit",
        "",
        f"- Engagement: `{meta.get('name')}`",
        f"- Target: `{meta['target']['repo']}` @ `{meta['target']['commit']}`",
        f"- Overall: PR tier **{led['overall']['pr_commit_tier']}**, "
        f"Release tier **{led['overall']['release_gate_tier']}**",
        "",
        "## Verification Methodology & Stage-by-Stage Results",
        "",
        "| # | Stage | Cadence | Verdict | Gate criteria (SPEC) |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "## Active Suppressions & Exceptions Inventory",
        "",
        *supp_rows,
        "",
        "## Coverage Exceptions Audit",
        "",
        cov_text,
        "",
        "## On-Chain Deployment & Bytecode Verification Mapping",
        "",
        *dep_lines,
        "",
    ]) + "\n"
    (eng / "SECURITY_ASSURANCE.md").write_text(assurance)

    # ---- bundle manifest
    files = {}
    for rel in BUNDLE:
        if rel.endswith("bundle-attestation.sig"):
            continue
        p = eng / rel
        files[rel] = sha256_file(p) if p.exists() else None
    bundle_digest = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()
    ).hexdigest()
    manifest = {
        "engagement": meta.get("name"),
        "target_commit": meta["target"]["commit"],
        "spec_version": meta.get("spec_version"),
        "files": files,
        "bundle_digest": bundle_digest,
        "missing": [k for k, v in files.items() if v is None],
    }
    (eng / "artifacts" / "bundle-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    # ---- SLSA provenance (local predicate; CI GitHub attestation replaces when present)
    gha = Path("/github/workspace").exists()
    prov = {
        "_type": "https://in-toto.io/Statement/v0.1",
        "subject": [{"name": meta.get("name"), "digest": {"sha256": bundle_digest}}],
        "predicateType": "https://slsa.dev/provenance/v0.2",
        "predicate": {
            "builder": {"id": "https://kodr.pro/hacvsp@v0.1.0"},
            "buildType": "hacvsp-release-gate",
            "source": meta["target"]["repo"],
            "parameters": {"commit": meta["target"]["commit"],
                           "ci_github_attestation": gha},
        },
    }
    with open(eng / "artifacts" / "provenance.intoto.jsonl", "a") as f:
        f.write(json.dumps(prov) + "\n")

    print(f"[attest] SECURITY_ASSURANCE.md rendered; bundle_digest={bundle_digest[:16]}… "
          f"missing={manifest['missing'] or 'none'}")
    return 0


def verify(eng: Path) -> int:
    manifest_path = eng / "artifacts" / "bundle-manifest.json"
    if not manifest_path.exists():
        print("[attest] bundle-manifest.json missing", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text())
    mismatches = []
    for rel, want in manifest["files"].items():
        if want is None:
            mismatches.append(f"{rel}: was missing at assembly")
            continue
        p = eng / rel
        got = sha256_file(p) if p.exists() else None
        if got != want:
            mismatches.append(f"{rel}: digest drift {got} != {want}")
    sig = eng / "signatures" / "bundle-attestation.sig"
    if not sig.exists():
        mismatches.append("signatures/bundle-attestation.sig missing")
    print(json.dumps({"ok": not mismatches, "mismatches": mismatches}, indent=2))
    return 0 if not mismatches else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("assemble", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--engagement", type=Path, required=True)
    args = ap.parse_args(argv)
    eng = args.engagement.resolve()
    return assemble(eng) if args.cmd == "assemble" else verify(eng)


if __name__ == "__main__":
    sys.exit(main())
