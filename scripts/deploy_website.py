import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"

BUCKET = "csce412-project5-027677879294"
DISTRIBUTION = "EC3GYYDBXOHBS"
REGION = "us-east-1"


def aws(*args):
    command = ["aws", *args, "--region", REGION]
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main():
    manifest_path = WEBSITE / "release.json"
    if not manifest_path.is_file():
        raise SystemExit("Missing website/release.json")

    manifest = json.loads(manifest_path.read_text())
    release_id = manifest.get("release_id", "")

    if len(release_id) != 40 or any(
        c not in "0123456789abcdef" for c in release_id.lower()
    ):
        raise SystemExit("Invalid release ID")

    if not (WEBSITE / "index.html").is_file():
        raise SystemExit("Missing website/index.html")

    if os.environ.get("CONFIRM_PRODUCTION_DEPLOY") != "yes":
        raise SystemExit("Production deployment not enabled")

    print("Deploying release:", release_id)

    aws(
        "s3", "sync", str(WEBSITE), f"s3://{BUCKET}/",
        "--exclude", "*.pyc",
        "--exclude", "__pycache__/*",
    )

    aws(
        "cloudfront", "create-invalidation",
        "--distribution-id", DISTRIBUTION,
        "--paths", "/*",
    )

    aws(
        "s3api", "wait", "object-exists",
        "--bucket", BUCKET,
        "--key", "release.json",
    )

    print("Deployment commands completed:", release_id)


if __name__ == "__main__":
    main()
