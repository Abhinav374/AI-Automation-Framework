# VWO Test Creator MCP

A local, deterministic MCP server for the 5,000 VWO test cases in `data/vwo_5000_test_cases.csv`. The server makes no LLM calls. It reads the source CSV at startup, keeps it unchanged, and exposes test discovery, execution planning, quality checks, authoring, and export tools.

## Start the server

Requires Python 3.11+ and `uv`:

```powershell
cd Chapter_14_MCP_Create_VIB
uv sync
uv run vwo-test-creator-mcp
```

For direct Python execution:

```powershell
$env:PYTHONPATH = "src"
python -m tc_mcp.server
```

The server uses stdio. For a VS Code MCP client, add a server entry to `.vscode/mcp.json`:

```json
{
  "servers": {
    "vwo-test-creator": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\AI-Automation-Framework\\Chapter_14_MCP_Create_VIB",
        "run",
        "vwo-test-creator-mcp"
      ]
    }
  }
}
```

The default CSV path is `data/vwo_5000_test_cases.csv`. Set `TC_MCP_CSV_PATH`, `TC_MCP_OVERLAY_PATH`, or `TC_MCP_EXPORT_PATH` to use explicit local paths. No external service, API key, or network connection is required after installation.

## Tools

The read-only server exposes 19 tools:

- **Discovery:** `list_modules`, `get_filter_options`, `get_test_stats`
- **Search:** `get_test_case`, `search_test_cases`, `search_by_keyword`, `get_top_tests_for_module`, `get_similar_test_cases`
- **Planning:** `build_test_suite`, `get_browser_device_matrix`, `get_automation_candidates`, `estimate_execution_effort`
- **Quality:** `find_duplicate_tests`, `find_coverage_gaps`, `validate_test_case`
- **Authoring/export:** `get_test_case_template`, `export_test_cases`, `convert_to_gherkin`, `generate_automation_stub`

`search_test_cases` accepts a `filters` object. For example, search for the top 10 Reports cases from High through Highest priority:

```json
{
  "filters": {
    "module": "Reports",
    "min_priority": "High"
  },
  "limit": 10,
  "sort_by": "priority"
}
```

Priority order is `Low < Medium < High < Highest`. `min_priority` and `max_priority` are inclusive. `limit` is clamped to 1–100 compact rows or 1–25 full rows; `offset` paginates the matched results. `get_top_tests_for_module` ranks cases by priority, status, and test type, then spreads picks across scenarios and features.

Resources are available at `tc://schema`, `tc://modules`, `tc://stats/summary`, and `tc://test/{issue_key}`. Prompts guide test drafting, release-run planning, and coverage review.

## Writing new cases

Write tools are **not registered by default**. To enable `add_test_cases` and `update_test_case`, set `TC_MCP_ALLOW_WRITES=true` before starting the server. New and updated rows are stored only in `data/tc_additions.csv`; the original 5,000-row dataset is never edited. `add_test_cases` defaults to `dry_run=true`, validates drafts, and checks for duplicate summaries before writing. Review its preview, then explicitly set `dry_run=false` to persist.

To keep test data elsewhere, set `TC_MCP_OVERLAY_PATH` to an explicit writable file path. Exports are written under the chapter's `exports/` directory when more than 50 rows are selected.

## Tests

```powershell
uv sync --extra test
uv run pytest
```
