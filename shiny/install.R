# =====================================================================
#  Installation des dépendances R du dashboard.
#
#      Rscript install.R
#
#  La base de données est SQLite : aucun serveur à installer.
# =====================================================================

packages <- c(
  "shiny",     # socle applicatif
  "bslib",     # thème Bootstrap 5, page_navbar, cartes
  "DBI",       # interface base de données
  "RSQLite",   # pilote SQLite (embarqué)
  "jsonlite",  # lecture de shared/store_types.json et shared/theme.json
  "plotly",    # graphiques interactifs
  "DT"         # tableaux triables et filtrables
)

missing <- packages[!packages %in% rownames(installed.packages())]

if (length(missing) == 0) {
  message("Toutes les dépendances sont déjà installées.")
} else {
  message("Installation de : ", paste(missing, collapse = ", "))
  install.packages(missing, repos = "https://cloud.r-project.org")
}

# Vérification
for (package in packages) {
  ok <- requireNamespace(package, quietly = TRUE)
  message(sprintf("  %-10s %s", package, if (ok) "✓" else "✗ MANQUANT"))
}

message("\nLancement du dashboard :")
message("  Rscript -e \"shiny::runApp('.', port = 3838, launch.browser = FALSE)\"")
message("  puis ouvrez http://127.0.0.1:3838")
