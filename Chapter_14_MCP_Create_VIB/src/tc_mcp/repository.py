"""CSV-backed storage and shared query helpers for the VWO test creator."""

from __future__ import annotations

import csv
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGED_DATA = Path(__file__).resolve().parent / "data"
_project_csv = PROJECT_ROOT / "data" / "vwo_5000_test_cases.csv"
DATA_PATH = Path(os.environ["TC_MCP_CSV_PATH"]) if "TC_MCP_CSV_PATH" in os.environ else (
    _project_csv if _project_csv.is_file() else PACKAGED_DATA / "vwo_5000_test_cases.csv"
)
_overlay_root = PROJECT_ROOT if _project_csv.is_file() else Path.home() / ".local" / "share" / "vwo-test-creator-mcp"
OVERLAY_PATH = Path(os.environ.get("TC_MCP_OVERLAY_PATH", _overlay_root / "tc_additions.csv"))
EXPORT_PATH = Path(os.environ.get("TC_MCP_EXPORT_PATH", _overlay_root / "exports"))
CSV_FIELDS = [
    "Issue Type", "Issue Key", "Summary", "Description", "Priority", "Component",
    "Labels", "Test Type", "Preconditions", "Steps", "Expected Result", "Browser",
    "Device", "Status",
]
PRIORITIES = ["Low", "Medium", "High", "Highest"]
TEST_TYPES = [
    "Functional", "Negative", "UI/UX", "API", "Boundary", "Regression",
    "Security", "Accessibility", "Performance",
]
STATUSES = ["Ready", "Automated", "Draft", "Deprecated"]
BROWSERS = ["Chrome 148", "Firefox 141", "Safari 19", "Edge 148"]
DEVICES = ["desktop", "mobile (Android)", "mobile (iOS)", "tablet"]
PRIORITY_WEIGHT = {"Highest": 40, "High": 30, "Medium": 20, "Low": 10}
STATUS_WEIGHT = {"Ready": 10, "Automated": 8, "Draft": 2, "Deprecated": 0}
TYPE_WEIGHT = {
    "Security": 6, "Functional": 6, "Negative": 5, "API": 5, "Regression": 4,
    "Boundary": 4, "Performance": 3, "UI/UX": 2, "Accessibility": 2,
}
ALIASES = {
    "ab testing": "A/B Testing",
    "ab-test": "A/B Testing",
    "ab-testings": "A/B Testing",
    "billing": "Account & Billing",
    "sdk": "SDK / Server-Side API",
    "server-side api": "SDK / Server-Side API",
    "user management": "User Management",
}
_LOCK = RLock()


class TestFilter(BaseModel):
    """Common filters used by search, statistics, and execution estimation."""

    __test__ = False

    module: str | list[str] | None = None
    feature: str | None = None
    priority: list[str] | None = None
    min_priority: str | None = None
    max_priority: str | None = None
    test_type: list[str] | None = None
    browser: str | None = None
    device: str | None = None
    status: list[str] | None = None
    label: str | None = None
    include_deprecated: bool = False
    include_duplicates: bool = True


class TestCaseDraft(BaseModel):
    """Fields accepted when a user proposes a new test case."""

    summary: str
    description: str
    priority: str = "Medium"
    module: str
    feature: str
    test_type: str
    preconditions: str
    steps: list[str] = Field(min_length=1)
    expected_result: str
    browser: str = "Chrome 148"
    device: str = "desktop"
    status: str = "Draft"
    labels: list[str] = Field(default_factory=list)


def _feature_from_row(row: dict[str, str]) -> str:
    match = re.search(r"\bthe\s+(.+?)\s+in\s+the\s+.+?\s+module\b", row["Description"], re.I)
    if match:
        return match.group(1).strip().rstrip(" .")
    summary = re.match(r"^\[[^\]]+\]\s+[^:]+:\s+(.+)$", row["Summary"])
    return summary.group(1).strip() if summary else row["Summary"]


def _normalize_row(raw: dict[str, str]) -> dict[str, Any]:
    row: dict[str, Any] = {field: (raw.get(field) or "").strip() for field in CSV_FIELDS}
    module_slug = "ab-testing" if row["Component"] == "A/B Testing" else re.sub(
        r"[^a-z0-9]+", "-", row["Component"].lower()
    ).strip("-")
    labels = row["Labels"].split()
    if row["Component"] == "A/B Testing":
        labels = [label for label in labels if label.lower() != "a"]
    row["Labels"] = " ".join(dict.fromkeys([*labels, module_slug]))
    row["Steps"] = [step.strip() for step in row["Steps"].split("|") if step.strip()]
    row["feature"] = _feature_from_row(row)
    row["module"] = row["Component"]
    row["key"] = row["Issue Key"]
    row["priority"] = row["Priority"]
    row["test_type"] = row["Test Type"]
    row["status"] = row["Status"]
    row["browser"] = row["Browser"]
    row["device"] = row["Device"]
    row["labels"] = row["Labels"].split()
    return row


class TestRepository:
    """Loads the immutable source CSV and merges optional authored overlays."""

    __test__ = False

    def __init__(self, csv_path: Path = DATA_PATH, overlay_path: Path = OVERLAY_PATH):
        self.csv_path = Path(csv_path)
        self.overlay_path = Path(overlay_path)
        self.rows = self._load()
        self.by_key = {row["key"]: row for row in self.rows}
        self.modules = sorted({row["module"] for row in self.rows})

    def _load(self) -> list[dict[str, Any]]:
        if not self.csv_path.is_file():
            raise FileNotFoundError(f"Test-case CSV not found: {self.csv_path}")
        rows: dict[str, dict[str, Any]] = {}
        for path in [self.csv_path, self.overlay_path]:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                missing = set(CSV_FIELDS) - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f"{path} is missing CSV columns: {', '.join(sorted(missing))}")
                for raw in reader:
                    row = _normalize_row(raw)
                    if row["key"]:
                        rows[row["key"]] = row
        return sorted(rows.values(), key=lambda row: row["key"])

    def reload(self) -> None:
        self.rows = self._load()
        self.by_key = {row["key"]: row for row in self.rows}
        self.modules = sorted({row["module"] for row in self.rows})

    def resolve_module(self, module: str) -> str:
        normalized = module.strip().casefold()
        for candidate in self.modules:
            if candidate.casefold() == normalized:
                return candidate
        alias = ALIASES.get(normalized)
        if alias in self.modules:
            return alias
        close = sorted(self.modules, key=lambda item: _distance(normalized, item.casefold()))[:3]
        suggestions = ", ".join(close)
        raise ValueError(f"Unknown module {module!r}. Did you mean {suggestions}? Valid modules: {', '.join(self.modules)}")

    def apply_filters(self, filters: TestFilter | None = None) -> list[dict[str, Any]]:
        filters = filters or TestFilter()
        if filters.min_priority and filters.min_priority not in PRIORITIES:
            raise ValueError(f"Invalid min_priority {filters.min_priority!r}. Valid values: {PRIORITIES}")
        if filters.max_priority and filters.max_priority not in PRIORITIES:
            raise ValueError(f"Invalid max_priority {filters.max_priority!r}. Valid values: {PRIORITIES}")
        minimum = PRIORITIES.index(filters.min_priority) if filters.min_priority else 0
        maximum = PRIORITIES.index(filters.max_priority) if filters.max_priority else len(PRIORITIES) - 1
        if minimum > maximum:
            raise ValueError("min_priority cannot be higher than max_priority.")
        selected_modules = filters.module if isinstance(filters.module, list) else ([filters.module] if filters.module else [])
        modules = {self.resolve_module(module) for module in selected_modules}
        priorities = filters.priority or []
        test_types = filters.test_type or []
        statuses = filters.status or []
        result = []
        for row in self.rows:
            if not filters.include_deprecated and row["status"] == "Deprecated":
                continue
            if modules and row["module"] not in modules:
                continue
            if filters.feature and filters.feature.casefold() not in row["feature"].casefold():
                continue
            if priorities and row["priority"] not in priorities:
                continue
            if not minimum <= PRIORITIES.index(row["priority"]) <= maximum:
                continue
            if test_types and row["test_type"] not in test_types:
                continue
            if filters.browser and filters.browser.casefold() != row["browser"].casefold():
                continue
            if filters.device and filters.device.casefold() != row["device"].casefold():
                continue
            if statuses and row["status"] not in statuses:
                continue
            if filters.label and filters.label.casefold() not in " ".join(row["labels"]).casefold():
                continue
            result.append(row)
        if not filters.include_duplicates:
            unique: dict[tuple[str, str, str], dict[str, Any]] = {}
            for row in result:
                unique.setdefault((row["Summary"], row["browser"], row["device"]), row)
            result = list(unique.values())
        return result

    def store_overlay(self, rows: Iterable[dict[str, Any]]) -> None:
        """Atomically replace the overlay; the source dataset is never modified."""
        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            existing: dict[str, dict[str, str]] = {}
            if self.overlay_path.exists():
                with self.overlay_path.open("r", encoding="utf-8-sig", newline="") as source:
                    for row in csv.DictReader(source):
                        if row.get("Issue Key"):
                            existing[row["Issue Key"]] = {field: row.get(field, "") for field in CSV_FIELDS}
            for row in rows:
                key = row.get("Issue Key", row.get("key", ""))
                existing[key] = _to_csv_row(row)
            fd, temp_name = tempfile.mkstemp(dir=self.overlay_path.parent, suffix=".tmp", text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as target:
                    writer = csv.DictWriter(target, fieldnames=CSV_FIELDS)
                    writer.writeheader()
                    writer.writerows(existing.values())
                os.replace(temp_name, self.overlay_path)
            except Exception:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
                raise
        self.reload()


def _to_csv_row(row: dict[str, Any]) -> dict[str, str]:
    result = {field: str(row.get(field, "")) for field in CSV_FIELDS}
    result["Issue Type"] = result["Issue Type"] or "Test"
    steps = row.get("Steps", row.get("steps", []))
    if isinstance(steps, list):
        result["Steps"] = " | ".join(str(step) for step in steps)
    aliases = {
        "Issue Key": "key", "Priority": "priority", "Component": "module",
        "Test Type": "test_type", "Status": "status", "Browser": "browser",
        "Device": "device", "Expected Result": "expected_result",
        "Preconditions": "preconditions", "Labels": "labels",
    }
    for field, alias in aliases.items():
        if field not in row and alias in row:
            value = row[alias]
            result[field] = " ".join(value) if field == "Labels" and isinstance(value, list) else str(value)
    return result


def _distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, 1):
        current = [i]
        for j, char_right in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char_left != char_right)))
        previous = current
    return previous[-1]


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": row["key"], "summary": row["Summary"], "module": row["module"],
        "feature": row["feature"], "priority": row["priority"], "test_type": row["test_type"],
        "status": row["status"], "browser": row["browser"], "device": row["device"],
    }


def full(row: dict[str, Any]) -> dict[str, Any]:
    result = compact(row)
    result.update({
        "description": row["Description"], "preconditions": row["Preconditions"],
        "steps": row["Steps"], "expected_result": row["Expected Result"],
        "labels": row["labels"],
    })
    return result


def response(rows: list[dict[str, Any]], limit: int, offset: int, filters: Any, detail: str = "compact") -> dict[str, Any]:
    max_limit = 25 if detail == "full" else 100
    bounded_limit = min(max(limit, 1), max_limit)
    page = rows[offset:offset + bounded_limit]
    transform = full if detail == "full" else compact
    return {
        "total_matched": len(rows),
        "returned": len(page),
        "offset": max(0, offset),
        "next_offset": offset + len(page) if offset + len(page) < len(rows) else None,
        "filters_applied": filters.model_dump(exclude_none=True) if isinstance(filters, BaseModel) else filters,
        "results": [transform(row) for row in page],
        "hint": "No matches. Try loosening one or more filters." if not rows else None,
    }


def counts(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def grouped(rows: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[row[field]].append(row)
    return result
