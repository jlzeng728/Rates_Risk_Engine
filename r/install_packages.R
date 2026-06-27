# Install the R packages used by pca_yield_curve.R into a project-local
# library (r/.Rlib). Run once from the project root:
#
#     Rscript r/install_packages.R
#
# pca_yield_curve.R adds r/.Rlib to .libPaths() automatically when present.

options(repos = "https://cloud.r-project.org")

LOCAL_LIB <- "r/.Rlib"
if (!dir.exists(LOCAL_LIB)) dir.create(LOCAL_LIB, recursive = TRUE)

pkgs <- c("DBI", "RSQLite", "tidyr", "dplyr", "ggplot2")
install.packages(pkgs, lib = LOCAL_LIB)

ok <- sapply(pkgs, requireNamespace, lib.loc = LOCAL_LIB, quietly = TRUE)
cat("Installed into", LOCAL_LIB, "\n")
print(ok)
if (!all(ok)) stop("Some packages failed to install")
