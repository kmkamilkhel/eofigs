import pytest


@pytest.fixture
def sans_font():
    """A sans-serif font that is installed everywhere (shipped with matplotlib)."""
    return "DejaVu Sans"
