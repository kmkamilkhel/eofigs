# Citation

## How to cite

If eofigs helped with a figure in your work, please cite the software. eofigs is archived on
Zenodo, which gives it two kinds of DOI:

| DOI | Refers to | Use it |
|---|---|---|
| [10.5281/zenodo.24053760](https://doi.org/10.5281/zenodo.24053760) | all versions (always resolves to the newest release) | to refer to eofigs in general |
| [10.5281/zenodo.24143866](https://doi.org/10.5281/zenodo.24143866) | version 0.2.0 | to cite the version you used, for reproducibility |
| [10.5281/zenodo.24084780](https://doi.org/10.5281/zenodo.24084780) | version 0.1.1 | if you used 0.1.1 |
| [10.5281/zenodo.24053761](https://doi.org/10.5281/zenodo.24053761) | version 0.1.0 | if you used 0.1.0 |

Each new release gets its own version DOI, listed on the
[Zenodo record](https://doi.org/10.5281/zenodo.24053760). `eofigs.__version__` tells you which
version you have.

> Mehmood, K. (2026). *eofigs: analysis-aware, publication-ready figures for Earth
> observation research* (Version 0.2.0) [Computer software]. Zenodo.
> <https://doi.org/10.5281/zenodo.24143866>

```bibtex
@software{mehmood_eofigs_2026,
  author    = {Mehmood, Kaleem},
  title     = {eofigs: analysis-aware, publication-ready figures for Earth observation research},
  year      = {2026},
  version   = {0.2.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.24143866},
  url       = {https://github.com/kmkamilkhel/eofigs},
}
```

The metadata are also in
[CITATION.cff](https://github.com/kmkamilkhel/eofigs/blob/main/CITATION.cff), which GitHub
offers as APA and BibTeX under "Cite this repository" (with the all-versions DOI).

## Methods and data

Cite the methods behind a recipe where your text relies on them, for example:

- Theil–Sen slopes and the Mann–Kendall test (`trend`, `trend_map`): Sen (1968), Kendall (1975);
- the orientation and fitted line of `accuracy_scatter`: Piñeiro et al. (2008);
- the NMAD of DEM errors: Höhle and Höhle (2009).

The data in the gallery keep their own licences and citations, listed in
[DATA_LICENSES.md](https://github.com/kmkamilkhel/eofigs/blob/main/DATA_LICENSES.md).
