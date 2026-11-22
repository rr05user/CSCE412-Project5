"""Human-approved rollback of the static website from a verified local snapshot.

Dry run (default): python scripts/rollback_website.py --release-id <40-char-sha>
Apply: CONFIRM_ROLLBACK=yes python scripts/rollback_website.py --release-id <sha> --execute

This script never chooses an unverified legacy backup automatically.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUCKET = "csce412-project5-027677879294"
DISTRIBUTION = "EC3GYYDBXOHBS"
REGION = "us-east-1"
BACKUPS = ROOT / "project6-backups"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def validate_snapshot(release_id):
    if not SHA_PATTERN.fullmatch(release_id):
        raise ValueError("Release ID must be exactly 40 lowercase hex characters")
    snapshot = BACKUPS / f"verified-release-{release_id}"
    if not snapshot.is_dir():
        raise ValueError(f"Verified release snapshot not found: {snapshot}")
    manifest_file = snapshot / "release.json"
    if not manifest_file.is_file():
        raise ValueError("Snapshot has no release.json")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("release_id") != release_id or manifest.get("source_commit") != release_id:
        raise ValueError("Snapshot release manifest does not match requested release")
    if not (snapshot / "index.html").is_file():
        raise ValueError("Snapshot has no index.html")
    if not list(snapshot.glob("*.html")):
        raise ValueError("Snapshot contains no HTML pages")
    return snapshot


def aws(*args):
    cmd = ["aws", *args, "--region", REGION, "--profile", os.environ.get("AWS_PROFILE", "csce412")]
    print("Running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Dry-run or execute human-approved release rollback")
    parser.add_argument("--release-id", required=True, help="40-character SHA of a locally verified release")
    parser.add_argument("--execute", action="store_true", help="Actually restore production (requires CONFIRM_ROLLBACK=yes)")
    args = parser.parse_args()

    try:
        snapshot = validate_snapshot(args.release_id)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    print(f"Validated rollback snapshot: {snapshot}")
    print(f"Target bucket: {BUCKET}; CloudFront distribution: {DISTRIBUTION}")
    if not args.execute:
        print("DRY RUN ONLY: No AWS changes made. Add --execute and CONFIRM_ROLLBACK=yes for a real rollback.")
        return
    if os.environ.get("CONFIRM_ROLLBACK") != "yes":
        parser.error("Rollback blocked: set CONFIRM_ROLLBACK=yes to approve production changes")

    # Recheck snapshot immediately before use. No deletion of unrelated bucket objects.
    validate_snapshot(args.release_id)
    aws("s3", "sync", str(snapshot), f"s3://{BUCKET}/")
    aws("cloudfront", "create-invalidation", "--distribution-id", DISTRIBUTION, "--paths", "/*")
    print("Rollback upload and invalidation requested; verify production after propagation.")


if __name__ == "__main__":
    main()
