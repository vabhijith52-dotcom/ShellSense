"""Test suite for golden commands and NLP parser accuracy."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from shellsense.models import Intent
from shellsense.nlp.rule_based import DEFAULT_PARSER
from shellsense.nlp.schemas import Clarification, Refusal

GOLDEN_YAML_PATH = Path(__file__).parent / "nlp" / "golden_commands.yaml"


def load_golden_data() -> dict[str, Any]:
    with open(GOLDEN_YAML_PATH, encoding="utf-8") as f:
        res: dict[str, Any] = yaml.safe_load(f)
        return res


def test_every_intent_has_at_least_15_phrases() -> None:
    data = load_golden_data()
    intents = data.get("intents", {})
    assert len(intents) >= 40, f"Expected at least 40 registered intents, got {len(intents)}"

    for intent_name, phrases in intents.items():
        assert len(phrases) >= 15, (
            f"Intent '{intent_name}' has only {len(phrases)} phrases in golden dataset; minimum required is 15."
        )


def test_refusals_in_golden_data() -> None:
    data = load_golden_data()
    refusals = data.get("refusals", [])
    assert len(refusals) >= 15
    for phrase in refusals:
        res = DEFAULT_PARSER.parse(phrase)
        assert isinstance(res, Refusal), f"Phrase '{phrase}' should produce Refusal, got {type(res)}: {res}"


def test_clarifications_in_golden_data() -> None:
    data = load_golden_data()
    clarifications = data.get("clarifications", [])
    assert len(clarifications) >= 5
    for phrase in clarifications:
        res = DEFAULT_PARSER.parse(phrase)
        assert isinstance(res, Clarification), f"Phrase '{phrase}' should produce Clarification, got {type(res)}: {res}"


def test_parser_accuracy_on_golden_dataset() -> None:
    data = load_golden_data()
    intents = data.get("intents", {})
    total = 0
    passed = 0
    failures = []

    for expected_intent, phrases in intents.items():
        for phrase in phrases:
            total += 1
            res = DEFAULT_PARSER.parse(phrase)
            if isinstance(res, Intent) and res.operation == expected_intent:
                passed += 1
            else:
                failures.append((expected_intent, phrase, getattr(res, "operation", type(res).__name__)))

    accuracy = (passed / total) * 100 if total > 0 else 0
    print(f"\nParser Golden Dataset Accuracy: {passed}/{total} ({accuracy:.1f}%)")
    # Tier 1 requirement: at least 95%
    if failures:
        sample_failures = failures[:10]
        print(f"Sample failures: {sample_failures}")
    assert accuracy >= 95.0, f"Accuracy {accuracy:.1f}% is below required 95.0% threshold"
