# =====================================================================
#  ERP Boutique — dashboard R Shiny
#  Chargement des bibliothèques, des ressources partagées et des modules.
#
#  Ce fichier est exécuté une seule fois au démarrage de l'application.
# =====================================================================

suppressPackageStartupMessages({
  library(shiny)
  library(bslib)
  library(DBI)
  library(RSQLite)
  library(jsonlite)
  library(plotly)
  library(DT)
})

options(stringsAsFactors = FALSE, scipen = 999)

# Repli si `NULL` (base R >= 4.4 le fournit, on le redéfinit pour les versions
# antérieures ; il est utilisé dès les lignes suivantes).
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

# --- Localisation des ressources partagées ---------------------------
# Shiny place le répertoire de travail sur le dossier de l'application.
APP_DIR <- getwd()
if (!dir.exists(file.path(APP_DIR, "R")) && dir.exists("shiny/R")) {
  APP_DIR <- normalizePath("shiny")
}
PROJECT_DIR <- normalizePath(file.path(APP_DIR, ".."), mustWork = FALSE)
SHARED_DIR  <- Sys.getenv("ERP_SHARED_DIR", file.path(PROJECT_DIR, "shared"))
DB_PATH     <- Sys.getenv("ERP_DB_PATH", file.path(PROJECT_DIR, "data", "erp.db"))

if (!dir.exists(SHARED_DIR)) {
  stop("Dossier partagé introuvable : ", SHARED_DIR,
       "\nDéfinissez ERP_SHARED_DIR vers le dossier 'shared/' du projet.")
}

# --- Catalogue des métiers et jetons de design (mêmes fichiers que Python)
CATALOG <- jsonlite::fromJSON(file.path(SHARED_DIR, "store_types.json"),
                              simplifyDataFrame = FALSE)
THEME   <- jsonlite::fromJSON(file.path(SHARED_DIR, "theme.json"),
                              simplifyDataFrame = FALSE)
SCHEMA_PATH <- file.path(SHARED_DIR, "schema.sql")

# --- Départements : l'axe de centralisation des données ---------------
DEPARTMENTS <- list(
  list(code = "OVERVIEW", route = "overview",   icon = "\U0001F4CA", name = "Vue d'ensemble"),
  list(code = "SALES",    route = "sales",      icon = "\U0001F9FE", name = "Ventes"),
  list(code = "STOCK",    route = "stock",      icon = "\U0001F4E6", name = "Stock"),
  list(code = "PURCH",    route = "purchasing", icon = "\U0001F69A", name = "Achats"),
  list(code = "CRM",      route = "crm",        icon = "\U0001F465", name = "Clients"),
  list(code = "HR",       route = "hr",         icon = "\U0001F9D1", name = "Ressources humaines"),
  list(code = "FIN",      route = "finance",    icon = "\U0001F4B0", name = "Finance")
)

# --- Sources des modules ---------------------------------------------
for (file in list.files(file.path(APP_DIR, "R"), pattern = "[.]R$", full.names = TRUE)) {
  source(file, local = FALSE, encoding = "UTF-8")
}
