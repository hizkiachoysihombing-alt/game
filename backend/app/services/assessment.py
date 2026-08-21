"""Deterministic grading for engineering answers."""

from dataclasses import dataclass
import math
import re

from app.models.models import Question, QuestionType


UNIT_FACTORS = {
    "a": ("current", 1.0), "ma": ("current", 1e-3), "ua": ("current", 1e-6),
    "v": ("voltage", 1.0), "mv": ("voltage", 1e-3), "kv": ("voltage", 1e3),
    "ohm": ("resistance", 1.0), "ω": ("resistance", 1.0), "kohm": ("resistance", 1e3),
    "w": ("power", 1.0), "kw": ("power", 1e3), "mw": ("power", 1e6),
    "hz": ("frequency", 1.0), "khz": ("frequency", 1e3), "mhz": ("frequency", 1e6),
    "s": ("time", 1.0), "ms": ("time", 1e-3), "us": ("time", 1e-6),
}


@dataclass(frozen=True)
class GradeResult:
    is_correct: bool
    score: float
    normalized_value: float | None
    normalized_unit: str | None
    feedback: str
    error_code: str | None = None


def _parse_numeric(raw: object) -> tuple[float, str | None]:
    if isinstance(raw, dict):
        value, unit = raw.get("value"), raw.get("unit")
        return float(value), str(unit).strip() if unit else None
    if isinstance(raw, (int, float)):
        return float(raw), None
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([^\d\s]+)?\s*", str(raw))
    if not match:
        raise ValueError("Enter a numeric value, optionally followed by a unit (for example: 500 mA).")
    return float(match.group(1)), match.group(2)


def _canonical(value: float, unit: str | None) -> tuple[float, str | None, str | None]:
    if not unit:
        return value, None, None
    key = unit.lower().replace("µ", "u").replace("Ω", "ω")
    item = UNIT_FACTORS.get(key)
    if item is None:
        return value, key, None
    dimension, factor = item
    return value * factor, key, dimension


def grade_question(question: Question, answer: object) -> GradeResult:
    if question.coding_language:
        source = answer.get("code", "") if isinstance(answer, dict) else str(answer or "")
        source_normalized = re.sub(r"\s+", " ", source.strip()).lower()
        tests = question.test_cases or []
        if not source.strip():
            return GradeResult(False, 0.0, None, None, "Write a solution before running the tests.", "EMPTY_CODE")
        passed = 0
        failed_names = []
        for test in tests:
            required = [str(item).lower() for item in test.get("required", [])]
            forbidden = [str(item).lower() for item in test.get("forbidden", [])]
            ok = all(item in source_normalized for item in required) and not any(item in source_normalized for item in forbidden)
            if ok:
                passed += 1
            else:
                failed_names.append(test.get("name", "Code requirement"))
        total = max(1, len(tests))
        score = 100.0 * passed / total
        correct = bool(tests) and passed == len(tests)
        feedback = f"{passed}/{len(tests)} checks passed." if correct else f"{passed}/{len(tests)} checks passed. Review: {', '.join(failed_names[:3])}."
        return GradeResult(correct, score, None, question.coding_language, feedback, None if correct else "CODE_TEST_FAILED")
    if question.question_type not in (QuestionType.NUMERICAL, QuestionType.CALCULATION):
        expected = str(question.expected_answer or "").strip().lower()
        actual = str(answer or "").strip().lower()
        correct = bool(expected) and actual == expected
        return GradeResult(correct, 100.0 if correct else 0.0, None, None, "Correct." if correct else "Review the lesson and try again.", None if correct else "CONCEPTUAL_MISUNDERSTANDING")

    try:
        actual_value, actual_unit = _parse_numeric(answer)
        expected_value, expected_unit = _parse_numeric(question.expected_answer)
    except (TypeError, ValueError) as exc:
        return GradeResult(False, 0.0, None, None, str(exc), "ARITHMETIC_ERROR")

    accepted = [str(unit) for unit in (question.accepted_units or [])]
    if expected_unit is None and accepted:
        expected_unit = accepted[0]
    actual_base, actual_key, actual_dimension = _canonical(actual_value, actual_unit or expected_unit)
    expected_base, expected_key, expected_dimension = _canonical(expected_value, expected_unit)
    if actual_unit and accepted:
        accepted_dimensions = {_canonical(1, unit)[2] for unit in accepted}
        if actual_dimension not in accepted_dimensions:
            return GradeResult(False, 0.0, actual_base, actual_key, f"Unit '{actual_unit}' is not compatible with the expected quantity.", "UNIT_CONVERSION_ERROR")
    tolerance = question.numerical_tolerance if question.numerical_tolerance is not None else max(abs(expected_base) * 1e-3, 1e-9)
    correct = math.isclose(actual_base, expected_base, rel_tol=1e-6, abs_tol=tolerance)
    feedback = "Correct. Equivalent engineering units are accepted." if correct else f"Your normalized value is {actual_base:g}; review the calculation and unit conversion."
    return GradeResult(correct, 100.0 if correct else 0.0, actual_base, actual_key or expected_key, feedback, None if correct else "ARITHMETIC_ERROR")
