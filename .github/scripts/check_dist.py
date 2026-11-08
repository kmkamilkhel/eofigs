"""Check the contents of the built wheel and sdist in dist/.

Usage: python .github/scripts/check_dist.py [dist]

The wheel must carry the package data (journal presets, variable library, the bundled
Natural Earth countries, the typing marker) and the licence. Only expected entries may sit
at the top level of either archive, and neither may carry the documentation, its sample
data, the built site or build caches.
"""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from pathlib import Path

WHEEL_NEEDS = (
    "eofigs/__init__.py",
    "eofigs/py.typed",
    "eofigs/data/journals.json",
    "eofigs/data/variables.json",
    "eofigs/data/ne_110m_countries.geojson",
)
SDIST_NEEDS = ("pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md", "CITATION.cff",
               "src/eofigs/__init__.py", "src/eofigs/data/journals.json")  # fmt: skip
#: Everything else at the top level of an archive is an error (an allowlist, so that
#: local files can never slip in).
WHEEL_TOP = re.compile(r"^(eofigs|eofigs-[^/]+\.dist-info)$")
SDIST_TOP = {"src", "tests", "conftest.py", "README.md", "LICENSE", "CHANGELOG.md",
             "CITATION.cff", "pyproject.toml", "PKG-INFO", ".gitignore"}  # fmt: skip
NEVER = re.compile(r"(^|/)(docs|site|build|examples)/|\.(tif|tiff|nc)$", re.IGNORECASE)


def check(names: list[str], needs: tuple[str, ...], allowed, label: str) -> list[str]:
    """Problems with one archive's file list."""
    problems = [f"{label}: missing {n}" for n in needs if n not in names]
    tops = sorted({n.split("/")[0] for n in names if n})
    problems += [f"{label}: unexpected top-level entry {t}" for t in tops if not allowed(t)]
    problems += [f"{label}: should not contain {n}" for n in names if NEVER.search(n)]
    return problems


def main() -> int:
    """Check both archives in the dist folder; exit code 1 on any problem."""
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels = sorted(dist.glob("eofigs-*.whl"))
    sdists = sorted(dist.glob("eofigs-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        print(f"expected one wheel and one sdist in {dist}, found {wheels + sdists}")
        return 1
    with zipfile.ZipFile(wheels[0]) as z:
        names = z.namelist()
    problems = check(names, WHEEL_NEEDS, WHEEL_TOP.match, wheels[0].name)
    if not any(re.search(r"\.dist-info/licenses/LICENSE$", n) for n in names):
        problems.append(f"{wheels[0].name}: missing the licence file")
    with tarfile.open(sdists[0]) as t:
        root = t.getnames()[0].split("/")[0]
        names = [n.removeprefix(root + "/") for n in t.getnames() if n != root]
    problems += check(names, SDIST_NEEDS, SDIST_TOP.__contains__, sdists[0].name)
    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"{wheels[0].name} and {sdists[0].name}: contents ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
