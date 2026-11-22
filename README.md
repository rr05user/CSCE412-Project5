# CSCE 412 — Project 6: AI Agents and AWS CI/CD

**Student:** Rahul Ravi  
**Course:** CSCE 412, Texas A&M University  
**Repository:** [rr05user/CSCE412-Project5](https://github.com/rr05user/CSCE412-Project5) — **`project6` branch**  
**Live site:** https://csce412rahul021005.me  
**Implementation:** Python, OpenAI API, GitHub, AWS CodePipeline, CodeBuild, S3, CloudFront, Route 53, and ACM

## 1. Project overview

Project 6 extends the earlier Project 5 AI-assisted static website into a continuous integration and continuous delivery (CI/CD) system. Five specialized Python agents generate requirements, validate the website, plan an approved deployment, verify the live AWS infrastructure, and diagnose production release failures. The GitHub-to-AWS pipeline separately runs automated tests, publishes the tested website, creates a CloudFront invalidation, and checks the deployed release.

**Deployment environment:** a static portfolio website with Home, About, Projects, Skills, and Contact pages, plus supporting assets and a custom not-found response. S3 is private; CloudFront serves the website over HTTPS at the custom domain.

### Implemented features

- **Five specialized agents** with distinct responsibilities and JSON results.
- **Real OpenAI API integration** using `gpt-4.1-mini` (configurable via `.env`) for agent reasoning and diagnosis.
- **Structured handoffs and audit logs** in `outputs/` and `logs/`.
- **GitHub-triggered AWS CodePipeline:** Source → CodeBuild Test → CodeBuild Deploy.
- **Automated pytest suite** and JUnit test-report generation in CodeBuild.
- **Release identification:** the deployed `website/release.json` records the Git source commit as a 40-character release ID.
- **Post-deployment verification** of the live release; a separate agent checks a broader set of live site/AWS properties.
- **Human approval controls** for direct local S3 sync and manual rollback execution.
- **Secrets protection** using local `.env`, AWS credential profiles or build roles, and `.gitignore`.

## 2. System architecture

```text
Developer: commit and push to GitHub (project6)
                       |
                       v
            AWS CodePipeline
                       |
      +----------------+----------------+
      |                                 |
      v                                 |
 GitHub Source                           |
      |                                  |
      v                                  |
 CodeBuild Test                          |
  - scripts/make_release.py              |
  - pytest tests/                        |
  - JUnit report                         |
  - website artifact + deploy scripts    |
      |                                  |
      v                                  |
 CodeBuild Deploy                        |
  - scripts/deploy_website.py            |
  - private S3 upload                    |
  - CloudFront cache invalidation        |
  - scripts/verify_production.py         |
      |                                  |
      v                                  |
 S3 + CloudFront + HTTPS custom domain <-+

Separate, manually invoked five-agent workflow:

 Agent 1: Requirements (OpenAI)
       | outputs/requirements.json
       v
 Agent 2: Website Builder / Checker
       | website/index.html
       v
 Agent 3: Deployment Planner (OpenAI)
       | outputs/deployment_plan.json
       | human approval required for --apply
       v
 Agent 4: Verification and Diagnosis
       | outputs/verification_results.json
       v
 Agent 5: CI/CD Recovery and Diagnosis (OpenAI on failure)
       | outputs/recovery_plan.json
       v
 logs/orchestrator_final.json + outputs/agent_handoffs_final.json
```

**Important separation:** CodePipeline automatically executes the build, test, deployment, and production verification scripts. The full five-agent orchestrator is run explicitly with `python orchestrator_final.py`; it is **not** a CodePipeline stage. The CI/CD recovery agent is integrated into this local orchestration workflow, but is not automatically invoked by a failed CodeBuild execution.

## 3. Agent responsibilities and communication

| Agent | Implementation | Responsibility | Main result |
|---|---|---|---|
| 1 — Requirements | `agent.py` | Use the OpenAI API to interpret the website/infrastructure requirements into a structured plan. | `outputs/requirements.json` |
| 2 — Website Builder | `agents/website_builder.py` | Inspect and validate website pages and assets; check readiness before deployment. | `website/index.html` and console validation |
| 3 — Deployment Planner | `agents/deployment_agent.py` | Inspect AWS deployment context, generate a structured deployment plan, and identify actions needing approval. Default mode is a dry run. | `outputs/deployment_plan.json`, `logs/deployment_agent.json` |
| 4 — Verification and Diagnosis | `agents/verification_agent.py` | Check the live site, HTTPS, redirects, CloudFront, S3 privacy, TLS, and AWS state; record results. | `outputs/verification_results.json`, `logs/verification_agent.json` |
| 5 — CI/CD Recovery | `agents/cicd_recovery_agent.py` | Run production-release verification, parse exit status/output, and use OpenAI to propose recovery actions when verification fails. Rollback remains approval-gated. | `outputs/recovery_plan.json`, `logs/cicd_recovery_agent.json` |

`orchestrator_final.py` calls agents in sequence, checks process exit codes and output artifacts, validates the earlier verification result, hands off the verification artifact, then runs Agent 5. It saves a final audit to `logs/orchestrator_final.json` and handoff records to `outputs/agent_handoffs_final.json`.

The agents do not execute arbitrary commands generated by the language model. Python controls the tool invocations, validates artifacts and expected AWS settings, and requires approval for a manual deployment. Agent 5's AI diagnosis is advisory, not an automatically executed repair.

## 4. Repository layout

```text
.
├── agent.py                         # Agent 1: requirements
├── orchestrator_final.py            # Five-agent orchestration and audit
├── agents/
│   ├── website_builder.py           # Agent 2
│   ├── deployment_agent.py           # Agent 3
│   ├── verification_agent.py         # Agent 4
│   └── cicd_recovery_agent.py        # Agent 5
├── scripts/
│   ├── make_release.py              # Commit-based release manifest
│   ├── deploy_website.py            # S3 sync + CloudFront invalidation
│   ├── verify_production.py         # Live release verification
│   └── rollback_website.py          # Approval-gated manual backup restore
├── tests/                           # pytest tests, including recovery tests
├── website/                         # HTML, CSS, JS and published content
├── buildspec-test.yml               # CodeBuild test phase
├── buildspec-deploy.yml             # CodeBuild deployment phase
├── requirements.txt                 # Python API dependencies
├── .env.example                     # Safe API configuration template
├── .gitignore                       # Excludes local secrets/artifacts
└── README.md                        # This file
```

Local runtime outputs in `outputs/`, `logs/`, `reports/`, `project6-backups/`, and generated `website/release.json` are ignored by Git as applicable. They are created or used during local runs and/or the build pipeline.

## 5. Reproduce the project locally (Windows PowerShell)

### Prerequisites

- Python 3.10+ with `pip` (the AWS CodeBuild buildspecs use Python **3.12**).
- Git and access to the **private** repository.
- AWS CLI v2 with permissions to inspect the existing deployment, configured as profile `csce412` for local runs.
- An OpenAI Platform API key with API billing/quota available; a ChatGPT subscription by itself does not provide API credits.
- Network access to the deployed domain and AWS services.

### Clone and install

```powershell
git clone https://github.com/rr05user/CSCE412-Project5.git
cd CSCE412-Project5
git checkout project6
python -m pip install -r requirements.txt
python -m pip install pytest
```

If the repository is already cloned, switch to the `project6` branch and pull its latest commits instead.

### Set environment variables (local only)

```powershell
Copy-Item .env.example .env
notepad .env
```

Set the following values inside `.env`:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

**Do not commit `.env` or paste a real key into logs, documentation, or GitHub.** The example file contains placeholders only. Agent scripts using the OpenAI API load local configuration via `python-dotenv`.

Configure AWS CLI credentials through the standard AWS CLI configuration process; do not add access keys to the repository. For a preconfigured machine, confirm the identity:

```powershell
aws sts get-caller-identity --profile csce412
```

### Run automated tests

```powershell
python -m pytest -q tests
```

Most recently verified local result: **16 passed**. This includes tests for Agent 5's successful-verification behavior, failure fallback, and rollback-approval controls. Tests are also run by CodeBuild as part of the CI pipeline; CI does not need a live OpenAI key to execute this pytest suite.

### Validate the OpenAI API connection

The following is a small, real, billable API request:

```powershell
python -c "from dotenv import load_dotenv; from openai import OpenAI; load_dotenv(override=True); r=OpenAI().chat.completions.create(model='gpt-4.1-mini', messages=[{'role':'user','content':'Reply with exactly OK'}], max_tokens=10); print(r.choices[0].message.content)"
```

Expected response: `OK`.

### Execute the full five-agent workflow (default: no manual S3 sync)

```powershell
Remove-Item Env:EXPECTED_RELEASE -ErrorAction SilentlyContinue
python orchestrator_final.py
```

A successful run ends with:

```text
WORKFLOW PASS: Five agents, approved AWS tools, 15/15 live checks
```

The default orchestrator mode performs checks/planning and AWS reads, without the manual S3 sync. The optional command `python orchestrator_final.py --apply` introduces a manual S3 sync that requires the user to type `SYNC`. Only use `--apply` if a real deployment is intended and approved; the normal GitHub CI/CD pipeline is the preferred deployment path.

## 6. CI/CD pipeline

**Pipeline name:** `csce412-project6-pipeline`  
**Region:** `us-east-1`  
**Source:** configured GitHub repository and `project6` branch  
**Stages:** GitHub Source → CodeBuild Test → CodeBuild Deploy

| Stage | AWS job/configuration | Actions |
|---|---|---|
| Source | GitHub source action | Retrieves a source revision when the configured branch changes. |
| Test | CodeBuild project `csce412-project6-test` / `buildspec-test.yml` | Uses Python 3.12, creates release metadata, runs `pytest` with a JUnit XML report, publishes the tested website and deployment scripts as artifacts. |
| Deploy | CodeBuild project `csce412-project6-deploy` / `buildspec-deploy.yml` | Verifies required files, deploys the site to S3, creates a CloudFront invalidation, and runs post-deployment release verification. |

The deployment build environment requires `CONFIRM_PRODUCTION_DEPLOY=yes`. `scripts/deploy_website.py` checks this variable before modifying production.

**Published infrastructure**

- **S3 bucket:** `csce412-project5-027677879294` (private; versioning enabled).
- **CloudFront distribution:** `EC3GYYDBXOHBS`.
- **Website:** https://csce412rahul021005.me.
- **DNS and TLS:** Route 53 records and an ACM certificate for HTTPS.

### Trigger and inspect a CI/CD run

Commit and push a change to the configured `project6` branch:

```powershell
git add README.md
git commit -m "Document Project 6 architecture and deployment"
git push origin project6
```

Inspect the live pipeline state:

```powershell
aws codepipeline get-pipeline-state `
  --name csce412-project6-pipeline `
  --region us-east-1 `
  --profile csce412 `
  --query "stageStates[].{Stage:stageName,Status:latestExecution.status}" `
  --output table
```

Look for `Succeeded` for Source, Test, and Deploy. Review CodeBuild logs and the JUnit test report for detailed evidence if a stage fails. The pipeline was last confirmed with all three stages successful on **November 22, 2026**.

## 7. Release tracking and production verification

The test stage runs `scripts/make_release.py`, producing `website/release.json`, which includes a `release_id`, `source_commit`, and `generated_utc`. The release ID identifies the tested Git commit. The deploy stage uploads the website, including the manifest, then invokes `scripts/verify_production.py` with the expected release ID from the build artifact.

Check a release from PowerShell:

```powershell
Invoke-RestMethod https://csce412rahul021005.me/release.json
```

Verify that the deployed revision matches the current local HEAD **after the pipeline finishes**:

```powershell
$env:EXPECTED_RELEASE = (git rev-parse HEAD).Trim()
python scripts/verify_production.py
Remove-Item Env:EXPECTED_RELEASE -ErrorAction SilentlyContinue
```

Do not interpret a mismatch as a broken website if the pipeline has not yet deployed the latest commit. Production verification retries to accommodate propagation delays, but a persistent mismatch causes its check to fail.

## 8. Agent 5: simulated failure, AI diagnosis, and rollback controls

### Safe failure-diagnosis demonstration

To demonstrate how the recovery agent interprets a real tool result, intentionally provide a **wrong expected release ID**:

```powershell
python agents/cicd_recovery_agent.py --expected-release 0000000000000000000000000000000000000000
```

This runs the read-only production release checker, obtains a nonzero exit code, and sends the observed failure details to OpenAI. It writes a JSON diagnosis with `summary`, `likely_causes`, and `proposed_actions`. Example report fields:

```json
{
  "rollback_recommended": true,
  "rollback_executed": false,
  "approval_required": true
}
```

The actual report also contains the underlying verification output and AI-generated analysis. **This is an intentional mismatch for demonstration purposes; it does not mean production was broken.** Do **not** add `--execute-rollback` to the demonstration command. The standalone recovery-agent report does not by itself mean a rollback occurred.

When the live release passes, the recovery agent records `verification.passed=true`, `rollback_recommended=false`, and an empty list of recovery actions, without making an unnecessary AI diagnosis call.

### Manual rollback implementation and safety limitation

There is a manual rollback path in `scripts/rollback_website.py`. It uses `project6-backups/production-before-cicd/` as its **local** restore source, uploads it to the existing S3 bucket, and requests a CloudFront invalidation. The script refuses to run unless `CONFIRM_ROLLBACK=yes` is explicitly set. Agent 5 adds a separate `--execute-rollback` flag and checks the same approval environment variable before calling the rollback script.

**Limitation:** The configured backup predates the CI/CD workflow; the script does **not** automatically select the most recent verified, known-good CI/CD release. It also uses `aws s3 sync` without deleting newer objects. Therefore, restoring it may leave a mixed website or an obsolete/missing release manifest. No production rollback has been demonstrated as successful. Do not run this operation without first inspecting and validating the backup, preserving the current production release, and obtaining explicit authorization. The simulated failure test above is deliberately read-only and is the recommended recovery demonstration for grading.

For a production-ready enhancement, store an immutable copy of each known-good release, verify its manifest, and restore the explicitly approved release before invalidating CloudFront and running post-rollback checks.

## 9. Validation and evidence

The following were verified on **November 22, 2026**:

| Check | Observed result |
|---|---|
| Local automated tests | **16/16 passed** (`python -m pytest -q tests`) |
| Python syntax | `orchestrator_final.py` and `agents/cicd_recovery_agent.py` compiled without errors |
| OpenAI API authentication | Live request returned `OK` |
| Simulated release mismatch | Agent 5 received six failed verification attempts and returned an AI-generated recovery analysis |
| Rollback during simulation | **Not executed**, as intended |
| Live infrastructure verification | **15/15 checks passed** |
| Five-agent orchestration | `WORKFLOW PASS` |
| Deployed release | `71c11ef8d72c0f9405b7502890dad455cf0dbfa2` |
| AWS CodePipeline | Source, Test, and Deploy stages reported `Succeeded` |
| Git secret handling | `.env` was ignored; working tree clean after prior source push |

**Evidence artifacts generated locally** (these are not committed because they may include environment details):

- `outputs/requirements.json`
- `outputs/deployment_plan.json`
- `outputs/verification_results.json`
- `outputs/recovery_plan.json`
- `outputs/agent_handoffs_final.json`
- `logs/deployment_agent.json`
- `logs/verification_agent.json`
- `logs/cicd_recovery_agent.json`
- `logs/orchestrator_final.json`

Supporting AWS evidence is available in CodePipeline stage execution history, CodeBuild execution logs, and JUnit test reports.

## 10. Security, approvals, and troubleshooting

### Security controls

- API keys belong in `.env` only; `.env` and related credential files are excluded by `.gitignore`.
- Do not store AWS access keys in source. Local commands use a named AWS CLI profile; CodeBuild uses its configured IAM role.
- S3 is private, anonymous S3 access is denied, and CloudFront provides public HTTPS delivery.
- The normal agent workflow is verify-only. Direct S3 sync requires typed `SYNC`; the deployment script has a separate production confirmation environment check.
- Recovery-agent recommendations do not automatically mutate AWS. Manual rollback requires explicit authorization and flags.
- The GitHub repository should remain private, with course staff granted the necessary access for grading.

### Troubleshooting

| Symptom | Next step |
|---|---|
| OpenAI `401` / expired API key | Replace the key in local `.env`; test with a small OpenAI request. Never publish the key. |
| OpenAI `429` / insufficient quota | Check OpenAI Platform billing and project usage limits. |
| `ModuleNotFoundError: openai` / `dotenv` | Run `python -m pip install -r requirements.txt`. |
| Tests fail locally | Run `python -m pytest -q tests` and inspect the failing assertion. |
| Release mismatch after a new push | Wait for the current CodePipeline execution to finish; verify the live `release.json` against the correct commit. |
| CodePipeline stage fails | Inspect the stage's CodeBuild logs and test results; do not assume a rollback executed. |
| AWS `AccessDenied` | Inspect which CLI identity/role is in use and request least-privilege permissions through the course's approved method; do not commit credentials. |
| Full orchestration fails while a direct API test works | Inspect `logs/orchestrator_final.json`, then the specific agent log and input artifact. |

## 11. Submission and reproducibility notes

- **Source branch to grade:** `project6` on the linked private GitHub repository.
- The files needed to inspect the agent code, CI/CD buildspecs, tests, and deployment/verification scripts are in the repository.
- `outputs/`, `logs/`, local backup files, API secrets, and runtime-generated deployment artifacts are excluded intentionally; use the commands above to reproduce results.
- Grant the course instructor/TA repository access where required. The README does not establish that access has already been granted.
- The pipeline and five-agent local workflow were demonstrated separately, as designed. The manual rollback remains a guarded, backup-based implementation rather than a fully automated recovery to the latest known-good CI release.

---

**Project outcome:** A functioning five-agent AI-assisted AWS website workflow, plus a successful GitHub-triggered CI/CD pipeline with automated tests, deploy verification, JSON release tracking, security checks, and human-in-the-loop deployment/recovery controls.
