"""Create a public, machine-readable release manifest from the source commit.

Run before testing and deployment. No AWS access is required.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"


def get_revision() -> str:
    for key in ("CODEBUILD_RESOLVED_SOURCE_VERSION", "RELEASE_SHA", "GITHUB_SHA"):
        raw = os.environ.get(key, "").strip()
        if re.fullmatch(r"[a-fA-F0-9]{40}", raw):
            return raw.lower()
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.PIPE
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            "Could not identify the commit. Run inside a Git checkout or set RELEASE_SHA "
            "to the full 40-character source commit SHA."
        ) from exc
    if not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
        raise SystemExit("Source revision is not a 40-character Git SHA.")
    return sha.lower()


def main() -> None:
    if not WEBSITE.is_dir():
        raise SystemExit(f"Missing website directory: {WEBSITE}")
    revision = get_revision()
    manifest = {
        "release_id": revision,
        "source_commit": revision,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    dest = WEBSITE / "release.json"
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Created {dest.relative_to(ROOT)} for commit {revision}")


if __name__ == "__main__":
    main()
