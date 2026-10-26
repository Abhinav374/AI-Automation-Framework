"""FastMCP server exposing VWO test-case discovery and authoring tools."""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError

from tc_mcp.repository import (
    BROWSERS,
    CSV_FIELDS,
    DEVICES,
    EXPORT_PATH,
    OVERLAY_PATH,
    PRIORITIES,
    PRIORITY_WEIGHT,
    STATUS_WEIGHT,
    STATUSES,
    TEST_TYPES,
    TYPE_WEIGHT,
    TestCaseDraft,
    TestFilter,
    TestRepository,
    compact,
    counts,
    full,
    grouped,
    response,
)

mcp = FastMCP("VWO Test Creator")
repository = TestRepository()
WRITES_ENABLED = os.environ.get("TC_MCP_ALLOW_WRITES", "").strip().lower() in {"1", "true", "yes"}


def _score(row: dict[str, Any]) -> int:
    return PRIORITY_WEIGHT.get(row["priority"], 0) + STATUS_WEIGHT.get(row["status"], 0) + TYPE_WEIGHT.get(row["test_type"], 0)


def _rank_key(row: dict[str, Any]) -> tuple[int, str]:
    return (-_score(row), row["key"])


def _rank_reason(row: dict[str, Any]) -> str:
    return f'{row["priority"]} · {row["status"]} · {row["test_type"]} · selected for feature {row["feature"]!r}'


def _round_robin(rows: list[dict[str, Any]], limit: int, per_feature: int = 1) -> list[dict[str, Any]]:
    features = grouped(rows, "feature")
    for feature_rows in features.values():
        feature_rows.sort(key=_rank_key)
    selected = []
    round_number = 0
    while len(selected) < limit:
        added = False
        for feature_rows in features.values():
            if round_number < min(per_feature, len(feature_rows)) and len(selected) < limit:
                selected.append(feature_rows[round_number])
                added = True
        if not added:
            break
        round_number += 1
    return selected


def _as_steps(row: dict[str, Any]) -> list[str]:
    steps = row.get("Steps", [])
    if isinstance(steps, list):
        return steps
    return [step.strip() for step in str(steps).split("|") if step.strip()]


def _step_text(step: str) -> str:
    return re.sub(r"^\d+\.\s*", "", step)


def _with_ranking(row: dict[str, Any], rank: int) -> dict[str, Any]:
    return {**compact(row), "rank": rank, "score": _score(row), "rank_reason": _rank_reason(row)}


def _selected_rows(issue_keys: list[str] | None, filters: TestFilter | None = None) -> list[dict[str, Any]]:
    if issue_keys:
        unknown = [key for key in issue_keys if key not in repository.by_key]
        if unknown:
            raise ValueError(f"Unknown issue key(s): {', '.join(unknown)}")
        return [repository.by_key[key] for key in issue_keys]
    return repository.apply_filters(filters)


def _validate_draft(draft: TestCaseDraft) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field, value in [
        ("summary", draft.summary),
        ("description", draft.description),
        ("feature", draft.feature),
        ("preconditions", draft.preconditions),
        ("expected_result", draft.expected_result),
    ]:
        if not value.strip():
            errors.append(f"{field} cannot be blank.")
    if draft.priority not in PRIORITIES:
        errors.append(f"priority must be one of {PRIORITIES}")
    if draft.module not in repository.modules:
        errors.append(f"module must be one of {repository.modules}")
    if draft.test_type not in TEST_TYPES:
        errors.append(f"test_type must be one of {TEST_TYPES}")
    if draft.browser not in BROWSERS:
        errors.append(f"browser must be one of {BROWSERS}")
    if draft.device not in DEVICES:
        errors.append(f"device must be one of {DEVICES}")
    if draft.status not in STATUSES:
        errors.append(f"status must be one of {STATUSES}")
    expected_prefix = f"[{draft.module}] {draft.test_type}:"
    if not draft.summary.startswith(expected_prefix):
        errors.append(f"summary must start with {expected_prefix!r}")
    if len(draft.steps) < 3:
        warnings.append("Fewer than 3 steps may not provide enough detail.")
    if re.search(r"\b(works as specified|works correctly|successfully)\b", draft.expected_result, re.I):
        warnings.append("Expected result is generic; describe an observable outcome.")
    if any(not step.strip() for step in draft.steps):
        errors.append("steps cannot contain blank entries.")
    duplicates = [
        row["key"] for row in repository.rows
        if row["Summary"].casefold() == draft.summary.casefold()
        and row["module"] == draft.module
    ][:5]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "possible_duplicates": duplicates}


def _validate_filter_values(filters: TestFilter) -> None:
    for field, allowed, values in [
        ("priority", PRIORITIES, filters.priority or []),
        ("test_type", TEST_TYPES, filters.test_type or []),
        ("status", STATUSES, filters.status or []),
    ]:
        invalid = [value for value in values if value not in allowed]
        if invalid:
            raise ValueError(f"Invalid {field} value(s): {invalid}. Valid values: {allowed}")
    if filters.browser and filters.browser not in BROWSERS:
        raise ValueError(f"Invalid browser {filters.browser!r}. Valid values: {BROWSERS}")
    if filters.device and filters.device not in DEVICES:
        raise ValueError(f"Invalid device {filters.device!r}. Valid values: {DEVICES}")


@mcp.tool(tags={"discovery"}, annotations={"readOnlyHint": True})
def list_modules(include_features: bool = True) -> list[dict[str, Any]]:
    """Use to discover available VWO modules and test counts; use get_filter_options for valid filter values."""
    result = []
    for module, rows in sorted(grouped(repository.rows, "module").items()):
        live = [row for row in rows if row["status"] != "Deprecated"]
        item: dict[str, Any] = {
            "module": module,
            "total": len(rows),
            "live": len(live),
            "by_priority": counts(live, "priority"),
        }
        if include_features:
            item["features"] = sorted({row["feature"] for row in rows})
        result.append(item)
    return result


@mcp.tool(tags={"discovery"}, annotations={"readOnlyHint": True})
def get_filter_options() -> dict[str, Any]:
    """Use to learn accepted module, priority, test type, browser, device and status values; use list_modules for counts."""
    return {
        "priorities": PRIORITIES,
        "test_types": TEST_TYPES,
        "browsers": BROWSERS,
        "devices": DEVICES,
        "statuses": STATUSES,
        "modules": repository.modules,
        "aliases": {"A/B Testing": ["ab testing", "ab-test"], "SDK / Server-Side API": ["sdk", "server-side api"]},
        "priority_order": PRIORITIES,
    }


@mcp.tool(tags={"discovery"}, annotations={"readOnlyHint": True})
def get_test_stats(group_by: list[str], filters: TestFilter | None = None) -> dict[str, Any]:
    """Use for grouped test counts and coverage questions; use list_modules for module feature lists."""
    aliases = {
        "module": "module", "priority": "priority", "test_type": "test_type",
        "status": "status", "browser": "browser", "device": "device", "feature": "feature",
    }
    if not 1 <= len(group_by) <= 2 or any(item not in aliases for item in group_by):
        raise ValueError(f"group_by must contain one or two of {list(aliases)}")
    _validate_filter_values(filters or TestFilter())
    rows = repository.apply_filters(filters)
    first = aliases[group_by[0]]
    if len(group_by) == 1:
        return {"total": len(rows), "group_by": group_by, "counts": counts(rows, first)}
    second = aliases[group_by[1]]
    table: dict[str, dict[str, int]] = {}
    for first_value, first_rows in sorted(grouped(rows, first).items()):
        table[first_value] = counts(first_rows, second)
    return {"total": len(rows), "group_by": group_by, "pivot": table}


@mcp.tool(tags={"search"}, annotations={"readOnlyHint": True})
def get_test_case(issue_keys: list[str]) -> dict[str, Any]:
    """Use to fetch one to 25 cases by exact VWO key; use search_test_cases to find keys from filters."""
    if not 1 <= len(issue_keys) <= 25:
        raise ValueError("Provide between 1 and 25 issue keys.")
    found = [full(repository.by_key[key]) for key in issue_keys if key in repository.by_key]
    missing = [key for key in issue_keys if key not in repository.by_key]
    return {"results": found, "unknown_keys": missing}


@mcp.tool(tags={"search"}, annotations={"readOnlyHint": True})
def search_test_cases(
    filters: TestFilter | None = None,
    sort_by: str = "priority",
    limit: int = 20,
    offset: int = 0,
    detail: str = "compact",
) -> dict[str, Any]:
    """Use for filtered test cases by module, priority, min/max priority or other fields; use get_top_tests_for_module for execution ranking."""
    if sort_by not in {"priority", "key"}:
        raise ValueError("sort_by must be 'priority' or 'key'.")
    if detail not in {"compact", "full"}:
        raise ValueError("detail must be 'compact' or 'full'.")
    if offset < 0:
        raise ValueError("offset cannot be negative.")
    active_filters = filters or TestFilter()
    _validate_filter_values(active_filters)
    rows = repository.apply_filters(active_filters)
    if sort_by == "priority":
        rows.sort(key=lambda row: (-PRIORITY_WEIGHT[row["priority"]], row["key"]))
    else:
        rows.sort(key=lambda row: row["key"])
    return response(rows, limit, offset, active_filters, detail)


@mcp.tool(tags={"search"}, annotations={"readOnlyHint": True})
def search_by_keyword(query: str, module: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Use for words or phrases such as SSO or rate limiting; use search_test_cases for exact structured filters."""
    terms = [term for term in re.findall(r"[a-z0-9]+", query.casefold()) if term]
    if not terms:
        raise ValueError("query must contain at least one searchable word.")
    module_filter = TestFilter(module=module) if module else TestFilter()
    rows = repository.apply_filters(module_filter)
    ranked = []
    for row in rows:
        fields = {
            "summary": row["Summary"], "description": row["Description"],
            "steps": " ".join(_as_steps(row)), "expected_result": row["Expected Result"],
            "feature": row["feature"], "labels": " ".join(row["labels"]),
        }
        matches = [(field, sum(value.casefold().count(term) for term in terms)) for field, value in fields.items()]
        score = sum(count for _, count in matches)
        if score:
            best_field = max(matches, key=lambda item: item[1])[0]
            ranked.append((score, best_field, row))
    ranked.sort(key=lambda item: (-item[0], *_rank_key(item[2])))
    bounded_limit = min(max(limit, 1), 100)
    result = [
        {**compact(row), "match_field": field, "match_score": score}
        for score, field, row in ranked[:bounded_limit]
    ]
    return {"total_matched": len(ranked), "returned": len(result), "results": result}


@mcp.tool(tags={"search", "planning"}, annotations={"readOnlyHint": True})
def get_top_tests_for_module(
    module: str,
    count: int = 10,
    test_types: list[str] | None = None,
    browser: str | None = None,
    device: str | None = None,
    unique_scenarios: bool = True,
) -> dict[str, Any]:
    """Use to choose the highest-value tests to run first for one module; use search_test_cases for unranked filtering."""
    if not 1 <= count <= 50:
        raise ValueError("count must be between 1 and 50.")
    if test_types and any(test_type not in TEST_TYPES for test_type in test_types):
        raise ValueError(f"test_types must be selected from {TEST_TYPES}")
    selected_module = repository.resolve_module(module)
    filters = TestFilter(module=selected_module, test_type=test_types, browser=browser, device=device)
    _validate_filter_values(filters)
    rows = repository.apply_filters(filters)
    rows = [row for row in rows if row["status"] != "Deprecated"]
    rows.sort(key=_rank_key)
    if unique_scenarios:
        best_by_scenario = {}
        for row in rows:
            best_by_scenario.setdefault(row["Summary"], row)
        rows = list(best_by_scenario.values())
        rows = _round_robin(rows, count, per_feature=999)
    else:
        rows = rows[:count]
    return {
        "module": selected_module,
        "total_candidates": len(repository.apply_filters(filters)),
        "returned": len(rows),
        "results": [_with_ranking(row, index) for index, row in enumerate(rows, 1)],
    }


@mcp.tool(tags={"search"}, annotations={"readOnlyHint": True})
def get_similar_test_cases(issue_key: str, limit: int = 10) -> dict[str, Any]:
    """Use to find related variants for review or examples; use search_by_keyword when no reference case is known."""
    if issue_key not in repository.by_key:
        raise ValueError(f"Unknown issue key {issue_key!r}.")
    source = repository.by_key[issue_key]
    candidates = [
        row for row in repository.rows
        if row["key"] != issue_key and row["module"] == source["module"] and row["feature"] == source["feature"]
    ]
    candidates.sort(key=lambda row: (
        row["test_type"] == source["test_type"],
        row["browser"] == source["browser"] and row["device"] == source["device"],
        *_rank_key(row),
    ))
    bounded_limit = min(max(limit, 1), 50)
    results = []
    for row in candidates[:bounded_limit]:
        differences = [
            field for field in ("test_type", "browser", "device", "priority", "status")
            if row[field] != source[field]
        ]
        results.append({**compact(row), "differs_from_source": differences})
    return {"source_key": issue_key, "total_matched": len(candidates), "results": results}


@mcp.tool(tags={"planning"}, annotations={"readOnlyHint": True})
def build_test_suite(
    suite_type: str,
    modules: list[str] | str = "all",
    min_tests: int = 0,
    max_tests: int = 50,
    browsers: list[str] | None = None,
    devices: list[str] | None = None,
    include_drafts: bool = False,
) -> dict[str, Any]:
    """Use to assemble smoke, sanity or regression runs with limits; use get_top_tests_for_module for one-module ranking."""
    if suite_type not in {"smoke", "sanity", "regression"}:
        raise ValueError("suite_type must be smoke, sanity or regression.")
    if min_tests < 0 or max_tests < 1 or max_tests > 100 or min_tests > max_tests:
        raise ValueError("Require 0 <= min_tests <= max_tests <= 100.")
    selected = repository.modules if modules == "all" else ([modules] if isinstance(modules, str) else modules)
    resolved = [repository.resolve_module(module) for module in selected]
    if browsers and any(browser not in BROWSERS for browser in browsers):
        raise ValueError(f"browsers must be selected from {BROWSERS}")
    if devices and any(device not in DEVICES for device in devices):
        raise ValueError(f"devices must be selected from {DEVICES}")
    rows = [row for row in repository.rows if row["module"] in resolved]
    rows = [row for row in rows if row["status"] != "Deprecated" and (include_drafts or row["status"] != "Draft")]
    if browsers:
        rows = [row for row in rows if row["browser"] in browsers]
    if devices:
        rows = [row for row in rows if row["device"] in devices]
    if suite_type == "smoke":
        eligible = [row for row in rows if row["priority"] == "Highest" and row["test_type"] in {"Functional", "API", "Security"}]
        per_feature = 1
    elif suite_type == "sanity":
        eligible = [row for row in rows if row["priority"] in {"Highest", "High"} and row["test_type"] in {"Functional", "Negative", "API"}]
        per_feature = 2
    else:
        eligible, per_feature = rows, len(rows)
    relaxed = []
    if len(eligible) < min_tests and suite_type in {"smoke", "sanity"}:
        excluded = [row for row in rows if row not in eligible]
        excluded.sort(key=_rank_key)
        eligible.extend(excluded[:max(0, min_tests - len(eligible))])
        relaxed.append("Added lower-priority or other-type tests to meet min_tests.")
    eligible.sort(key=_rank_key)
    spread = _round_robin(eligible, max_tests, per_feature=per_feature)
    if suite_type == "smoke":
        spread.sort(key=lambda row: (
            row["device"] != "desktop", row["browser"] != "Chrome 148",
            -_score(row), row["key"],
        ))
    by_module = Counter(row["module"] for row in spread)
    by_type = Counter(row["test_type"] for row in spread)
    by_priority = Counter(row["priority"] for row in spread)
    return {
        "suite_type": suite_type,
        "requested_modules": resolved,
        "total_candidates": len(eligible),
        "returned": len(spread),
        "min_tests_met": len(spread) >= min_tests,
        "relaxations": relaxed,
        "estimated_minutes_manual": len(spread) * 10,
        "makeup": {"by_module": dict(by_module), "by_test_type": dict(by_type), "by_priority": dict(by_priority)},
        "results": [_with_ranking(row, index) for index, row in enumerate(spread, 1)],
    }


@mcp.tool(tags={"planning", "quality"}, annotations={"readOnlyHint": True})
def get_browser_device_matrix(module: str | None = None, feature: str | None = None) -> dict[str, Any]:
    """Use to check browser/device coverage holes; use find_coverage_gaps for feature-by-test-type coverage."""
    filters = TestFilter(module=module, feature=feature)
    rows = repository.apply_filters(filters)
    matrix = {
        browser: {
            device: sum(row["browser"] == browser and row["device"] == device for row in rows)
            for device in DEVICES
        }
        for browser in BROWSERS
    }
    gaps = [{"browser": browser, "device": device} for browser in BROWSERS for device in DEVICES if matrix[browser][device] == 0]
    return {"total": len(rows), "browsers": BROWSERS, "devices": DEVICES, "matrix": matrix, "empty_cells": gaps}


@mcp.tool(tags={"planning"}, annotations={"readOnlyHint": True})
def get_automation_candidates(module: str | None = None, min_priority: str = "High", limit: int = 20) -> dict[str, Any]:
    """Use to prioritize manual tests for automation; use get_top_tests_for_module for immediate run order."""
    if min_priority not in PRIORITIES:
        raise ValueError(f"min_priority must be one of {PRIORITIES}")
    filters = TestFilter(module=module, min_priority=min_priority, status=["Ready"])
    rows = repository.apply_filters(filters)
    rows.sort(key=lambda row: (-(_score(row) + (3 if row["test_type"] in {"Functional", "API", "Regression"} else 0)), row["key"]))
    page = rows[:min(max(limit, 1), 100)]
    return {
        "total_matched": len(rows),
        "results": [
            {**compact(row), "automation_reason": f'{row["priority"]} priority {row["test_type"]} test with reusable structured steps.'}
            for row in page
        ],
    }


@mcp.tool(tags={"planning"}, annotations={"readOnlyHint": True})
def estimate_execution_effort(
    issue_keys: list[str] | None = None,
    filters: TestFilter | None = None,
    minutes_manual: int = 10,
    minutes_automated: int = 1,
) -> dict[str, Any]:
    """Use to estimate execution time for selected test cases; use build_test_suite when a run still needs to be assembled."""
    if issue_keys and filters and filters.model_dump(exclude_defaults=True, exclude_none=True):
        raise ValueError("Provide issue_keys or filters, not both.")
    if minutes_manual < 0 or minutes_automated < 0:
        raise ValueError("Execution minutes cannot be negative.")
    rows = _selected_rows(issue_keys, filters)
    manual = [row for row in rows if row["status"] != "Automated"]
    automated = [row for row in rows if row["status"] == "Automated"]
    modules = defaultdict(lambda: {"manual": 0, "automated": 0, "total_minutes": 0})
    for row in manual:
        modules[row["module"]]["manual"] += 1
        modules[row["module"]]["total_minutes"] += minutes_manual
    for row in automated:
        modules[row["module"]]["automated"] += 1
        modules[row["module"]]["total_minutes"] += minutes_automated
    return {
        "total_cases": len(rows),
        "manual_cases": len(manual),
        "automated_cases": len(automated),
        "manual_minutes": len(manual) * minutes_manual,
        "automated_minutes": len(automated) * minutes_automated,
        "total_minutes": len(manual) * minutes_manual + len(automated) * minutes_automated,
        "by_module": dict(sorted(modules.items())),
    }


@mcp.tool(tags={"quality"}, annotations={"readOnlyHint": True})
def find_duplicate_tests(module: str | None = None, mode: str = "exact", limit: int = 100) -> dict[str, Any]:
    """Use to find repeated scenarios and recommend a keeper; use get_similar_test_cases for useful, nonduplicate variants."""
    if mode not in {"exact", "same_scenario"}:
        raise ValueError("mode must be 'exact' or 'same_scenario'.")
    rows = repository.apply_filters(TestFilter(module=module, include_deprecated=True))
    key_fields = ("Summary", "Browser", "Device") if mode == "exact" else ("Summary",)
    buckets: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[tuple(row[field] for field in key_fields)].append(row)
    groups = []
    for group_rows in buckets.values():
        if len(group_rows) < 2:
            continue
        group_rows.sort(key=_rank_key)
        groups.append({
            "keeper": compact(group_rows[0]),
            "duplicate_count": len(group_rows) - 1,
            "tests": [compact(row) for row in group_rows],
        })
    groups.sort(key=lambda group: (-group["duplicate_count"], group["keeper"]["key"]))
    bounded_limit = min(max(limit, 1), 100)
    return {"mode": mode, "duplicate_groups": len(groups), "duplicate_rows": sum(item["duplicate_count"] for item in groups), "groups": groups[:bounded_limit]}


@mcp.tool(tags={"quality"}, annotations={"readOnlyHint": True})
def find_coverage_gaps(module: str | None = None) -> dict[str, Any]:
    """Use to identify missing feature/test-type and priority coverage; use get_browser_device_matrix for browser/device details."""
    rows = repository.apply_filters(TestFilter(module=module))
    modules = sorted({row["module"] for row in rows})
    features = sorted({(row["module"], row["feature"]) for row in rows})
    present = {(row["module"], row["feature"], row["test_type"]) for row in rows}
    missing_types = [
        {"module": selected_module, "feature": feature, "test_type": test_type}
        for selected_module, feature in features for test_type in TEST_TYPES
        if (selected_module, feature, test_type) not in present
    ]
    highest_covered = {
        (row["module"], row["feature"]) for row in rows if row["priority"] == "Highest"
    }
    highest_missing = sorted(set(features) - highest_covered)
    security_missing = sorted({
        (selected_module, feature) for selected_module, feature in features
        if not any(row["module"] == selected_module and row["feature"] == feature and row["test_type"] == "Security" for row in rows)
    })
    accessibility_missing = sorted({
        (selected_module, feature) for selected_module, feature in features
        if not any(row["module"] == selected_module and row["feature"] == feature and row["test_type"] == "Accessibility" for row in rows)
    })
    matrix = get_browser_device_matrix(module=module)["matrix"]
    empty_cells = [{"browser": browser, "device": device} for browser in BROWSERS for device in DEVICES if not matrix[browser][device]]
    return {
        "modules": modules,
        "features_checked": len(features),
        "missing_feature_test_types": missing_types,
        "features_without_highest": [{"module": item[0], "feature": item[1]} for item in highest_missing],
        "features_without_security": [{"module": item[0], "feature": item[1]} for item in security_missing],
        "features_without_accessibility": [{"module": item[0], "feature": item[1]} for item in accessibility_missing],
        "empty_browser_device_cells": empty_cells,
    }


@mcp.tool(tags={"quality", "authoring"}, annotations={"readOnlyHint": True})
def validate_test_case(test_case: TestCaseDraft) -> dict[str, Any]:
    """Use to lint a proposed case before saving; use get_test_case_template to start from the VWO format."""
    return _validate_draft(test_case)


@mcp.tool(tags={"authoring"}, annotations={"readOnlyHint": True})
def get_test_case_template(
    module: str,
    feature: str,
    test_type: str,
    browser: str = "Chrome 148",
    device: str = "desktop",
) -> dict[str, Any]:
    """Use to create a new VWO-format test draft with examples; use validate_test_case before adding it."""
    selected_module = repository.resolve_module(module)
    if test_type not in TEST_TYPES or browser not in BROWSERS or device not in DEVICES:
        raise ValueError("Use a valid test_type, browser, and device from get_filter_options.")
    example_rows = [
        row for row in repository.rows
        if row["module"] == selected_module
        and row["feature"].casefold() == feature.casefold()
        and row["status"] != "Deprecated"
    ]
    examples = [full(row) for row in sorted(example_rows, key=_rank_key)[:3]]
    return {
        "template": {
            "issue_type": "Test", "issue_key": "Assigned when added",
            "summary": f"[{selected_module}] {test_type}: <action and feature>",
            "description": f"As a QA engineer, verify {feature} in the {selected_module} module.",
            "priority": "Medium", "module": selected_module, "feature": feature,
            "test_type": test_type, "preconditions": f"An active VWO account with access to {selected_module}.",
            "steps": ["Log in to VWO.", f"Open the {selected_module} module.", f"Exercise {feature}.", "Observe and record the result."],
            "expected_result": "Describe the observable result and persisted state.",
            "browser": browser, "device": device, "status": "Draft", "labels": [],
        },
        "examples": examples,
        "rules": ["Use the exact [Module] Test Type: summary prefix.", "Write numbered, actionable steps.", "State an observable expected result."],
    }


def _draft_to_row(draft: TestCaseDraft, key: str) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9]+", "-", draft.module.lower()).strip("-")
    return {
        "Issue Type": "Test", "Issue Key": key, "Summary": draft.summary,
        "Description": draft.description, "Priority": draft.priority, "Component": draft.module,
        "Labels": " ".join(dict.fromkeys([*draft.labels, slug, draft.test_type.lower()])),
        "Test Type": draft.test_type, "Preconditions": draft.preconditions,
        "Steps": draft.steps, "Expected Result": draft.expected_result,
        "Browser": draft.browser, "Device": draft.device, "Status": draft.status,
    }


def _next_key() -> int:
    return max((int(match.group(1)) for key in repository.by_key if (match := re.fullmatch(r"VWO-(\d+)", key))), default=6000) + 1


if WRITES_ENABLED:
    @mcp.tool(tags={"authoring"}, annotations={"readOnlyHint": False, "destructiveHint": False})
    def add_test_cases(test_cases: list[TestCaseDraft], dry_run: bool = True) -> dict[str, Any]:
        """Use only after reviewing draft cases; dry_run previews by default, then use validate_test_case to fix issues."""
        if not 1 <= len(test_cases) <= 25:
            raise ValueError("Provide between 1 and 25 test cases.")
        validation = [_validate_draft(item) for item in test_cases]
        invalid = [{"index": index, **result} for index, result in enumerate(validation) if not result["valid"]]
        if invalid:
            return {"created": False, "dry_run": dry_run, "invalid_cases": invalid}
        batch_summaries = Counter((item.module, item.summary.casefold()) for item in test_cases)
        repeated_batch = [summary for summary, count in batch_summaries.items() if count > 1]
        if repeated_batch:
            return {"created": False, "dry_run": dry_run, "duplicate_batch_summaries": [summary[1] for summary in repeated_batch]}
        next_number = _next_key()
        rows = [_draft_to_row(draft, f"VWO-{next_number + index}") for index, draft in enumerate(test_cases)]
        duplicate_keys = [key for row in rows for key in _validate_draft(TestCaseDraft(
            summary=row["Summary"], description=row["Description"], priority=row["Priority"],
            module=row["Component"], feature=_feature_from_csv_row(row), test_type=row["Test Type"],
            preconditions=row["Preconditions"], steps=row["Steps"], expected_result=row["Expected Result"],
            browser=row["Browser"], device=row["Device"], status=row["Status"],
        ))["possible_duplicates"]]
        if duplicate_keys:
            return {"created": False, "dry_run": dry_run, "duplicate_keys": sorted(set(duplicate_keys))}
        if not dry_run:
            repository.store_overlay(rows)
        return {"created": not dry_run, "dry_run": dry_run, "overlay": str(OVERLAY_PATH), "results": [_draft_preview(row) for row in rows]}

    @mcp.tool(tags={"authoring"}, annotations={"readOnlyHint": False, "destructiveHint": False})
    def update_test_case(issue_key: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Use to update status, priority, steps or expected result via the overlay; use search_test_cases to locate the case."""
        if issue_key not in repository.by_key:
            raise ValueError(f"Unknown issue key {issue_key!r}.")
        allowed = {"Priority", "Status", "Steps", "Expected Result", "priority", "status", "steps", "expected_result"}
        invalid = set(changes) - allowed
        if invalid or not changes:
            raise ValueError(f"changes must contain one or more of {sorted(allowed)}")
        row = dict(repository.by_key[issue_key])
        before = full(row)
        aliases = {"priority": "Priority", "status": "Status", "steps": "Steps", "expected_result": "Expected Result"}
        for key, value in changes.items():
            column = aliases.get(key, key)
            if column == "Priority" and value not in PRIORITIES:
                raise ValueError(f"Priority must be one of {PRIORITIES}")
            if column == "Status" and value not in STATUSES:
                raise ValueError(f"Status must be one of {STATUSES}")
            if column == "Steps" and (not isinstance(value, list) or not value or any(not str(step).strip() for step in value)):
                raise ValueError("Steps must be a non-empty list of nonblank strings.")
            row[column] = " | ".join(value) if column == "Steps" and isinstance(value, list) else value
        repository.store_overlay([row])
        return {"key": issue_key, "before": before, "after": full(repository.by_key[issue_key]), "overlay": str(OVERLAY_PATH)}


def _feature_from_csv_row(row: dict[str, Any]) -> str:
    return re.sub(r"^\[[^\]]+\]\s+[^:]+:\s*", "", row["Summary"]).strip()


def _draft_preview(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": row["Issue Key"], "summary": row["Summary"], "module": row["Component"],
        "priority": row["Priority"], "test_type": row["Test Type"],
        "browser": row["Browser"], "device": row["Device"], "status": row["Status"],
    }


@mcp.tool(tags={"export"}, annotations={"readOnlyHint": True})
def export_test_cases(
    format: str = "json",
    issue_keys: list[str] | None = None,
    filters: TestFilter | None = None,
) -> dict[str, Any]:
    """Use to export selected cases to csv, Jira CSV, markdown or JSON; use convert_to_gherkin for feature files."""
    if format not in {"csv", "jira_csv", "markdown", "json"}:
        raise ValueError("format must be csv, jira_csv, markdown or json.")
    if issue_keys and filters and filters.model_dump(exclude_defaults=True, exclude_none=True):
        raise ValueError("Provide issue_keys or filters, not both.")
    rows = _selected_rows(issue_keys, filters)
    export_rows = [_to_export_row(row) for row in rows]
    if len(rows) > 50:
        export_dir = EXPORT_PATH.resolve()
        export_dir.mkdir(parents=True, exist_ok=True)
        suffix = "csv" if format in {"csv", "jira_csv"} else format
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = export_dir / f"vwo_test_cases_{timestamp}.{suffix}"
        if format in {"csv", "jira_csv"}:
            with output.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerows([_to_csv_export_row(row) for row in rows])
        elif format == "json":
            output.write_text(json.dumps(export_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            output.write_text(_markdown_export(export_rows), encoding="utf-8")
        return {"format": format, "total": len(rows), "file": str(output)}
    if format == "json":
        content: Any = export_rows
    elif format == "markdown":
        content = _markdown_export(export_rows)
    elif format in {"csv", "jira_csv"}:
        import io
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows([_to_csv_export_row(row) for row in rows])
        content = stream.getvalue()
    return {"format": format, "total": len(rows), "content": content}


def _to_export_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "Issue Type": "Test", "Issue Key": row["key"], "Summary": row["Summary"],
        "Description": row["Description"], "Priority": row["priority"], "Component": row["module"],
        "Labels": " ".join(row["labels"]), "Test Type": row["test_type"],
        "Preconditions": row["Preconditions"], "Steps": _as_steps(row),
        "Expected Result": row["Expected Result"], "Browser": row["browser"],
        "Device": row["device"], "Status": row["status"],
    }


def _to_csv_export_row(row: dict[str, Any]) -> dict[str, str]:
    result = _to_export_row(row)
    result["Steps"] = " | ".join(result["Steps"])
    return {key: str(value) for key, value in result.items()}


def _markdown_export(rows: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f'## {row["Issue Key"]}: {row["Summary"]}\n\n'
        f'- **Module:** {row["Component"]}\n- **Priority:** {row["Priority"]}\n'
        f'- **Type:** {row["Test Type"]}\n- **Status:** {row["Status"]}\n\n'
        f'**Preconditions:** {row["Preconditions"]}\n\n'
        + "\n".join(f"{index}. {step}" for index, step in enumerate(row["Steps"], 1))
        + f'\n\n**Expected result:** {row["Expected Result"]}'
        for row in rows
    )


@mcp.tool(tags={"export"}, annotations={"readOnlyHint": True})
def convert_to_gherkin(issue_keys: list[str]) -> dict[str, str]:
    """Use to convert up to 10 cases into Gherkin feature scenarios; use export_test_cases for tabular formats."""
    if not 1 <= len(issue_keys) <= 10:
        raise ValueError("Provide between 1 and 10 issue keys.")
    rows = _selected_rows(issue_keys)
    blocks = []
    for row in rows:
        steps = _as_steps(row)
        lines = [f'Feature: {row["feature"]}', "", f'  Scenario: {row["Summary"]}']
        lines.append(f'    Given {row["Preconditions"]}')
        for index, step in enumerate(steps):
            keyword = "When" if index == 0 else "And"
            lines.append(f"    {keyword} {_step_text(step)}")
        lines.append(f'    Then {row["Expected Result"]}')
        blocks.append("\n".join(lines))
    return {"gherkin": "\n\n".join(blocks)}


@mcp.tool(tags={"export", "authoring"}, annotations={"readOnlyHint": True})
def generate_automation_stub(issue_key: str, framework: str = "pytest_playwright") -> dict[str, str]:
    """Use to scaffold a browser automation test from one case; use convert_to_gherkin for framework-neutral scenarios."""
    if issue_key not in repository.by_key:
        raise ValueError(f"Unknown issue key {issue_key!r}.")
    if framework not in {"pytest_playwright", "playwright_ts"}:
        raise ValueError("framework must be pytest_playwright or playwright_ts.")
    row = repository.by_key[issue_key]
    steps = _as_steps(row)
    if framework == "pytest_playwright":
        comments = "\n".join(f"    # {index}. {step}" for index, step in enumerate(steps, 1))
        code = (
            "import pytest\n\n"
            f"def test_{re.sub(r'[^a-z0-9]+', '_', issue_key.lower()).strip('_')}(page):\n"
            f'    """{row["Summary"]}"""\n'
            f"{comments}\n"
            "    # TODO: Replace these comments with Playwright actions and assertions.\n"
            f'    assert page.title()  # Expected: {row["Expected Result"]}\n'
        )
    else:
        comments = "\n".join(f"  // {index}. {step}" for index, step in enumerate(steps, 1))
        code = (
            "import { test, expect } from '@playwright/test';\n\n"
            f"test({json.dumps(row['Summary'])}, async ({{ page }}) => {{\n"
            f"{comments}\n"
            "  // TODO: Replace these comments with Playwright actions and assertions.\n"
            f"  await expect(page).toHaveTitle(/.+/); // Expected: {row['Expected Result']}\n"
            "});\n"
        )
    return {"framework": framework, "issue_key": issue_key, "code": code}


@mcp.resource("tc://schema")
def schema_resource() -> str:
    """Provide the VWO test-case schema and dataset filter values."""
    return json.dumps({"columns": CSV_FIELDS, "priorities": PRIORITIES, "modules": repository.modules, "test_types": TEST_TYPES, "browsers": BROWSERS, "devices": DEVICES, "statuses": STATUSES}, ensure_ascii=False)


@mcp.resource("tc://modules")
def modules_resource() -> str:
    """Provide module names, features, and test counts."""
    return json.dumps(list_modules(), ensure_ascii=False)


@mcp.resource("tc://stats/summary")
def summary_resource() -> str:
    """Provide headline dataset totals and priority counts."""
    live = [row for row in repository.rows if row["status"] != "Deprecated"]
    return json.dumps({"total": len(repository.rows), "live": len(live), "modules": len(repository.modules), "priorities": counts(live, "priority")}, ensure_ascii=False)


@mcp.resource("tc://test/{issue_key}")
def test_case_resource(issue_key: str) -> str:
    """Provide a full test case by key as an addressable resource."""
    if issue_key not in repository.by_key:
        raise ValueError(f"Unknown issue key {issue_key!r}.")
    return json.dumps(full(repository.by_key[issue_key]), ensure_ascii=False)


@mcp.prompt
def generate_test_cases(module: str, feature: str, test_type: str, count: int = 3) -> str:
    """Guide the client through drafting, validating, and previewing new cases."""
    return f"Create {count} distinct VWO test cases for {feature} in {module}, type {test_type}. Use get_test_case_template for examples, validate each draft, show all drafts to the user, and only then call add_test_cases with dry_run=false if writes are enabled and the user approves."


@mcp.prompt
def plan_release_run(modules: str, max_tests: int, deadline_hours: float) -> str:
    """Guide the client through selecting and estimating a release test suite."""
    return f"Plan a test run for {modules}, capped at {max_tests} tests and {deadline_hours} hours. Use build_test_suite, estimate_execution_effort, then export the final selection."


@mcp.prompt
def review_module_coverage(module: str) -> str:
    """Guide the client through a concise test coverage review."""
    return f"Review test coverage for {module}. Use get_test_stats, find_coverage_gaps, and find_duplicate_tests; summarize the largest actionable gaps and the evidence."


def main() -> None:
    """Run the MCP server over stdio for local MCP clients."""
    mcp.run()


if __name__ == "__main__":
    main()
