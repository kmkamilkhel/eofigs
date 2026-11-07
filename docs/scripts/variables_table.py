"""Print the variable table for docs/variables.md from the bundled variables.json.

Run from the repository root:  python docs/scripts/variables_table.py
The test suite checks that docs/variables.md contains exactly this table.
"""

import re

from eofigs.variables import _bundled


def _html(mathtext: str) -> str:
    text = re.sub(r"\$\^\{([^}]*)\}\$", r"<sup>\1</sup>", mathtext)
    text = re.sub(r"\$_\{([^}]*)\}\$", r"<sub>\1</sub>", text)
    return text.replace("$\\degree$", "°").replace("$", "")


def _limits(vmin, vmax) -> str:
    if vmin is None and vmax is None:
        return "from data"
    low = "data" if vmin is None else f"{vmin:g}"
    high = "data" if vmax is None else f"{vmax:g}"
    return f"{low} to {high}"


def table() -> str:
    """Markdown table of the bundled variables (not those registered in this session)."""
    lines = [
        "| Name | Long name | Symbol | Units | Colour map | Anomaly and trend map "
        "| Default range |",
        "|---|---|---|---|---|---|---|",
    ]
    for _name, v in sorted(_bundled().items()):
        lines.append(
            f"| `{v.name}` | {v.long_name} | {_html(v.symbol)} | {_html(v.units) or '–'} "
            f"| `{v.cmap}` | `{v.anomaly_cmap}` | {_limits(v.vmin, v.vmax)} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(table())
