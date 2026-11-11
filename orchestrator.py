"""CSCE 412 Project 5: coordinate existing specialized agents."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"


def now():
    return datetime.now(timezone.utc).isoformat()


def read_artifact(relative_path):
    path = ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"Missing agent artifact: {relative_path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain", default="csce412rahul021005.me"
    )
    parser.add_argument(
        "--rebuild-website", action="store_true",
        help="Regenerate local website; does not upload it to AWS"
    )
    args = parser.parse_args()
    domain = args.domain.strip().lower()

    LOGS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    execution = {
        "started_at": now(),
        "domain": domain,
        "mode": "REBUILD_LOCAL" if args.rebuild_website
                else "VERIFY_DEPLOYED",
        "steps": [],
        "handoffs": [],
        "status": "RUNNING"
    }

    def handoff(sender, receiver, artifact):
        read_artifact(artifact)
        execution["handoffs"].append({
            "from": sender,
            "to": receiver,
            "artifact": artifact,
            "checked_at": now()
        })
        print(f"HANDOFF: {sender} -> {receiver}: {artifact}")

    def run_agent(name, args_list, expected_file):
        print(f"\n=== {name} ===", flush=True)
        command = [sys.executable, *args_list]

        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=240
        )

        if result.stdout:
            print(result.stdout[-5000:], flush=True)
        if result.stderr:
            print(result.stderr[-2000:],
                  file=sys.stderr, flush=True)

        execution["steps"].append({
            "agent": name,
            "command": args_list,
            "timestamp": now(),
            "exit_code": result.returncode,
            "output_artifact": expected_file,
            "status": "PASS" if result.returncode == 0
                      else "FAIL",
            "stdout_tail": result.stdout[-3000:],
            "stderr_tail": result.stderr[-1500:]
        })

        if result.returncode:
            raise RuntimeError(
                f"{name} failed; see terminal output"
            )

        artifact_path = ROOT / expected_file
        if not artifact_path.is_file():
            raise RuntimeError(
                f"Missing expected output: {expected_file}"
            )
        if artifact_path.suffix == ".json":
            read_artifact(expected_file)

    try:
        # Agent 1: Generate requirements.
        run_agent(
            "Requirements Agent",
            ["agent.py"],
            "outputs/requirements.json"
        )

        handoff(
            "Requirements Agent",
            "Website Builder Agent",
            "outputs/requirements.json"
        )

        # Agent 2: Check existing site or regenerate locally.
        website_cmd = ["agents/website_builder.py"]
        if not args.rebuild_website:
            website_cmd.append("--check")

        run_agent(
            "Website Builder Agent",
            website_cmd,
            "website/index.html"
        )

        for page in (
            "index.html", "about.html", "projects.html",
            "skills.html", "contact.html", "404.html"
        ):
            if not (ROOT / "website" / page).is_file():
                raise RuntimeError(
                    "Missing website page: " + page
                )

        execution["handoffs"].append({
            "from": "Website Builder Agent",
            "to": "Deployment Agent",
            "artifact": "website/*.html + website/assets/",
            "checked_at": now()
        })
        print(
            "HANDOFF: Website Builder -> Deployment Agent: "
            "website files"
        )

        # Agent 3: Generate and validate deployment plan.
        run_agent(
            "Deployment Agent",
            [
                "agents/deployment_agent.py",
                "--domain", domain
            ],
            "outputs/deployment_plan.json"
        )

        plan = read_artifact(
            "outputs/deployment_plan.json"
        )
        if plan.get("domain") != domain:
            raise RuntimeError(
                "Deployment plan domain mismatch"
            )

        handoff(
            "Deployment Agent",
            "Verification Agent",
            "outputs/deployment_plan.json"
        )

        if args.rebuild_website:
            execution["status"] = (
                "LOCAL_BUILD_READY_FOR_REVIEW"
            )
            print(
                "\nLocal website regenerated. Review and "
                "re-deploy before live verification."
            )
        else:
            read_artifact("outputs/aws_state.json")

            # Agent 4: Test the actual deployed AWS website.
            run_agent(
                "Verification Agent",
                [
                    "agents/verification_agent.py",
                    "--domain", domain
                ],
                "outputs/verification_results.json"
            )

            result = read_artifact(
                "outputs/verification_results.json"
            )
            execution["verification"] = {
                "passed": result.get("passed"),
                "total": result.get("total")
            }

            if (
                not result.get("total")
                or result.get("passed") != result.get("total")
            ):
                execution["status"] = "VERIFICATION_FAILED"
                raise RuntimeError(
                    "Verification failed. See "
                    "outputs/verification_results.json"
                )

            execution["status"] = "PASS"
            print(
                f"\nORCHESTRATION PASS: "
                f"{result['passed']}/{result['total']} checks"
            )

    except Exception as error:
        if execution["status"] == "RUNNING":
            execution["status"] = "FAILED"
        execution["error"] = str(error)
        print(
            "\nORCHESTRATION ERROR:", error,
            file=sys.stderr
        )
        return_code = 1
    else:
        return_code = 0
    finally:
        execution["finished_at"] = now()

        (LOGS / "orchestrator.json").write_text(
            json.dumps(execution, indent=2),
            encoding="utf-8"
        )

        (OUTPUTS / "agent_handoffs.json").write_text(
            json.dumps(
                execution["handoffs"], indent=2
            ),
            encoding="utf-8"
        )

        print("Saved: logs/orchestrator.json")
        print("Saved: outputs/agent_handoffs.json")

    return return_code


if __name__ == "__main__":
    sys.exit(main())
