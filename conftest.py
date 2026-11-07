"""Test set-up shared by the test suite and the docstring examples."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from eofigs import styling, variables  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state():
    """Run every test and example with fresh matplotlib settings, eofigs defaults and library."""
    saved_style = dict(styling._STATE)
    saved_registry = dict(variables._REGISTERED)
    with matplotlib.rc_context():
        yield
    plt.close("all")
    styling._STATE.clear()
    styling._STATE.update(saved_style)
    variables._REGISTERED.clear()
    variables._REGISTERED.update(saved_registry)
