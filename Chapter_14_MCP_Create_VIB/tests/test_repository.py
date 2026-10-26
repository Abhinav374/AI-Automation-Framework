from pathlib import Path

from tc_mcp.repository import TestFilter, TestRepository


DATA = Path(__file__).resolve().parents[1] / "data" / "vwo_5000_test_cases.csv"


def repository(tmp_path):
    return TestRepository(DATA, tmp_path / "tc_additions.csv")


def test_loads_dataset_and_normalizes_labels(tmp_path):
    repo = repository(tmp_path)

    assert len(repo.rows) == 5000
    assert len(repo.modules) == 17
    assert len({row["feature"] for row in repo.rows}) == 72
    ab_cases = [row for row in repo.rows if row["module"] == "A/B Testing"]
    assert all("a" not in row["labels"] for row in ab_cases)
    assert all("ab-testing" in row["labels"] for row in ab_cases)


def test_filters_priority_range_module_and_deprecated_default(tmp_path):
    repo = repository(tmp_path)

    cases = repo.apply_filters(TestFilter(module="Reports", min_priority="High"))

    assert cases
    assert all(row["module"] == "Reports" for row in cases)
    assert all(row["priority"] in {"High", "Highest"} for row in cases)
    assert all(row["status"] != "Deprecated" for row in cases)


def test_unknown_module_suggests_valid_modules(tmp_path):
    repo = repository(tmp_path)

    try:
        repo.apply_filters(TestFilter(module="Report"))
    except ValueError as error:
        assert "Reports" in str(error)
    else:
        raise AssertionError("Unknown module should be rejected.")


def test_invalid_priority_range_is_reported(tmp_path):
    repo = repository(tmp_path)

    try:
        repo.apply_filters(TestFilter(min_priority="Highest", max_priority="Low"))
    except ValueError as error:
        assert "min_priority" in str(error)
    else:
        raise AssertionError("Inverted priority range should be rejected.")


def test_overlay_is_atomic_and_does_not_change_source(tmp_path):
    source_before = DATA.read_bytes()
    repo = repository(tmp_path)
    addition = {
        "Issue Type": "Test",
        "Issue Key": "VWO-6001",
        "Summary": "[Reports] Functional: verify new report export",
        "Description": "Verify new report export in the Reports module.",
        "Priority": "High",
        "Component": "Reports",
        "Labels": "reports functional",
        "Test Type": "Functional",
        "Preconditions": "An active VWO account.",
        "Steps": ["Log in.", "Open Reports.", "Export a report."],
        "Expected Result": "The report is exported and downloadable.",
        "Browser": "Chrome 148",
        "Device": "desktop",
        "Status": "Draft",
    }

    repo.store_overlay([addition])

    assert "VWO-6001" in repo.by_key
    assert DATA.read_bytes() == source_before
    assert repo.overlay_path.is_file()


def test_exact_duplicate_groups_match_dataset_baseline(tmp_path):
    repo = repository(tmp_path)
    rows = repo.apply_filters(TestFilter(include_deprecated=True))
    groups = {}
    for row in rows:
        groups.setdefault((row["Summary"], row["Browser"], row["Device"]), []).append(row)

    duplicate_rows = sum(len(group) - 1 for group in groups.values() if len(group) > 1)

    assert duplicate_rows == 466
