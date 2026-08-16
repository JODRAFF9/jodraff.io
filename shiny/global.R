# =====================================================================
#  ERP Boutique, dashboard R Shiny
#  Amorçage : dépendances, puis chargement des modules.
#
#  Les ressources partagées (catalogue des métiers, jetons de design,
#  chemins) vivent dans R/aaa_shared.R, qui ne dépend de rien et se charge
#  toujours en premier, que ce soit Shiny qui charge le dossier R/
#  automatiquement (depuis Shiny 1.5) ou la boucle ci-dessous.
# =====================================================================

# --- 1. Dépendances ---------------------------------------------------
# Les paquets manquants sont installés automatiquement : lancer
# `shiny::runApp()` sur une machine neuve suffit. Pour désactiver ce
# comportement (serveur de production, image figée), définir
# ERP_AUTO_INSTALL=0 dans l'environnement.
ERP_PACKAGES <- c("shiny", "bslib", "DBI", "RSQLite", "jsonlite", "plotly", "DT")

local({
  missing <- ERP_PACKAGES[!vapply(ERP_PACKAGES, requireNamespace, TRUE, quietly = TRUE)]
  if (length(missing) == 0) return(invisible(NULL))

  if (identical(Sys.getenv("ERP_AUTO_INSTALL", "1"), "0")) {
    stop("Paquets R manquants : ", paste(missing, collapse = ", "),
         "\nInstallez-les avec : Rscript shiny/install.R", call. = FALSE)
  }

  message("Installation des paquets manquants : ", paste(missing, collapse = ", "))
  repos <- getOption("repos")
  if (is.null(repos[["CRAN"]]) || repos[["CRAN"]] == "@CRAN@") {
    repos["CRAN"] <- "https://cloud.r-project.org"
  }
  install.packages(missing, repos = repos, quiet = TRUE)

  still_missing <- missing[!vapply(missing, requireNamespace, TRUE, quietly = TRUE)]
  if (length(still_missing)) {
    stop("Installation impossible pour : ", paste(still_missing, collapse = ", "),
         "\nInstallez-les manuellement : Rscript shiny/install.R", call. = FALSE)
  }
})

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

# --- 2. Modules -------------------------------------------------------
# Les fichiers du dossier R/ sont chargés dans l'ordre alphabétique
# (aaa_shared.R en premier, car theme.R a besoin de THEME dès son
# évaluation). Si Shiny les a déjà chargés, les sourcer à nouveau ne fait
# que redéfinir des objets identiques.
local({
  app_dir <- getwd()
  if (!dir.exists(file.path(app_dir, "R")) && dir.exists(file.path(app_dir, "shiny", "R"))) {
    app_dir <- file.path(app_dir, "shiny")
  }
  files <- sort(list.files(file.path(app_dir, "R"), pattern = "[.][Rr]$", full.names = TRUE))
  if (length(files) == 0) {
    stop("Aucun fichier trouvé dans le dossier R/ de l'application.\n",
         "Lancez l'application depuis le dossier 'shiny/' du projet : ",
         "setwd('.../jodraff/shiny') puis shiny::runApp()", call. = FALSE)
  }
  for (file in files) {
    source(file, local = globalenv(), encoding = "UTF-8")
  }
})
