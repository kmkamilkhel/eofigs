# Ready-to-use environment with eofigs and its geospatial stack (conda-forge).
FROM mambaorg/micromamba:2.10.0-ubuntu24.04

LABEL org.opencontainers.image.source="https://github.com/kmkamilkhel/eofigs" \
      org.opencontainers.image.url="https://kmkamilkhel.github.io/eofigs/" \
      org.opencontainers.image.title="eofigs" \
      org.opencontainers.image.description="Analysis-aware, publication-ready figures for Earth observation research, with cartopy, rioxarray and geopandas preinstalled." \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Kaleem Mehmood"

# Metric-compatible free fonts for journal presets (Times New Roman and Arial substitutes)
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig fonts-liberation fonts-texgyre \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

USER $MAMBA_USER
RUN micromamba install -y -n base -c conda-forge --override-channels \
        python=3.13 numpy pandas xarray scipy "matplotlib-base>=3.9" cartopy cmcrameri \
        matplotlib-scalebar rioxarray geopandas shapely pyproj pypdf pip \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml README.md LICENSE /tmp/eofigs/
COPY --chown=$MAMBA_USER:$MAMBA_USER src /tmp/eofigs/src
RUN pip install --no-cache-dir --no-deps /tmp/eofigs \
    && rm -rf /tmp/eofigs \
    && python -c "import eofigs, cartopy, rioxarray, geopandas, cmcrameri, matplotlib_scalebar, pypdf; print('eofigs', eofigs.__version__)"

WORKDIR /work
CMD ["python"]
