"""CSCE 412: AWS deployment runner for Agent 3."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "website"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"
PROFILE = "csce412"
REGION = "us-east-1"
PAGES = (
    "index.html", "about.html", "projects.html",
    "skills.html", "contact.html", "404.html"
)


def aws(*args):
    """Execute only approved, predefined AWS CLI operations."""
    cmd = ["aws", "--profile", PROFILE, "--region", REGION, *args]
    result = subprocess.run(
        cmd, capture_output=True, text=True, shell=False
    )
    if result.returncode:
        raise RuntimeError(
            f"AWS command failed: {' '.join(args[:3])}\n"
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def save_log(data):
    LOGS.mkdir(parents=True, exist_ok=True)
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    (LOGS / "s3_deployment.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan_file = OUTPUTS / "deployment_plan.json"
    if not plan_file.exists():
        parser.error("Missing deployment plan. Run Agent 3 first.")

    plan = json.loads(plan_file.read_text(encoding="utf-8-sig"))
    if plan.get("mode") != "DRY_RUN" or not isinstance(plan.get("plan"), dict):
        parser.error("Invalid deployment plan format")

    for page in PAGES:
        if not (SITE / page).is_file():
            parser.error(f"Missing website/{page}")

    if not (SITE / "assets" / "style.css").is_file():
        parser.error("Missing website stylesheet")

    print("Verifying AWS credentials...")
    identity = json.loads(
        aws("sts", "get-caller-identity", "--output", "json")
    )

    account = identity["Account"]
    arn = identity["Arn"]
    if not arn.endswith(":user/csce412-deployer"):
        parser.error("Unexpected AWS identity: " + arn)

    bucket = "csce412-project5-" + account

    print("\nAWS DEPLOYMENT PLAN")
    print("Account:", account)
    print("Region:", REGION)
    print("Bucket:", bucket)
    print("1. Create private S3 bucket if absent")
    print("2. Enable S3 Block Public Access")
    print("3. Upload website files")
    print("4. Verify uploaded files and bucket settings")

    if not args.apply:
        print("\nDRY RUN COMPLETE")
        print("AWS resources created: 0")
        save_log({
            "agent": "deployment_runner",
            "status": "DRY_RUN",
            "bucket": bucket,
            "aws_changes": 0
        })
        return

    approval = input("\nType DEPLOY to approve AWS changes: ")
    if approval.strip() != "DEPLOY":
        print("Cancelled.")
        return

    actions = []
    try:
        # Check whether the project's bucket already exists.
        probe = subprocess.run(
            [
                "aws", "--profile", PROFILE, "--region", REGION,
                "s3api", "head-bucket", "--bucket", bucket
            ],
            capture_output=True, text=True, shell=False
        )

        if probe.returncode:
            message = (probe.stderr + probe.stdout).strip()
            if "404" not in message and "Not Found" not in message:
                raise RuntimeError(
                    "Cannot inspect S3 bucket: " + message
                )
            aws("s3api", "create-bucket", "--bucket", bucket)
            actions.append("bucket_created")
        else:
            print("Existing bucket found. Reusing it.")

        aws(
            "s3api", "put-public-access-block",
            "--bucket", bucket,
            "--public-access-block-configuration",
            "BlockPublicAcls=true,IgnorePublicAcls=true,"
            "BlockPublicPolicy=true,RestrictPublicBuckets=true"
        )
        actions.append("public_access_block_enabled")

        print("Uploading website...")
        print(aws(
            "s3", "sync", str(SITE),
            f"s3://{bucket}/", "--no-progress"
        ))
        actions.append("website_uploaded")

        settings = json.loads(aws(
            "s3api", "get-public-access-block",
            "--bucket", bucket, "--output", "json"
        ))
        if not all(
            settings["PublicAccessBlockConfiguration"].values()
        ):
            raise RuntimeError("Public access verification failed")

        listing = json.loads(aws(
            "s3api", "list-objects-v2",
            "--bucket", bucket, "--output", "json"
        ))
        uploaded = {
            item["Key"] for item in listing.get("Contents", [])
        }
        if not set(PAGES).issubset(uploaded):
            raise RuntimeError("Required pages missing from S3")

        state = {
            "bucket": bucket,
            "region": REGION,
            "phase": "S3_UPLOADED",
            "cloudfront": None
        }
        (OUTPUTS / "aws_state.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )

        save_log({
            "agent": "deployment_runner",
            "status": "SUCCESS",
            "bucket": bucket,
            "actions": actions
        })

        print("\nS3 UPLOAD VERIFIED")
        print("Next phase: CloudFront distribution")

    except Exception as error:
        save_log({
            "agent": "deployment_runner",
            "status": "FAILED",
            "bucket": bucket,
            "actions_completed": actions,
            "error": str(error)
        })
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
