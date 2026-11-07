import re

import eofigs


def test_version_is_pep440_string():
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+|rc\d+)?", eofigs.__version__)


def test_public_api_exposes_only_what_works():
    assert eofigs.__all__ == ["__version__"]
