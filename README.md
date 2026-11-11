# CSCE 412 Project 5
## Secure AWS Website Using Multi-Agent AI

**Live website:** https://csce412rahul021005.me

### Project Overview

This project implements a cloud and HPC portfolio website
hosted on AWS and supported by a custom four-agent AI system.

The system assists with requirements analysis, website generation,
AWS deployment planning and execution, verification, and diagnosis.

### Cloud Architecture

- Amazon S3: Private static website storage
- Amazon CloudFront: HTTPS content delivery using Origin Access Control
- Amazon Route 53: Domain DNS routing
- AWS Certificate Manager: TLS certificate
- Namecheap: Domain registrar

### Multi-Agent Architecture

1. Requirements Agent (`agent.py`)
   Analyzes technical requirements using an LLM and creates JSON output.

2. Website Builder Agent (`agents/website_builder.py`)
   Generates website files and performs local verification.

3. Deployment Agent (`agents/deployment_agent.py`)
   Generates and validates deployment plans. Approved AWS operations
   are executed through scripts in `deploy/` and the final orchestrator.

4. Verification and Diagnosis Agent (`agents/verification_agent.py`)
   Performs live HTTPS, CloudFront, S3, and certificate checks.
   Uses an LLM to analyze results and suggest corrective actions.

### Orchestration

`orchestrator_final.py` coordinates the four agents and records
task handoffs and approved AWS tool execution.

The default mode verifies the existing deployment.
The `--apply` option requests approval before synchronizing
website files to the existing S3 bucket.

### Setup

Requirements:
- Python 3.10+
- OpenAI API key
- AWS CLI v2 with an authenticated AWS profile named `csce412`

Install dependencies:

    python -m pip install -r requirements.txt

Copy `.env.example` to `.env` and configure your API key.

Run the integrated workflow:

    python orchestrator_final.py

Run the approved S3 synchronization workflow:

    python orchestrator_final.py --apply

### Initial AWS Deployment

The initial S3 and CloudFront resources were created using the
scripts in `deploy/`. Domain registration and initial DNS/certificate
configuration included documented manual AWS/Namecheap steps.

The integrated orchestrator handles existing-resource checks and
approved website synchronization; it does not recreate the entire
AWS infrastructure from scratch.

### Verification

Run:

    python agents/verification_agent.py --domain csce412rahul021005.me

The agent checks 15 conditions including HTTPS, redirects,
certificate matching, CloudFront, S3 privacy, and page availability.

### Controlled Failure and Recovery

The CloudFront viewer protocol policy was temporarily changed from
`redirect-to-https` to `https-only`.

The verification agent detected the HTTP redirect failure.
The original policy was restored and all 15 checks passed again.

Evidence is retained in the `evidence/` directory.

### Security and AI Usage

OpenAI API calls assist with requirements, content generation,
deployment planning, and diagnosis.

AWS operations require explicit approval where changes are made.
Secrets, virtual environments, and raw runtime state are excluded
from GitHub.

### Project Evidence

See `evidence/` for selected agent communication, tool execution,
deployment, verification, and recovery records.
