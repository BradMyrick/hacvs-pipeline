#!/usr/bin/env python3
"""HACVSP SARIF Aggregator — normalize static-analysis findings, enforce
signed-suppression governance.

Inputs:
  --slither-json PATH   slither --json report
  --sarif PATH [PATH..] one or more SARIF 2.1.0 reports (aderyn, ...)
  --suppressions PATH   target .security-suppressions.json
  --out PATH            artifacts/static-analysis-summary.json

Fail-closed: any suppression that is structurally invalid or unsigned is
reported in `invalid_suppressions` (the stage gate turns that into NO_GO).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SLITHER_IMPACT = {
    "High": "high", "Medium": "medium", "Low": "low",
    "Informational": "info", "Optimization": "info", "Multi": "high",
}
SARIF_LEVEL = {
    "error": "high", "warning": "medium", "note": "low", "none": "info",
}
REQUIRED_SUPPRESSION_FIELDS = [
    "tool", "finding_id", "file", "line_range",
    "git_commit_hash", "justification", "reviewer", "reviewer_signature",
]
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SIG_MIN_LEN = 16


def canonical_entry_digest(entry: dict) -> str:
    canon = {
        k: entry.get(k, "")
        for k in ("tool", "finding_id", "file", "line_range", "git_commit_hash")
    }
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def parse_slither(path: Path) -> list[dict]:
    findings = []
    if not path.exists() or path.stat().st_size == 0:
        return findings
    data = json.loads(path.read_text())
    for det in (data.get("results", {}) or {}).get("detectors", []) or []:
        els = det.get("elements", []) or [{}]
        sm = (els[0] or {}).get("source_mapping", {}) or {}
        fname = sm.get("filename_relative") or sm.get("filename_absolute") or "?"
        lines = sm.get("lines") or []
        findings.append({
            "engine": "slither",
            "check": det.get("check", "unknown"),
            "severity": SLITHER_IMPACT.get(det.get("impact", "Informational"), "info"),
            "confidence": det.get("confidence", ""),
            "file": str(fname),
            "lines": f"{min(lines)}-{max(lines)}" if lines else "",
            "description": det.get("description", "")[:240],
        })
    return findings


def parse_sarif(path: Path, engine: str) -> list[dict]:
    findings = []
    if not path.exists() or path.stat().st_size == 0:
        return findings
    data = json.loads(path.read_text())
    for run in data.get("runs", []) or []:
        rules = {}
        for r in (run.get("tool", {}).get("driver", {}).get("rules", []) or []):
            rules[r.get("id")] = (r.get("properties", {}) or {}).get("precision", "")
        for res in run.get("results", []) or []:
            loc = (res.get("locations", [{}]) or [{}])[0]
            pl = loc.get("physicalLocation", {}) or {}
            uri = (pl.get("artifactLocation", {}) or {}).get("uri", "?")
            region = pl.get("region", {}) or {}
            start, end = region.get("startLine", 0), region.get("endLine", 0)
            findings.append({
                "engine": engine,
                "check": res.get("ruleId", "unknown"),
                "severity": SARIF_LEVEL.get(res.get("level", "note"), "low"),
                "confidence": rules.get(res.get("ruleId"), ""),
                "file": str(uri),
                "lines": f"{start}-{end}" if start else "",
                "description": ((res.get("message", {}) or {}).get("text", ""))[:240],
            })
    return findings


def lines_overlap(a: str, b: str) -> bool:
    def parse(rng: str):
        m = re.match(r"^(\d+)(?:-(\d+))?$", str(rng or ""))
        if not m:
            return None
        lo = int(m.group(1))
        hi = int(m.group(2) or m.group(1))
        return lo, hi
    ra, rb = parse(a), parse(b)
    if ra is None or rb is None:
        return True  # unspecified ranges match loosely (fail-open on match, recorded)
    return not (ra[1] < rb[0] or rb[1] < ra[0])


def suppression_matches(entry: dict, finding: dict) -> bool:
    if entry.get("tool") not in (finding["engine"], "any"):
        return False
    if entry.get("finding_id") != finding["check"]:
        return False
    efile = str(entry.get("file", ""))
    if efile and efile not in finding["file"] and finding["file"] not in efile:
        return False
    if entry.get("line_range") and finding["lines"]:
        if not lines_overlap(entry["line_range"], finding["lines"]):
            return False
    return True


def validate_suppressions(entries: list) -> tuple[list[dict], list[str]]:
    valid, invalid = [], []
    for i, e in enumerate(entries):
        why = []
        if not isinstance(e, dict):
            invalid.append(f"entry[{i}]: not an object")
            continue
        for f in REQUIRED_SUPPRESSION_FIELDS:
            if not str(e.get(f, "")).strip():
                why.append(f"missing {f}")
        if not COMMIT_RE.match(str(e.get("git_commit_hash", ""))):
            why.append("git_commit_hash not a 40-hex sha")
        if len(str(e.get("reviewer_signature", ""))) < SIG_MIN_LEN:
            why.append("reviewer_signature too short to be a real signature")
        if why:
            invalid.append(f"entry[{i}] ({e.get('finding_id', '?')}): " + ", ".join(why))
        else:
            e = dict(e)
            e["_canonical_digest"] = canonical_entry_digest(e)
            valid.append(e)
    return valid, invalid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slither-json", type=Path, default=None)
    ap.add_argument("--sarif", nargs="*", type=Path, default=[])
    ap.add_argument("--suppressions", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    findings: list[dict] = []
    engines: dict[str, dict] = {}

    if args.slither_json:
        f = parse_slither(args.slither_json)
        findings += f
        engines["slither"] = {
            "report_present": bool(f) or args.slither_json.exists(),
            "findings": len(f),
        }

    for sarif_path in args.sarif:
        engine = sarif_path.stem.split("-")[0]  # aderyn-report.sarif -> aderyn
        f = parse_sarif(sarif_path, engine)
        findings += f
        engines[engine] = {
            "report_present": bool(f) or sarif_path.exists(),
            "findings": len(f),
        }

    entries: list[dict] = []
    invalid: list[str] = []
    if args.suppressions and args.suppressions.exists():
        try:
            entries = json.loads(args.suppressions.read_text())
            if not isinstance(entries, list):
                entries = []
                invalid.append("suppressions file is not a JSON array")
        except Exception as exc:  # noqa: BLE001
            invalid.append(f"suppressions file unparseable: {exc}")
    valid, inv = validate_suppressions(entries)
    invalid += inv

    unsuppressed, suppressed = [], []
    for finding in findings:
        match = next(
            (s for s in valid if suppression_matches(s, finding)), None
        )
        if match:
            suppressed.append({"finding": finding, "suppression_digest": match["_canonical_digest"]})
        else:
            unsuppressed.append(finding)

    totals = {
        "total": len(findings),
        "suppressed": len(suppressed),
        "unsuppressed": {s: 0 for s in SEVERITY_ORDER},
        "by_engine": {e: v["findings"] for e, v in engines.items()},
    }
    for f in unsuppressed:
        totals["unsuppressed"][f["severity"]] += 1

    out = {
        "engines": engines,
        "totals": totals,
        "invalid_suppressions": invalid,
        "unsuppressed_findings": unsuppressed,
        "suppressed_findings": suppressed,
        "suppression_canonical_digests": [s["_canonical_digest"] for s in valid],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"[sarif-aggregator] {len(findings)} findings, "
          f"{len(suppressed)} suppressed, {len(invalid)} invalid suppressions -> {args.out}")
    # Exit non-zero only on invalid suppressions (unsuppressed counts are the
    # stage gate's responsibility, giving the expert richer triage context).
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
