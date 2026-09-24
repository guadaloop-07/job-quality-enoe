#!/usr/bin/env python3
"""Render an aggregate-only descriptive ENOE profile baseline as Markdown."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

if __package__:
    from scripts.enoe_profile import CORE_PERIODS, profile_report
else:
    from enoe_profile import CORE_PERIODS, profile_report

BASELINE_CLASSIFIERS = (
    "position_in_occupation",
    "employment_formality",
    "informal_sector",
    "activity_branch",
    "occupation_group",
    "income_band",
    "working_time_duration",
    "unit_size",
    "written_contract",
    "contract_type",
    "employment_health_access",
    "non_health_benefits",
)


class BaselineError(ValueError):
    """Raised when aggregate profile evidence cannot support the baseline."""


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise BaselineError(f"baseline estimate has invalid {field}") from error


def _markdown(value: object) -> str:
    """Keep source category codes safe inside a Markdown table cell."""
    return str(value).replace("|", "\\|")


def _leading_estimate(estimates: Sequence[dict[str, object]]) -> dict[str, object]:
    visible = [estimate for estimate in estimates if estimate.get("suppressed") is False]
    if not visible:
        raise BaselineError("baseline has no disclosure-eligible estimate for a classifier period")
    return max(
        visible, key=lambda estimate: _decimal(estimate.get("weighted_share"), "weighted_share")
    )


def baseline_payload(profile: dict[str, object]) -> dict[str, object]:
    """Build a complete quarterly leading-category timeline from profile evidence."""
    if profile.get("profile_inputs_validated") is not True:
        raise BaselineError("weighted profile inputs were not validated")
    if tuple(profile.get("core_periods", ())) != CORE_PERIODS:
        raise BaselineError("baseline requires the complete 2023Q1--2025Q4 core window")

    estimates = profile.get("estimates")
    if not isinstance(estimates, list) or not all(
        isinstance(estimate, dict) for estimate in estimates
    ):
        raise BaselineError("weighted profile estimates have an invalid structure")

    indexed: dict[tuple[str, str], list[dict[str, object]]] = {}
    available_classifiers = set()
    for estimate in estimates:
        period = str(estimate.get("period", ""))
        classifier = str(estimate.get("classifier", ""))
        if period not in CORE_PERIODS:
            raise BaselineError("baseline received an estimate outside the core window")
        indexed.setdefault((period, classifier), []).append(estimate)
        available_classifiers.add(classifier)
    if available_classifiers != set(BASELINE_CLASSIFIERS):
        raise BaselineError("baseline classifier set differs from the approved protocol")

    timelines = []
    for classifier in BASELINE_CLASSIFIERS:
        cells = []
        for period in CORE_PERIODS:
            leading = _leading_estimate(indexed.get((period, classifier), []))
            cells.append(
                {
                    "period": period,
                    "category_code": str(leading["category_code"]),
                    "category_state": str(leading["category_state"]),
                    "weighted_share": _decimal(leading["weighted_share"], "weighted_share"),
                }
            )
        timelines.append({"classifier": classifier, "cells": cells})

    return {
        "source": profile.get("source"),
        "unit_of_analysis": profile.get("unit_of_analysis"),
        "domain": profile.get("domain"),
        "weight_rule": profile.get("weight_rule"),
        "core_periods": list(CORE_PERIODS),
        "timelines": timelines,
    }


def _share(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(baseline: dict[str, object]) -> str:
    """Render a reader-facing report without exposing suppressed cells or microdata."""
    timelines = baseline.get("timelines")
    if not isinstance(timelines, list):
        raise BaselineError("baseline timelines have an invalid structure")
    periods = baseline["core_periods"]
    if not isinstance(periods, list):
        raise BaselineError("baseline periods have an invalid structure")

    lines = [
        "# Jalisco employment-condition descriptive baseline",
        "",
        "## Executive summary",
        "",
        "- This baseline presents each survey quarter separately; it does not pool person-quarters "
        "into a multi-quarter population estimate.",
        "- Employment formality and informal sector remain distinct classifiers throughout the report.",
        "- Each timeline cell shows the largest disclosure-eligible weighted category in its "
        "quarter. Suppressed cells never contribute a share to this report.",
        "",
        "## Quarterly leading categories",
        "",
        "| Classifier | " + " | ".join(periods) + " |",
        "| --- | " + " | ".join("---" for _ in periods) + " |",
    ]
    for timeline in timelines:
        classifier = _markdown(timeline["classifier"])
        cells = timeline["cells"]
        if not isinstance(cells, list) or len(cells) != len(periods):
            raise BaselineError("baseline timeline is incomplete")
        values = [
            f"{_markdown(cell['category_code'])} ({_share(cell['weighted_share'])})"
            for cell in cells
        ]
        lines.append("| " + classifier + " | " + " | ".join(values) + " |")

    lines.extend(
        [
            "",
            "## Scope and interpretation",
            "",
            f"- Source: {baseline['source']}.",
            f"- Unit of analysis: {baseline['unit_of_analysis']}.",
            f"- Domain: {baseline['domain']}.",
            f"- Weight rule: {baseline['weight_rule']}.",
            "- The category codes follow the approved weighted official-classifier protocol. "
            "They are descriptive classifications, not latent profiles, a job-quality score, "
            "or official INEGI categories.",
            "- This report does not establish municipal representativeness or make causal claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(render_markdown(baseline_payload(profile_report())), end="")


if __name__ == "__main__":
    main()
