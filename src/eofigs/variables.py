"""Variable library: names, symbols, units and colour maps for Earth observation variables."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources
from typing import Any

import cmcrameri.cm  # noqa: F401  (registers the "cmc.*" colour maps)
import matplotlib as mpl
from matplotlib.colors import Colormap

import eofigs.palettes  # noqa: F401  (registers the "eofigs.*" colour maps)

KINDS = ("continuous", "diverging", "categorical", "mask")
PER_UNITS = {"year": "yr", "decade": "decade"}


@dataclass(frozen=True)
class Variable:
    """How one variable is named, labelled and coloured.

    Attributes
    ----------
    name : str
        Key in the library, for example ``"ndvi"``.
    long_name : str
        Full name, for example ``"Normalized Difference Vegetation Index"``.
    symbol : str
        Short symbol in matplotlib mathtext, for example ``"NDVI"`` or ``"T$_{a}$"``.
    units : str
        Units in mathtext (``"gC m$^{-2}$ d$^{-1}$"``); empty for unitless variables.
        These are the units the data are expected in; eofigs never converts units.
    cmap : str
        Registered matplotlib colour map name (cmcrameri maps are ``"cmc.<name>"``).
    anomaly_cmap : str
        Diverging colour map for anomalies and trends, centred on zero.
    kind : {"continuous", "diverging", "categorical", "mask"}
        How the data behave; sets the colour scaling and the raster reduction.
    vmin, vmax : float or None
        Default colour limits; ``None`` lets the data decide.
    standard_name : str or None
        CF standard name used to recognise the variable in xarray attributes.
    aliases : tuple of str
        Other names that refer to the variable.
    """

    name: str
    long_name: str
    symbol: str
    units: str = ""
    cmap: str = "cmc.batlow"
    anomaly_cmap: str = "cmc.vik"
    kind: str = "continuous"
    vmin: float | None = None
    vmax: float | None = None
    standard_name: str | None = None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the fields."""
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS} (got {self.kind!r}).")
        for field_name in ("cmap", "anomaly_cmap"):
            name = getattr(self, field_name)
            if name not in mpl.colormaps:
                raise ValueError(
                    f"{field_name} {name!r} is not a registered colour map. "
                    "Use a matplotlib name or a cmcrameri name such as 'cmc.batlow'."
                )
        if self.vmin is not None and self.vmax is not None and self.vmin >= self.vmax:
            raise ValueError(f"vmin ({self.vmin}) must be smaller than vmax ({self.vmax}).")

    @property
    def label(self) -> str:
        """Axis or colour-bar label: long name with units in brackets."""
        return f"{self.long_name} ({self.units})" if self.units else self.long_name

    @property
    def short_label(self) -> str:
        """Compact label: symbol with units in brackets."""
        return f"{self.symbol} ({self.units})" if self.units else self.symbol

    def get_cmap(self) -> Colormap:
        """Return the colour map as a matplotlib object."""
        return mpl.colormaps[self.cmap]

    def anomaly(self) -> Variable:
        """Return the variable as an anomaly: zero-centred diverging colours, same units."""
        return replace(
            self,
            name=f"{self.name}_anomaly",
            long_name=f"{self.long_name} anomaly",
            symbol=f"{self.symbol} anomaly",
            cmap=self.anomaly_cmap,
            kind="diverging",
            vmin=None,
            vmax=None,
            standard_name=None,
            aliases=(),
        )

    def trend(self, per: str = "decade") -> Variable:
        """Return the variable as a trend per year or per decade.

        Parameters
        ----------
        per : {"decade", "year"}
            Time unit of the trend; units become for example ``"NDVI decade$^{-1}$"``.

        Raises
        ------
        ValueError
            For any other ``per``.
        """
        if per not in PER_UNITS:
            raise ValueError(f"per must be one of {tuple(PER_UNITS)} (got {per!r}).")
        time_unit = f"{PER_UNITS[per]}$^{{-1}}$"
        units = f"{self.units} {time_unit}" if self.units else time_unit
        return replace(
            self,
            name=f"{self.name}_trend",
            long_name=f"{self.long_name} trend",
            symbol=f"{self.symbol} trend",
            units=units,
            cmap=self.anomaly_cmap,
            kind="diverging",
            vmin=None,
            vmax=None,
            standard_name=None,
            aliases=(),
        )


@lru_cache(maxsize=1)
def _bundled() -> dict[str, Variable]:
    text = resources.files("eofigs").joinpath("data/variables.json").read_text(encoding="utf-8")
    entries = json.loads(text)["variables"]
    return {
        key: Variable(name=key, **{**entry, "aliases": tuple(entry["aliases"])})
        for key, entry in entries.items()
    }


_REGISTERED: dict[str, Variable] = {}


def _library() -> dict[str, Variable]:
    return {**_bundled(), **_REGISTERED}


def _norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(text).strip().lower())


def variable_names() -> list[str]:
    """Names of all variables in the library (bundled and registered)."""
    return sorted(_library())


def variable(name: Any) -> Variable:
    """Look up a variable by name, alias or xarray attributes.

    Parameters
    ----------
    name : str, Variable or xarray.DataArray
        A library name or alias (case-insensitive, ``"NDVI"``, ``"leaf area index"``),
        a :class:`Variable` (returned unchanged), or a DataArray recognised from its
        ``standard_name``, ``long_name`` or name. For a DataArray whose ``units``
        attribute differs from the library units, the returned variable carries the
        data's units (CF strings such as ``"kg m-2 s-1"`` are written in mathtext).

    Returns
    -------
    Variable

    Raises
    ------
    ValueError
        If nothing matches; the message suggests close names.

    Examples
    --------
    >>> import eofigs
    >>> eofigs.variable("GPP").label
    'Gross primary productivity (gC m$^{-2}$ d$^{-1}$)'
    >>> eofigs.variable("ndvi").trend("decade").units
    'decade$^{-1}$'
    """
    if isinstance(name, Variable):
        return name
    if hasattr(name, "attrs") and hasattr(name, "dims"):
        return _from_dataarray(name)
    found = _find(str(name))
    if found is None:
        raise ValueError(_unknown_message(str(name)))
    return found


def _find(text: str) -> Variable | None:
    library = _library()
    key = _norm(text)
    for var in library.values():
        names = {var.name, var.long_name, *var.aliases}
        if var.standard_name:
            names.add(var.standard_name)
        if key in {_norm(n) for n in names}:
            return var
    return None


def _unknown_message(text: str) -> str:
    choices = variable_names()
    close = difflib.get_close_matches(_norm(text), choices, n=3, cutoff=0.5)
    hint = f" Did you mean {', '.join(close)}?" if close else ""
    return (
        f"Unknown variable {text!r}.{hint} Available: {', '.join(choices)}. "
        "Add your own with eofigs.register_variable()."
    )


def _from_dataarray(da: Any) -> Variable:
    attrs = da.attrs
    if attrs.get("eofigs_derived") == "trend" and attrs.get("source_variable"):
        base = _find(str(attrs["source_variable"]))
        if base is not None:
            derived = base.trend(str(attrs.get("per", "decade")))
            units = attrs.get("units")
            if units and _norm(units) != _norm(derived.units):
                return replace(derived, units=units)
            return derived
    candidates = [attrs.get("standard_name"), attrs.get("long_name"), da.name]
    for candidate in candidates:
        if candidate:
            found = _find(str(candidate))
            if found is not None:
                units = attrs.get("units")
                if units and _norm(cf_units_to_mathtext(units)) != _norm(found.units):
                    return replace(found, units=cf_units_to_mathtext(units))
                return found
    tried = [str(c) for c in candidates if c]
    raise ValueError(
        f"Could not recognise the variable from {tried or 'an unnamed DataArray'}. "
        f"Pass variable= with one of: {', '.join(variable_names())}, "
        "or register it with eofigs.register_variable()."
    )


_UNIT_TOKEN = re.compile(r"^([A-Za-z%]+)(-?\d+)$")
_UNIT_WORDS = {"degC": "$\\degree$C", "degrees_C": "$\\degree$C", "1": "", "degree": "$\\degree$"}


def cf_units_to_mathtext(units: str) -> str:
    """Write a CF/UDUNITS units string in mathtext.

    Examples
    --------
    >>> from eofigs.variables import cf_units_to_mathtext
    >>> cf_units_to_mathtext("kg m-2 s-1")
    'kg m$^{-2}$ s$^{-1}$'
    >>> cf_units_to_mathtext("gC m^-2 d^-1")
    'gC m$^{-2}$ d$^{-1}$'
    """
    if "$" in units:
        return units
    out = []
    for token in units.replace("^", "").replace("**", "").split():
        if token in _UNIT_WORDS:
            out.append(_UNIT_WORDS[token])
            continue
        match = _UNIT_TOKEN.match(token)
        if match and match.group(2) != "1":
            out.append(f"{match.group(1)}$^{{{match.group(2)}}}$")
        elif match:
            out.append(match.group(1))
        else:
            out.append(token)
    return " ".join(t for t in out if t)


def register_variable(name: str, overwrite: bool = False, **fields: Any) -> Variable:
    """Add a variable to the library, or replace one with ``overwrite=True``.

    Registered variables are found by :func:`variable` and by every recipe for the
    rest of the session. This is the only way the library changes.

    Parameters
    ----------
    name : str
        Key of the new variable.
    overwrite : bool, default False
        Replace an existing variable (bundled or registered) of the same name.
    **fields
        :class:`Variable` fields: ``long_name`` (required), ``symbol`` (defaults to the
        long name), ``units``, ``cmap``, ``anomaly_cmap``, ``kind``, ``vmin``, ``vmax``,
        ``standard_name``, ``aliases``.

    Returns
    -------
    Variable

    Raises
    ------
    ValueError
        If the name exists and ``overwrite`` is False, or a field is invalid.

    Examples
    --------
    >>> import eofigs
    >>> v = eofigs.register_variable(
    ...     "cci", long_name="Chlorophyll carotenoid index", symbol="CCI", vmin=-0.5, vmax=0.5,
    ...     overwrite=True)
    >>> eofigs.variable("CCI").long_name
    'Chlorophyll carotenoid index'
    """
    key = _norm(name).replace(" ", "_")
    if not overwrite and key in _library():
        raise ValueError(f"Variable {key!r} already exists; pass overwrite=True to replace it.")
    if "long_name" not in fields:
        raise ValueError("register_variable needs long_name=.")
    fields.setdefault("symbol", fields["long_name"])
    fields["aliases"] = tuple(fields.get("aliases", ()))
    var = Variable(name=key, **fields)
    _REGISTERED[key] = var
    return var
