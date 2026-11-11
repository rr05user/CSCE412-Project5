"""CSCE 412 - Agent 3: AWS Deployment Planner (dry run)."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
SERVICES = {"S3", "CloudFront", "Route 53", "ACM"}

SYSTEM = """
You are a specialized AWS deployment planning AI agent.
Plan the deployment of a five-page static website.

Use only these AWS services:
S3, CloudFront, Route 53, ACM.

Requirements:
- Private S3 bucket
- CloudFront Origin Access Control
- HTTPS certificate from ACM in us-east-1
- HTTP-to-HTTPS redirect
- Route 53 DNS for the registered domain
- Human approval before infrastructure changes

Respond with JSON containing:
summary: string
services: array of service names
steps: array of objects containing service, action,
expected_result, approval_required
risks: array of strings

Do not claim that AWS resources were created.
Do not execute commands.

IMPORTANT: Return at least 8 distinct deployment steps.
Every step must contain:
- service
- action
- expected_result
- approval_required

Include separate steps for:
1. Creating a private S3 bucket
2. Uploading website files to S3
3. Configuring CloudFront Origin Access Control
4. Creating a CloudFront distribution
5. Configuring HTTP-to-HTTPS redirects
6. Requesting an ACM certificate in us-east-1
7. Validating the ACM certificate through DNS
8. Configuring Route 53 DNS records

Use only the four approved AWS service names.
"""

def validate(plan):
    if not isinstance(plan.get("summary"), str):
        raise ValueError("Missing summary")

    services = plan.get("services")
    if not isinstance(services, list):
        raise ValueError("Invalid services")
    if set(services) != SERVICES:
        raise ValueError("Incorrect AWS services")

    steps = plan.get("steps")
    if not isinstance(steps, list) or len(steps) < 5:
        raise ValueError("Insufficient deployment steps")

    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("Invalid deployment step")
        if step.get("service") not in SERVICES:
            raise ValueError("Unapproved AWS service")
        if not isinstance(step.get("action"), str):
            raise ValueError("Missing action")
        if not isinstance(step.get("expected_result"), str):
            raise ValueError("Missing expected result")
        if not isinstance(step.get("approval_required"), bool):
            raise ValueError("Missing approval flag")

    if not any(s["approval_required"] for s in steps):
        raise ValueError("Approval checkpoint required")

    if not isinstance(plan.get("risks"), list):
        raise ValueError("Missing risks")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    args = parser.parse_args()

    domain = args.domain.strip().lower()

    requirements_file = ROOT / "outputs" / "requirements.json"

    if not requirements_file.exists():
        parser.error("Run python agent.py first")

    required_pages = [
        "index.html", "about.html", "projects.html",
        "skills.html", "contact.html", "404.html"
    ]

    for page in required_pages:
        if not (ROOT / "website" / page).exists():
            parser.error("Missing website page: " + page)

    requirements = json.loads(
        requirements_file.read_text(encoding="utf-8-sig")
    )

    print("Deployment Agent: reading previous agent output")
    print("Generating AWS deployment plan...")

    task = {
        "domain": domain,
        "region": "us-east-1",
        "requirements": requirements,
        "website_pages": required_pages
    }

    client = OpenAI()

    for attempt in range(1, 4):
        print(f"Generating deployment plan: attempt {attempt}/3")

        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(task)}
            ]
        )

        try:
            plan = json.loads(response.choices[0].message.content)
            validate(plan)
            print("Deployment plan validated successfully")
            break
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Validation failed: {exc}")
            if attempt == 3:
                raise
    output_dir = ROOT / "outputs"
    logs_dir = ROOT / "logs"
    output_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    result = {
        "created_at": timestamp,
        "agent": "deployment_agent",
        "model": MODEL,
        "domain": domain,
        "mode": "DRY_RUN",
        "executed_aws_operations": 0,
        "plan": plan
    }

    (output_dir / "deployment_plan.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    (logs_dir / "deployment_agent.json").write_text(
        json.dumps({
            "timestamp": timestamp,
            "agent": "deployment_agent",
            "status": "SUCCESS",
            "validation": "PASS",
            "mode": "DRY_RUN",
            "executed_aws_operations": 0
        }, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(plan, indent=2))
    print("Validation: PASS")
    print("Saved to: outputs/deployment_plan.json")
    print("Log saved to: logs/deployment_agent.json")
    print("AWS resources created: 0")


if __name__ == "__main__":
    main()
