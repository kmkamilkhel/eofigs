"""The variables page must contain the table generated from variables.json."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "variables.md"
SCRIPT = ROOT / "docs" / "scripts" / "variables_table.py"


@pytest.mark.skipif(not DOC.exists(), reason="documentation not available (installed package)")
def test_variables_page_matches_data():
    spec = importlib.util.spec_from_file_location("variables_table", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.table() in DOC.read_text(encoding="utf-8"), (
        "docs/variables.md is out of date: run python docs/scripts/variables_table.py"
    )
