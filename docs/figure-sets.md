# Figure sets

A figure set numbers, saves and checks all figures of one manuscript in one folder.

```python
import eofigs

eofigs.set_style("elsevier", font="serif")
figs = eofigs.figure_set("manuscript/figures")

figs.add("study_area", fig1, caption="Study area and plots.")  # Fig01_study_area.pdf/.tiff
figs.add("ndvi_trend", fig2, caption="NDVI trend 2000-2024.")  # Fig02_ndvi_trend...
figs.add("accuracy", fig3, supplementary=True)  # FigS01_accuracy...
figs.add("scatter", fig4, art="line")  # line art at 1000 dpi

figs.order(["ndvi_trend", "study_area", "scatter"])  # renumbers and renames the files
```

- Files are named `Fig01_<name>` and `FigS01_<name>` in the journal's formats; reordering
  renames them.
- Adding a name again **replaces** that figure under the same number, so the folder never
  keeps an outdated figure after the analysis changes. Use `exists()` (below) to skip
  figures on purpose.
- `figures_manifest.csv` lists every figure: label (`Fig. 1`, `Fig. S1`), files, printed size
  in mm, resolution, artwork type, check result with any problems, and caption. It is
  rewritten after every change.
- Opening the same folder again continues from the manifest. In long notebooks, skip
  figures that are already saved:

```python
if not figs.exists("ndvi_trend"):
    fig2 = make_trend_figure()  # expensive
    figs.add("ndvi_trend", fig2)
```
