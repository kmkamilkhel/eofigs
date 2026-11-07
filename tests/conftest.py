import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from eofigs import styling as style_module  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state():
    """Run each test with fresh matplotlib settings and eofigs defaults."""
    saved_state = dict(style_module._STATE)
    with matplotlib.rc_context():
        yield
    plt.close("all")
    style_module._STATE.clear()
    style_module._STATE.update(saved_state)


@pytest.fixture
def sans_font():
    """A sans-serif font that is installed everywhere (shipped with matplotlib)."""
    return "DejaVu Sans"
