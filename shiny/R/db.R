# =====================================================================
#  Accès à la base SQL centrale.
#
#  C'est EXACTEMENT le même fichier de base que celui utilisé par le
#  dashboard Python, l'API REST, le front web et l'application Angular :
#  shared/schema.sql décrit les tables, les triggers et les vues, et
#  chaque interface se contente de lire et d'écrire dedans.
# =====================================================================

`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

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

#' Applique shared/schema.sql (idempotent : tout est CREATE IF NOT EXISTS).
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
  invisible(TRUE)
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
