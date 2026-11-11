"""Agent 4: Real AWS website verification and AI diagnosis."""
import argparse
import json
import os
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        return None

opener = urllib.request.build_opener(NoRedirect())

def http_check(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "CSCE412-Verifier/1.0"}
    )
    try:
        with opener.open(req, timeout=15) as response:
            return {
                "status": response.status,
                "location": response.headers.get("Location", "")
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "location": e.headers.get("Location", "")
        }
    except Exception as e:
        return {"error": str(e)[:200]}

def aws_check(*args):
    cmd = [
        "aws", "--profile", "csce412",
        "--region", "us-east-1",
        "--no-cli-pager", *args
    ]
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if p.returncode:
            return {"error": p.stderr.strip()[:250]}
        return json.loads(p.stdout)
    except Exception as e:
        return {"error": str(e)[:250]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain", default="csce412rahul021005.me"
    )
    args = parser.parse_args()
    domain = args.domain.strip().lower()

    required = [
        "requirements.json",
        "deployment_plan.json",
        "aws_state.json"
    ]
    for name in required:
        if not (ROOT / "outputs" / name).exists():
            parser.error("Missing outputs/" + name)

    state = json.loads(
        (ROOT / "outputs/aws_state.json").read_text(
            encoding="utf-8-sig"
        )
    )
    plan = json.loads(
        (ROOT / "outputs/deployment_plan.json").read_text(
            encoding="utf-8-sig"
        )
    )

    if plan.get("domain") != domain:
        parser.error("Deployment plan has the wrong domain")

    cloudfront = state.get("cloudfront") or {}
    if not cloudfront.get("domain"):
        parser.error("CloudFront state is missing")

    checks = []

    def record(name, result, passed):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "observed": result
        })

    base = "https://" + domain
    print("Testing:", base)

    pages = [
        "/", "/index.html", "/about.html",
        "/projects.html", "/skills.html",
        "/contact.html", "/assets/style.css",
        "/assets/site.js"
    ]

    for page in pages:
        result = http_check(base + page)
        record(
            "HTTPS " + page,
            result, result.get("status") == 200
        )

    redirect = http_check("http://" + domain + "/")
    record(
        "HTTP to HTTPS redirect",
        redirect,
        redirect.get("status") in (301, 302, 307, 308)
        and redirect.get("location", "").startswith(
            "https://" + domain + "/"
        )
    )

    missing = http_check(
        base + "/csce412-nonexistent-page-49327.html"
    )
    record(
        "Custom 404 response",
        missing, missing.get("status") == 404
    )

    cdn = http_check(
        "https://" + cloudfront["domain"] + "/index.html"
    )
    record(
        "CloudFront delivery",
        cdn, cdn.get("status") == 200
    )

    bucket = state["bucket"]
    s3 = http_check(
        "https://" + bucket +
        ".s3.us-east-1.amazonaws.com/index.html"
    )
    record(
        "Anonymous S3 access denied",
        s3, s3.get("status") == 403
    )

    try:
        with socket.create_connection(
            (domain, 443), timeout=12
        ) as sock:
            with ssl.create_default_context().wrap_socket(
                sock, server_hostname=domain
            ) as tls:
                cert = tls.getpeercert()
                names = [
                    name for kind, name in
                    cert.get("subjectAltName", [])
                    if kind == "DNS"
                ]
                valid = domain in names or any(
                    n.startswith("*.")
                    and domain.endswith(n[1:])
                    for n in names
                )
                record(
                    "Valid matching TLS certificate",
                    {"dns_names": names,
                     "protocol": tls.version()},
                    valid
                )
    except Exception as e:
        record(
            "Valid matching TLS certificate",
            {"error": str(e)[:200]}, False
        )

    block = aws_check(
        "s3api", "get-public-access-block",
        "--bucket", bucket, "--output", "json"
    )
    flags = block.get(
        "PublicAccessBlockConfiguration", {}
    )
    record(
        "S3 public access blocked",
        block,
        len(flags) == 4 and all(flags.values())
    )

    dist = aws_check(
        "cloudfront", "get-distribution",
        "--id", cloudfront["id"], "--output", "json"
    )
    info = dist.get("Distribution", {})
    record(
        "CloudFront deployed",
        {"status": info.get("Status"),
         "error": dist.get("error")},
        info.get("Status") == "Deployed"
    )

    results = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "agent": "verification_agent",
        "domain": domain,
        "source_artifacts": [
            "outputs/deployment_plan.json",
            "outputs/aws_state.json"
        ],
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks)
    }

    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    (ROOT / "outputs/verification_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(status + ":", check["check"])

    print(
        f"Verification: {results['passed']}/"
        f"{results['total']} checks passed"
    )

    system = """
    You are an AWS verification and diagnosis AI agent.
    Interpret ACTUAL technical test evidence.
    Approved services: S3, CloudFront, Route 53, ACM.
    Do not invent test results or claim untested success.
    Identify likely causes for any failed checks.
    Suggest corrective actions requiring human approval
    for changes to cloud infrastructure.
    Return JSON with:
    summary: string
    likely_causes: array of strings
    proposed_actions: array of strings
    limitations: array of strings
    """

    try:
        response = OpenAI().chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user",
                 "content": json.dumps(results)}
            ]
        )
        analysis = json.loads(
            response.choices[0].message.content
        )
        results["analysis"] = analysis
    except Exception as e:
        results["analysis_error"] = str(e)[:250]

    (ROOT / "logs/verification_agent.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    print("Saved: outputs/verification_results.json")
    print("Saved: logs/verification_agent.json")

if __name__ == "__main__":
    main()
