"""CSCE 412: four-agent orchestration + approved AWS S3 tool execution."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOMAIN = "csce412rahul021005.me"
OUT = ROOT / "outputs"
LOGS = ROOT / "logs"
PROFILE = "csce412"


def load(relative):
    path = ROOT / relative
    if not path.is_file():
        raise RuntimeError("Missing artifact: " + relative)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="Offer human-approved website sync to existing S3 bucket"
    )
    args = parser.parse_args()
    LOGS.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    audit = {
        "mode": "APPROVED_SYNC" if args.apply else "VERIFY_ONLY",
        "started_at": now(), "domain": DOMAIN,
        "agents": [], "handoffs": [], "tools": [], "status": "RUNNING"
    }

    def handoff(sender, receiver, artifact):
        if not (ROOT / artifact).is_file():
            raise RuntimeError("Missing handoff: " + artifact)
        audit["handoffs"].append({
            "from": sender, "to": receiver,
            "artifact": artifact, "time": now()
        })
        print("HANDOFF", sender, "->", receiver, ":", artifact, flush=True)

    def run_agent(name, command, artifact):
        print("\nAGENT:", name, flush=True)
        result = subprocess.run(
            [sys.executable, *command], cwd=ROOT,
            capture_output=True, text=True, timeout=300
        )
        print(result.stdout[-1600:], flush=True)
        if result.stderr:
            print(result.stderr[-700:], file=sys.stderr, flush=True)
        audit["agents"].append({
            "name": name, "exit_code": result.returncode,
            "artifact": artifact, "finished_at": now()
        })
        if result.returncode or not (ROOT / artifact).is_file():
            raise RuntimeError(name + " failed")

    def aws(action, *args):
        command = [
            "aws", "--profile", PROFILE, "--region", "us-east-1",
            "--no-cli-pager", *args
        ]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True,
            text=True, timeout=120
        )
        audit["tools"].append({
            "agent": "Deployment", "action": action,
            "exit_code": result.returncode, "time": now()
        })
        if result.returncode:
            raise RuntimeError(action + ": " + result.stderr[-400:])
        return result.stdout.strip()

    try:
        run_agent(
            "Requirements", ["agent.py"],
            "outputs/requirements.json"
        )
        handoff(
            "Requirements", "Website Builder",
            "outputs/requirements.json"
        )
        run_agent(
            "Website Builder",
            ["agents/website_builder.py", "--check"],
            "website/index.html"
        )
        handoff(
            "Website Builder", "Deployment", "website/index.html"
        )
        run_agent(
            "Deployment Planner",
            ["agents/deployment_agent.py", "--domain", DOMAIN],
            "outputs/deployment_plan.json"
        )

        plan = load("outputs/deployment_plan.json")
        state = load("outputs/aws_state.json")
        if plan.get("domain") != DOMAIN or plan.get("mode") != "DRY_RUN":
            raise RuntimeError("Invalid plan or domain")

        bucket = state.get("bucket", "")
        distribution = (state.get("cloudfront") or {}).get("id")
        identity = json.loads(aws(
            "Read AWS identity", "sts", "get-caller-identity",
            "--output", "json"
        ))

        if bucket != "csce412-project5-" + identity["Account"] or not distribution:
            raise RuntimeError(
                "Unexpected bucket or missing existing CloudFront distribution"
            )

        if args.apply:
            print("\nThis syncs local website files to the EXISTING S3 bucket.")
            print("Bucket:", bucket)
            print("It will not delete objects or change CloudFront/DNS.")
            if input("Type SYNC to approve: ").strip() != "SYNC":
                raise RuntimeError("S3 sync not approved")

            output = aws(
                "Approved S3 website sync",
                "s3", "sync", str(ROOT / "website"),
                "s3://" + bucket + "/", "--no-progress"
            )
            print(output or "No files needed updating.")

        aws(
            "Inspect S3 privacy", "s3api",
            "get-public-access-block", "--bucket", bucket
        )
        aws(
            "Inspect CloudFront distribution", "cloudfront",
            "get-distribution", "--id", distribution
        )

        handoff(
            "Deployment", "Verification",
            "outputs/deployment_plan.json"
        )
        handoff(
            "Deployment", "Verification",
            "outputs/aws_state.json"
        )
        run_agent(
            "Verification and Diagnosis",
            ["agents/verification_agent.py", "--domain", DOMAIN],
            "outputs/verification_results.json"
        )

        verification = load("outputs/verification_results.json")
        audit["verification"] = {
            "passed": verification.get("passed"),
            "total": verification.get("total")
        }

        if verification.get("passed") != 15 or verification.get("total") != 15:
            raise RuntimeError(
                "Live verification did not pass all 15 checks"
            )

        audit["status"] = "PASS"
        print(
            "\nWORKFLOW PASS: Four agents, approved AWS tools, 15/15 live checks"
        )

    except Exception as exc:
        audit["status"] = "FAIL"
        audit["error"] = str(exc)
        print("\nWORKFLOW ERROR:", exc, file=sys.stderr)

    finally:
        audit["finished_at"] = now()
        (LOGS / "orchestrator_final.json").write_text(
            json.dumps(audit, indent=2), encoding="utf-8"
        )
        (OUT / "agent_handoffs_final.json").write_text(
            json.dumps(audit["handoffs"], indent=2), encoding="utf-8"
        )
        print("Saved: logs/orchestrator_final.json")

    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
