# CSCE 412 Project 6: Step 1 Starter

These files extend the **existing** CSCE412-Project5 repository. They do not contain or replace the website. All commands are run from your existing repository root in PowerShell.

1. First create/switch to the `project6` Git branch, with a clean Git working tree.
2. Copy the contents of this ZIP **into the repository root**, so the new `tests/`, `scripts/`, and `buildspec-test.yml` appear alongside `website/` and `orchestrator_final.py`.
3. Activate the previous Python environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip install pytest
   ```
4. Create a release manifest and run tests:
   ```powershell
   python .\scripts\make_release.py
   python -m pytest -q .\tests --junitxml=reports\website-tests.xml
   ```
5. If tests fail, **do not** deploy; first inspect exact failure messages. Some checks may need adaptation to actual Project 5 generated HTML; avoid weakening the requirement merely to pass.
6. Add these generated file patterns to your existing `.gitignore` (without overwriting its other contents): `website/release.json`, `reports/`, `__pycache__/`, `.pytest_cache/`. The pipeline generates `release.json` from the actual commit at build time; do not commit this derived file.
7. Check which files will be committed:
   ```powershell
   git status --short
   git diff --check
   ```
8. Once tests pass, add only implementation files (not `.env`, API keys, virtualenv, local logs):
   ```powershell
   git add tests scripts/make_release.py buildspec-test.yml README-STEP1.md
   git commit -m "Project 6: add pre-deployment validation and release IDs"
   ```

`buildspec-test.yml` is ready to use later in an AWS CodeBuild test action. CodeBuild will use its GitHub source commit as the release ID, then run the same pytest suite and produce JUnit XML test reports.

## Limitations

- No AWS resources are modified by this starter.
- Not yet a complete pipeline: deployment, caching, live verification, rollback, and agent diagnosis come in subsequent steps.
- The test suite assumes the documented five-page Project 5 HTML structure and `website/assets/site.js`; inspect failures to adapt if needed.
- The pre-deploy tests validate local artifacts, but a production verification stage must independently check the real HTTPS domain.
