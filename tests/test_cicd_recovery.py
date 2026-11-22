"""Tests for Project 6 CI/CD recovery agent."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "agents" / "cicd_recovery_agent.py"

spec = importlib.util.spec_from_file_location("recovery_agent", AGENT_PATH)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def test_successful_verification():
    result = {
        "passed": True,
        "exit_code": 0,
        "stdout": "Production verification passed",
        "stderr": ""
    }

    analysis = agent.diagnose(result)

    assert analysis["likely_causes"] == []
    assert analysis["proposed_actions"] == []


def test_failed_verification_fallback():
    result = {
        "passed": False,
        "exit_code": 1,
        "stdout": "Release mismatch",
        "stderr": "Verification failed"
    }

    with patch.dict("sys.modules", {"openai": None}):
        analysis = agent.diagnose(result)

    assert isinstance(analysis["summary"], str)
    assert isinstance(analysis["proposed_actions"], list)
    assert len(analysis["proposed_actions"]) > 0


def test_recovery_agent_has_approval_gate():
    source = AGENT_PATH.read_text(encoding="utf-8")

    assert "rollback_executed" in source
    assert "approval_required" in source
    assert "CONFIRM_ROLLBACK" in source
    assert "--execute-rollback" in source
