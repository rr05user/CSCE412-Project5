import os
import subprocess
from pathlib import Path

BUCKET = "csce412-project5-027677879294"
DISTRIBUTION = "EC3GYYDBXOHBS"
BACKUP = Path("project6-backups/production-before-cicd")

def run(*args):
    subprocess.run(
        ["aws", *args, "--region", "us-east-1",
         "--profile", os.environ.get("AWS_PROFILE", "csce412")],
        check=True
    )

def main():
    if os.environ.get("CONFIRM_ROLLBACK") != "yes":
        raise SystemExit("Set CONFIRM_ROLLBACK=yes to restore")

    if not (BACKUP / "index.html").exists():
        raise SystemExit("Backup missing")

    run("s3", "sync", str(BACKUP), f"s3://{BUCKET}/")

    run(
        "cloudfront", "create-invalidation",
        "--distribution-id", DISTRIBUTION,
        "--paths", "/*"
    )

    print("Rollback upload and invalidation requested")

if __name__ == "__main__":
    main()
