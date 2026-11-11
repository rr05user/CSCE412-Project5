# Your First Cloud Requirements AI Agent

## Prerequisites
Python 3.10+, an OpenAI API key, and a terminal. This tutorial does not require AWS credentials.

## Setup
```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # On Windows, copy .env.example .env
```
Edit `.env` to supply `OPENAI_API_KEY`. Never commit `.env` to Git.

## Run
```bash
python agent.py
```
The program asks an LLM to analyze cloud requirements, validates its structured response, and invokes the local `save_analysis` tool to write `outputs/requirements.json`.

## Exercises
1. Change the request and compare results.
2. Add a new output field and validate it.
3. Add a tool to validate the allowed AWS service names.
4. Explain why saving a file is a tool action, but does not itself demonstrate autonomous model-selected tool calling.
5. Extend the program to let the LLM choose between at least two approved local tools.

## Security
Never print or commit secrets. Do not let LLM-generated text execute as a shell command without review. No AWS privileges are required for this tutorial.
