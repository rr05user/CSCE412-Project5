"""Agent 5: CI/CD failure diagnosis and recovery planning."""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"


def run_verification():
    result = subprocess.run(
        ["python", "scripts/verify_production.py"],
        cwd=ROOT,
        capture_output=True,
        text=True
    )
    return {
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-3000:]
    }


def diagnose(result):
    if result["passed"]:
        return {
            "summary": "Production verification succeeded",
            "likely_causes": [],
            "proposed_actions": []
        }

    try:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(ROOT / ".env")

        response = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AWS CI/CD recovery agent. "
                        "Analyze actual verification failures. "
                        "Return JSON with summary, likely_causes "
                        "(array), proposed_actions (array). "
                        "Never claim an action was executed. "
                        "Recommend human approval before rollback."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(result)
                }
            ]
        )

        return json.loads(response.choices[0].message.content)

    except Exception as exc:
        return {
            "summary": "Verification failed; AI diagnosis unavailable",
            "likely_causes": [str(exc)[:200]],
            "proposed_actions": [
                "Inspect production release and deployment logs",
                "Consider approved rollback"
            ]
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-release")
    args = parser.parse_args()

    if args.expected_release:
        os.environ["EXPECTED_RELEASE"] = args.expected_release

    result = run_verification()
    analysis = diagnose(result)

    report = {
        "agent": "cicd_recovery_agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verification": result,
        "analysis": analysis,
        "rollback_recommended": not result["passed"],
        "rollback_executed": False,
        "approval_required": True
    }

    OUTPUTS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)

    (OUTPUTS / "recovery_plan.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    (LOGS / "cicd_recovery_agent.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
