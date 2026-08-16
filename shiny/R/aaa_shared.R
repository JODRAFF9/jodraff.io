# =====================================================================
#  Ressources partagées — chargées AVANT tout le reste.
#
#  Le nom du fichier commence par « aaa_ » à dessein : Shiny charge les
#  fichiers du dossier R/ par ordre alphabétique, et `theme.R` a besoin de
#  THEME dès son évaluation. Ce fichier ne dépend de rien : il peut donc
#  être chargé par Shiny (chargement automatique du dossier R/) comme par
#  global.R, dans n'importe quel ordre et n'importe quel environnement.
# =====================================================================

# Base R >= 4.4 fournit `%||%` ; on le redéfinit pour les versions antérieures.
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

#' Dossier de l'application Shiny.
#'
#' Shiny place le répertoire de travail sur le dossier de l'application ;
#' on gère aussi le cas d'un lancement depuis la racine du projet.
erp_app_dir <- function() {
  here <- getwd()
  if (dir.exists(file.path(here, "R")) && file.exists(file.path(here, "app.R"))) {
    return(here)
  }
  if (dir.exists(file.path(here, "shiny", "R"))) {
    return(normalizePath(file.path(here, "shiny"), mustWork = FALSE))
  }
  here
}

#' Dossier `shared/` : catalogue des métiers, schéma SQL, jetons de design.
erp_shared_dir <- function() {
  from_env <- Sys.getenv("ERP_SHARED_DIR", "")
  if (nzchar(from_env)) return(from_env)
  candidates <- c(
    file.path(erp_app_dir(), "..", "shared"),   # disposition normale du dépôt
    file.path(erp_app_dir(), "shared"),         # ressources copiées dans l'app
    file.path(getwd(), "shared")
  )
  for (path in candidates) {
    if (dir.exists(path)) return(normalizePath(path, mustWork = FALSE))
  }
  stop("Dossier 'shared/' introuvable (cherché : ",
       paste(normalizePath(candidates, mustWork = FALSE), collapse = " ; "),
       ").\nLancez l'application depuis le dossier 'shiny/' du projet, ",
       "ou définissez la variable d'environnement ERP_SHARED_DIR.",
       call. = FALSE)
}

# Cache des ressources JSON : elles ne sont lues qu'une fois par session.
.erp_cache <- new.env(parent = emptyenv())

#' Lit (et mémorise) un fichier JSON du dossier partagé.
erp_resource <- function(filename) {
  if (!is.null(.erp_cache[[filename]])) return(.erp_cache[[filename]])
  path <- file.path(erp_shared_dir(), filename)
  if (!file.exists(path)) {
    stop("Ressource partagée introuvable : ", path, call. = FALSE)
  }
  value <- jsonlite::fromJSON(path, simplifyDataFrame = FALSE)
  .erp_cache[[filename]] <- value
  value
}

# --- Ressources exposées au reste de l'application ---------------------
CATALOG     <- erp_resource("store_types.json")   # métiers, devises, segments
THEME       <- erp_resource("theme.json")         # jetons de design
SCHEMA_PATH <- file.path(erp_shared_dir(), "schema.sql")
DB_PATH     <- Sys.getenv(
  "ERP_DB_PATH",
  file.path(normalizePath(file.path(erp_app_dir(), ".."), mustWork = FALSE),
            "data", "erp.db"))

# --- Départements : l'axe de centralisation des données ----------------
DEPARTMENTS <- list(
  list(code = "OVERVIEW", route = "overview",   icon = "\U0001F4CA", name = "Vue d'ensemble"),
  list(code = "SALES",    route = "sales",      icon = "\U0001F9FE", name = "Ventes"),
  list(code = "STOCK",    route = "stock",      icon = "\U0001F4E6", name = "Stock"),
  list(code = "PURCH",    route = "purchasing", icon = "\U0001F69A", name = "Achats"),
  list(code = "CRM",      route = "crm",        icon = "\U0001F465", name = "Clients"),
  list(code = "HR",       route = "hr",         icon = "\U0001F9D1", name = "Ressources humaines"),
  list(code = "FIN",      route = "finance",    icon = "\U0001F4B0", name = "Finance")
)
