# =====================================================================
#  Accès à la base SQL centrale.
#
#  C'est EXACTEMENT le même fichier de base que celui utilisé par le
#  dashboard Python, l'API REST, le front web et l'application Angular :
#  shared/schema.sql décrit les tables, les triggers et les vues, et
#  chaque interface se contente de lire et d'écrire dedans.
# =====================================================================

#' Ouvre (et prépare) la connexion à la base centrale.
db_connect <- function(path = DB_PATH) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  con <- DBI::dbConnect(RSQLite::SQLite(), path)
  DBI::dbExecute(con, "PRAGMA foreign_keys = ON")
  DBI::dbExecute(con, "PRAGMA journal_mode = WAL")
  DBI::dbExecute(con, "PRAGMA busy_timeout = 5000")
  db_init_schema(con)
  con
}

#' Applique shared/schema.sql puis les migrations des bases existantes.
db_init_schema <- function(con) {
  sql <- paste(readLines(SCHEMA_PATH, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
  # Découpe en instructions : les triggers contiennent des « ; » internes,
  # on s'appuie donc sur les marqueurs BEGIN ... END.
  statements <- db_split_sql(sql)
  for (statement in statements) {
    trimmed <- trimws(statement)
    if (nchar(trimmed) == 0) next
    try(DBI::dbExecute(con, trimmed), silent = TRUE)
  }
  db_apply_migrations(con)
  invisible(TRUE)
}

#' Colonnes d'une table ; vecteur vide si la table n'existe pas.
db_columns <- function(con, table) {
  info <- try(DBI::dbGetQuery(con, sprintf("PRAGMA table_info(%s)", table)), silent = TRUE)
  if (inherits(info, "try-error") || nrow(info) == 0) return(character(0))
  info$name
}

#' Met à niveau une base déjà remplie, d'après shared/migrations.json.
#'
#' schema.sql ne contient que des CREATE ... IF NOT EXISTS : il crée une base
#' neuve mais laisse intacte une base existante. Sans cette étape, une base
#' créée par une version antérieure garderait ses anciennes colonnes et les
#' écritures échoueraient (« table company has no column named ... »).
#' Chaque opération n'agit que si l'ancien état est présent : rejouable sans
#' risque.
db_apply_migrations <- function(con) {
  if (!file.exists(MIGRATIONS_PATH)) return(invisible(character(0)))
  plan <- jsonlite::fromJSON(MIGRATIONS_PATH, simplifyDataFrame = FALSE)
  appliquees <- character(0)

  for (regle in plan$colonnes_renommees %||% list()) {
    colonnes <- db_columns(con, regle$table)
    if (regle$de %in% colonnes && !(regle$vers %in% colonnes)) {
      DBI::dbExecute(con, sprintf('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"',
                                  regle$table, regle$de, regle$vers))
      appliquees <- c(appliquees, sprintf("%s.%s -> %s", regle$table, regle$de, regle$vers))
    }
  }

  for (regle in plan$colonnes_ajoutees %||% list()) {
    colonnes <- db_columns(con, regle$table)
    if (length(colonnes) > 0 && !(regle$colonne %in% colonnes)) {
      DBI::dbExecute(con, sprintf('ALTER TABLE "%s" ADD COLUMN "%s" %s',
                                  regle$table, regle$colonne, regle$type))
      appliquees <- c(appliquees, sprintf("%s.%s ajoutée", regle$table, regle$colonne))
    }
  }

  if (length(appliquees)) {
    message("Base mise à niveau : ", paste(appliquees, collapse = ", "))
  }
  invisible(appliquees)
}

#' Découpe un script SQL en instructions, en préservant les corps de triggers.
db_split_sql <- function(sql) {
  lines <- strsplit(sql, "\n", fixed = TRUE)[[1]]
  lines <- lines[!grepl("^\\s*--", lines)]
  statements <- character(0)
  buffer <- character(0)
  in_block <- FALSE
  for (line in lines) {
    buffer <- c(buffer, line)
    if (grepl("\\bBEGIN\\b", line, ignore.case = TRUE) &&
        grepl("CREATE\\s+TRIGGER", paste(buffer, collapse = " "), ignore.case = TRUE)) {
      in_block <- TRUE
    }
    if (in_block) {
      if (grepl("^\\s*END\\s*;", line, ignore.case = TRUE)) {
        statements <- c(statements, paste(buffer, collapse = "\n"))
        buffer <- character(0)
        in_block <- FALSE
      }
    } else if (grepl(";\\s*$", line)) {
      statements <- c(statements, paste(buffer, collapse = "\n"))
      buffer <- character(0)
    }
  }
  if (length(buffer)) statements <- c(statements, paste(buffer, collapse = "\n"))
  statements
}

#' Requête paramétrée renvoyant un data.frame.
db_query <- function(con, sql, params = NULL) {
  if (is.null(params)) DBI::dbGetQuery(con, sql) else DBI::dbGetQuery(con, sql, params = params)
}

#' Première valeur de la première colonne, avec valeur de repli.
db_scalar <- function(con, sql, params = NULL, default = 0) {
  result <- db_query(con, sql, params)
  if (nrow(result) == 0 || is.na(result[[1]][1])) default else result[[1]][1]
}

#' Ligne unique sous forme de liste (NULL si aucune).
db_one <- function(con, sql, params = NULL) {
  result <- db_query(con, sql, params)
  if (nrow(result) == 0) NULL else as.list(result[1, , drop = FALSE])
}

#' L'entreprise est-elle configurée ?
db_is_configured <- function(con) {
  tables <- DBI::dbListTables(con)
  if (!"company" %in% tables) return(FALSE)
  db_scalar(con, "SELECT COUNT(*) FROM company") > 0
}

db_company <- function(con) db_one(con, "SELECT * FROM company WHERE id = 1")

#' Journalise une action inter-départements.
db_log <- function(con, department, entity, action, entity_id = NA, detail = "") {
  DBI::dbExecute(
    con,
    "INSERT INTO audit_log (department, entity, entity_id, action, detail)
     VALUES (?, ?, ?, ?, ?)",
    params = list(department, entity, entity_id, action, detail)
  )
  invisible(TRUE)
}

#' Vide toutes les tables métier.
db_reset <- function(con) {
  tables <- c("sale_items", "sales", "purchase_items", "purchases", "stock_moves",
              "expenses", "payroll", "audit_log", "products", "categories",
              "suppliers", "customers", "employees", "departments", "company", "app_meta")
  DBI::dbExecute(con, "PRAGMA foreign_keys = OFF")
  for (table in tables) {
    if (table %in% DBI::dbListTables(con)) {
      DBI::dbExecute(con, paste0("DELETE FROM ", table))
    }
  }
  try(DBI::dbExecute(con, "DELETE FROM sqlite_sequence"), silent = TRUE)
  DBI::dbExecute(con, "PRAGMA foreign_keys = ON")
  invisible(TRUE)
}
