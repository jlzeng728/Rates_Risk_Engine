# Principal Component Analysis of Yield Curve Changes
# ===================================================
# Decompose daily changes in the par yield curve into level, slope, and
# curvature factors via prcomp, persist the factor loadings and variance
# explained to SQLite, and render the loadings figure.

# Use the project-local package library if present (created by
# r/install_packages.R); otherwise fall back to the default user library.
LOCAL_LIB <- "r/.Rlib"
if (dir.exists(LOCAL_LIB)) .libPaths(c(LOCAL_LIB, .libPaths()))

suppressMessages({
  library(DBI)
  library(RSQLite)
  library(tidyr)
  library(dplyr)
  library(ggplot2)
})

DB_PATH <- "data/yield_curve.db"
FIG_PATH <- "figures/03_pca_loadings.png"

# Exclude the 1-month money-market tenor: its idiosyncratic volatility is a
# different regime from the term structure and obscures the level factor.
PCA_MIN_TENOR <- 0.2

con <- dbConnect(SQLite(), DB_PATH)
yc <- dbGetQuery(con, "SELECT date, tenor, par_yield FROM yield_curves ORDER BY date, tenor")
yc <- yc[yc$tenor >= PCA_MIN_TENOR, ]

# Reshape to a date x tenor matrix and take first differences of the yields.
wide <- yc %>%
  pivot_wider(names_from = tenor, values_from = par_yield) %>%
  arrange(date)

dY <- as.matrix(wide[, -1])
dY <- diff(dY)
dY <- dY[complete.cases(dY), ]
tenors <- as.numeric(colnames(dY))

cat(sprintf("PCA input: %d daily changes across %d tenors\n", nrow(dY), ncol(dY)))

# PCA on the covariance of curve changes (no scaling: keep basis-point units).
pca <- prcomp(dY, center = TRUE, scale. = FALSE)
eig <- pca$sdev^2
explained <- eig / sum(eig)

cat(sprintf("PC1-3 explained: %.1f%% %.1f%% %.1f%% (cumulative %.1f%%)\n",
            100 * explained[1], 100 * explained[2], 100 * explained[3],
            100 * sum(explained[1:3])))

# Fix loading signs so the factors are interpretable across runs:
# PC1 positive (level), PC2 increasing in tenor (slope), PC3 convex (curvature).
orient <- function(v, ref) if (sum(v * ref) < 0) -v else v
centered <- tenors - mean(tenors)
pc1 <- orient(pca$rotation[, 1], rep(1, length(tenors)))
pc2 <- orient(pca$rotation[, 2], centered)
pc3 <- orient(pca$rotation[, 3], centered^2 - mean(centered^2))

factors <- data.frame(tenor = tenors, pc1 = pc1, pc2 = pc2, pc3 = pc3)
variance <- data.frame(
  pc = seq_along(eig),
  eigenvalue = eig,
  explained = explained,
  cumulative = cumsum(explained)
)

invisible(dbExecute(con, "DELETE FROM pca_factors"))
dbWriteTable(con, "pca_factors", factors, append = TRUE)
invisible(dbExecute(con, "DELETE FROM pca_variance"))
dbWriteTable(con, "pca_variance", variance[1:min(6, nrow(variance)), ], append = TRUE)
invisible(dbDisconnect(con))

# Loadings figure.
plot_df <- factors %>%
  pivot_longer(-tenor, names_to = "factor", values_to = "loading") %>%
  mutate(factor = recode(factor,
                         pc1 = sprintf("PC1 - Level (%.0f%%)", 100 * explained[1]),
                         pc2 = sprintf("PC2 - Slope (%.0f%%)", 100 * explained[2]),
                         pc3 = sprintf("PC3 - Curvature (%.0f%%)", 100 * explained[3])))

p <- ggplot(plot_df, aes(tenor, loading, colour = factor)) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey50") +
  geom_line(linewidth = 1.1) +
  geom_point(size = 2) +
  scale_colour_manual(values = c("#0072B2", "#D55E00", "#009E73")) +
  labs(title = "Yield Curve PCA - Level / Slope / Curvature",
       x = "Tenor (years)", y = "Factor loading", colour = NULL) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

ggsave(FIG_PATH, p, width = 9, height = 5.5, dpi = 300)
cat(sprintf("Saved %s\n", FIG_PATH))
