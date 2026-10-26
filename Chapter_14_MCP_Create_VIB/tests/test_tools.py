import asyncio
from pathlib import Path

from fastmcp.client import Client

from tc_mcp.server import WRITES_ENABLED, mcp


def test_server_registers_read_tools_and_excludes_writes_by_default():
    async def inspect_tools():
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(inspect_tools())

    assert len(names) == (21 if WRITES_ENABLED else 19)
    assert {"search_test_cases", "get_top_tests_for_module", "build_test_suite"} <= names
    assert ("add_test_cases" in names) is WRITES_ENABLED
    assert ("update_test_case" in names) is WRITES_ENABLED


def test_resources_and_prompts_are_registered():
    async def inspect_context():
        async with Client(mcp) as client:
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            prompts = await client.list_prompts()
            test_case = await client.read_resource("tc://test/VWO-1001")
        return resources, templates, prompts, test_case

    resources, templates, prompts, test_case = asyncio.run(inspect_context())

    assert len(resources) == 3
    assert len(templates) == 1
    assert len(prompts) == 3
    assert test_case


def test_top_tests_tool_returns_diverse_ranked_results():
    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "get_top_tests_for_module",
                {"module": "Reports", "count": 5},
            )

    result = asyncio.run(call_tool())
    payload = result.structured_content

    assert payload["module"] == "Reports"
    assert payload["returned"] == 5
    assert [case["rank"] for case in payload["results"]] == [1, 2, 3, 4, 5]
    assert all(case["priority"] in {"Highest", "High", "Medium", "Low"} for case in payload["results"])


def test_filter_search_obeys_inclusive_minimum_priority():
    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "search_test_cases",
                {
                    "filters": {"module": "Reports", "min_priority": "High"},
                    "limit": 10,
                    "sort_by": "priority",
                },
            )

    payload = asyncio.run(call_tool()).structured_content

    assert payload["total_matched"] > 0
    assert payload["returned"] == 10
    assert all(case["module"] == "Reports" for case in payload["results"])
    assert all(case["priority"] in {"High", "Highest"} for case in payload["results"])


def test_read_tool_families_work_through_mcp_client():
    async def exercise_tools():
        async with Client(mcp) as client:
            calls = [
                ("list_modules", {"include_features": False}),
                ("get_filter_options", {}),
                ("get_test_stats", {"group_by": ["module", "priority"]}),
                ("get_test_case", {"issue_keys": ["VWO-1001"]}),
                ("search_by_keyword", {"query": "data collection"}),
                ("get_similar_test_cases", {"issue_key": "VWO-1001"}),
                ("build_test_suite", {"suite_type": "smoke", "max_tests": 20}),
                ("get_browser_device_matrix", {"module": "Reports"}),
                ("get_automation_candidates", {"module": "Reports", "limit": 5}),
                ("estimate_execution_effort", {"issue_keys": ["VWO-1001"]}),
                ("find_duplicate_tests", {}),
                ("find_coverage_gaps", {"module": "Reports"}),
                (
                    "validate_test_case",
                    {
                        "test_case": {
                            "summary": "[Reports] Functional: verify report sharing",
                            "description": "Verify report sharing in the Reports module.",
                            "priority": "High",
                            "module": "Reports",
                            "feature": "report sharing",
                            "test_type": "Functional",
                            "preconditions": "A VWO account with access to Reports.",
                            "steps": ["Log in.", "Open Reports.", "Share a report."],
                            "expected_result": "The selected users can access the shared report.",
                            "browser": "Chrome 148",
                            "device": "desktop",
                        }
                    },
                ),
                (
                    "get_test_case_template",
                    {"module": "Reports", "feature": "scheduled email", "test_type": "Functional"},
                ),
                ("export_test_cases", {"issue_keys": ["VWO-1001"], "format": "json"}),
                ("convert_to_gherkin", {"issue_keys": ["VWO-1001"]}),
                ("generate_automation_stub", {"issue_key": "VWO-1001"}),
            ]
            results = {}
            for name, arguments in calls:
                results[name] = await client.call_tool(name, arguments)
            return results

    results = asyncio.run(exercise_tools())

    assert len(results) == 17
    assert all(not result.is_error for result in results.values())
    assert results["get_test_stats"].structured_content["total"] == 4585
    assert results["validate_test_case"].structured_content["valid"] is True
    assert "Feature:" in results["convert_to_gherkin"].structured_content["gherkin"]
    assert results["find_duplicate_tests"].structured_content["duplicate_rows"] == 466
