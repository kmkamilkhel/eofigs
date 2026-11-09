# Reference values for the seasonal Mann-Kendall tests in tests/test_stats.py.
#
# Three monthly series (2001-2015) are built from a deterministic formula that the tests
# rebuild in Python. The values printed here are stored in the tests as constants, so the
# test suite does not need R. Packages: trend (smk.test, csmk.test, sea.sens.slope) and
# rkt (rkt, with and without the Hirsch-Slack correction).
#
# Run: Rscript docs/scripts/seasonal_mk_reference.R

suppressMessages({
  library(trend)
  library(rkt)
})

series <- function(kind) {
  k <- 0:179
  year <- k %/% 12
  month <- k %% 12 + 1
  noise <- ((k * 7919) %% 101) / 101 - 0.5
  year_effect <- ((year * 104729) %% 97) / 97 - 0.5  # shared by all months of a year
  slope <- if (kind == "none") 0 else 0.003
  x <- round(0.5 + 0.2 * sin(2 * pi * (month - 1) / 12) + slope * year + 0.05 * noise +
               0.03 * year_effect, 3)
  if (kind == "gaps") x[(k * 31) %% 17 == 0] <- NA
  list(x = x, year = 2001 + year, month = month)
}

show <- function(name, value) cat(sprintf("%s = %.12g\n", name, value))

for (kind in c("trend", "none", "gaps")) {
  s <- series(kind)
  cat(sprintf("# %s\n", kind))
  fractional <- s$year + (s$month - 0.5) / 12
  plain <- rkt(fractional, s$x, s$month, correct = FALSE)
  corrected <- rkt(s$year, s$x, s$month, correct = TRUE)
  show("rkt_S", plain$S)
  show("rkt_varS", plain$varS)
  show("rkt_p", plain$sl)
  show("rkt_slope", plain$B)
  show("rkt_varS_corrected", corrected$varS.corrected)
  show("rkt_p_corrected", corrected$sl.corrected)
  if (kind != "gaps") {
    x <- ts(s$x, start = c(2001, 1), frequency = 12)
    smk <- smk.test(x)
    csmk <- csmk.test(x)
    show("trend_smk_S", smk$estimates[["S"]])
    show("trend_smk_varS", smk$estimates[["varS"]])
    show("trend_smk_p", smk$p.value)
    show("trend_csmk_varS", csmk$estimates[["varS"]])
    show("trend_sea_sens_slope", sea.sens.slope(x))
  }
}
cat(sprintf("# R %s, trend %s, rkt %s\n", getRversion(), packageVersion("trend"),
            packageVersion("rkt")))
