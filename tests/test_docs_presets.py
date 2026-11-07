"""The journal presets page must show the values in journals.json."""

from pathlib import Path

import pytest

from eofigs._presets import get_journal, journal_keys

DOC = Path(__file__).resolve().parents[1] / "docs" / "journals.md"


@pytest.mark.skipif(not DOC.exists(), reason="documentation not available (installed package)")
@pytest.mark.parametrize("key", journal_keys())
def test_presets_page_matches_data(key):
    rows = [
        line
        for line in DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| `{key}`")
    ]
    assert len(rows) == 1, f"no single row for {key}"
    row = rows[0]
    j = get_journal(key)
    for name, width in j.widths_mm.items():
        if name != "minimum":
            assert f"{name} {width:g}" in row
    assert f"| {j.max_height_mm:g}" in row
    assert f"{j.dpi['line']} / {j.dpi['halftone']} / {j.dpi['combination']}" in row
    assert ", ".join(f.upper() for f in j.formats) in row
    if j.source_url:
        assert j.source_url in row and j.checked in row
