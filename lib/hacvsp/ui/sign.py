"""Host-side signing for UI actions — key material never leaves the process."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

NAMESPACE = "hacvsp"


def signing_key() -> Path:
    env = os.environ.get("HACVSP_SIGN_KEY")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    default = Path.home() / ".ssh" / "id_ed25519"
    if default.exists():
        return default
    raise FileNotFoundError(
        "no signing key: set HACVSP_SIGN_KEY or create ~/.ssh/id_ed25519")


def sign_digest(digest: str) -> str:
    """Detached ssh-ed25519 signature over a canonical digest (namespace hacvsp)."""
    key = signing_key()
    res = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE],
        input=digest.encode(), capture_output=True, check=True, timeout=30)
    return res.stdout.decode().strip()


def canonical_entry_digest(entry: dict) -> str:
    """MUST match tools/sarif-aggregator canonicalization — imported from it."""
    import importlib.util
    agg_path = Path(__file__).resolve().parents[3] / "tools" / "sarif-aggregator" / "sarif_aggregator.py"
    spec = importlib.util.spec_from_file_location("sarif_aggregator", agg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical_entry_digest(entry)
