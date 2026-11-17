"""Tests for rule-based NLP parser, clarification prompts, and security refusals."""

from shellsense.models import Intent
from shellsense.nlp.rule_based import RuleBasedParser
from shellsense.nlp.schemas import Clarification, Refusal


def test_system_info_parsing() -> None:
    parser = RuleBasedParser()
    res = parser.parse("Show my RAM usage")
    assert isinstance(res, Intent)
    assert res.operation == "SHOW_MEMORY"
    assert res.confidence >= 0.9

    res_cpu = parser.parse("Show CPU usage")
    assert isinstance(res_cpu, Intent)
    assert res_cpu.operation == "SHOW_CPU"


def test_blocked_and_sudo_refusal() -> None:
    parser = RuleBasedParser()
    res = parser.parse("sudo rm -rf /")
    assert isinstance(res, Refusal)
    assert "forbidden" in res.reason.lower()

    res_bash = parser.parse("bash -c 'whoami'")
    assert isinstance(res_bash, Refusal)


def test_clarification_on_ambiguous_empty() -> None:
    parser = RuleBasedParser()
    res = parser.parse("")
    assert isinstance(res, Clarification)
    assert len(res.options) > 0


def test_process_termination_parsing() -> None:
    parser = RuleBasedParser()
    res = parser.parse("kill process 1234")
    assert isinstance(res, Intent)
    assert res.operation == "TERMINATE_PROCESS"
    assert res.params["pids"] == [1234]
