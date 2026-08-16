#!/usr/bin/env Rscript
# =====================================================================
#  Tests du dashboard R Shiny.
#
#  Objectif : vérifier que la pile R tient les mêmes engagements que la
#  pile Python, sur la même base SQL.
#
#      1. le dossier R/ se charge dans n'importe quel ordre d'appel
#      2. le générateur R produit une entreprise cohérente
#      3. les requêtes répondent sur toutes les vues
#      4. l'interface (modules, graphiques, tableaux) se construit
#      5. PARITÉ : sur une base créée par Python, R lit les mêmes chiffres
#
#  Exécution :
#      Rscript tests/test_shiny.R
#      Rscript tests/test_shiny.R chemin/vers/base_python.db   (parité)
# =====================================================================

# Localise le dossier de l'application, que le test soit lancé depuis la
# racine du projet, depuis tests/ ou depuis shiny/.
SHINY_DIR <- local({
  for (candidate in c("shiny", file.path("..", "shiny"), ".")) {
    if (dir.exists(file.path(candidate, "R"))) {
      return(normalizePath(candidate, mustWork = TRUE))
    }
  }
  stop("Dossier 'shiny/' introuvable. Lancez : Rscript tests/test_shiny.R ",
       "depuis la racine du projet.", call. = FALSE)
})

# --- petit harnais ----------------------------------------------------
.results <- new.env(parent = emptyenv())
.results$passed <- 0L
.results$failed <- character(0)

check <- function(label, expr) {
  outcome <- tryCatch({
    if (isTRUE(expr)) TRUE else paste("attendu VRAI, obtenu", format(expr)[1])
  }, error = function(e) paste0(class(e)[1], ": ", conditionMessage(e)))
  if (isTRUE(outcome)) {
    .results$passed <- .results$passed + 1L
    cat(sprintf("  ✓ %s\n", label))
  } else {
    .results$failed <- c(.results$failed, label)
    cat(sprintf("  ✗ %s\n      %s\n", label, outcome))
  }
}

section <- function(title) cat(sprintf("\n  %s\n  %s\n", title, strrep("─", 62)))

# =====================================================================
section("1. Chargement du dossier R/")
# =====================================================================
# Shiny charge R/ par ordre alphabétique, dans un environnement dédié, sans
# que global.R ait forcément tourné avant. C'est exactement le scénario qui
# faisait échouer theme.R sur « objet 'THEME' introuvable ».
files <- sort(list.files(file.path(SHINY_DIR, "R"), pattern = "[.][Rr]$", full.names = TRUE))
check("le dossier R/ contient des fichiers", length(files) > 0)

isolated <- new.env(parent = globalenv())
load_errors <- character(0)
for (f in files) {
  res <- try(source(f, local = isolated, encoding = "UTF-8"), silent = TRUE)
  if (inherits(res, "try-error")) {
    load_errors <- c(load_errors, sprintf("%s : %s", basename(f),
                                          conditionMessage(attr(res, "condition"))))
  }
}
check("tous les fichiers se chargent seuls, sans global.R", length(load_errors) == 0)
if (length(load_errors)) cat("     ", paste(load_errors, collapse = "\n      "), "\n")
check("THEME est disponible après chargement", !is.null(isolated$THEME))
check("CATALOG expose les 7 métiers", length(isolated$CATALOG$types) == 7)
check("DEPARTMENTS expose les 7 entrées de navigation", length(isolated$DEPARTMENTS) == 7)

# Chargement réel, dans l'environnement global cette fois.
suppressPackageStartupMessages({
  library(DBI); library(RSQLite); library(jsonlite)
})
for (f in files) source(f, encoding = "UTF-8")

# =====================================================================
section("2. Générateur")
# =====================================================================
tmp <- file.path(tempdir(), "erp-tests")
dir.create(tmp, showWarnings = FALSE, recursive = TRUE)
on.exit(unlink(tmp, recursive = TRUE), add = TRUE)

new_db <- function(name) db_connect(file.path(tmp, paste0(name, ".db")))

generated <- list()
for (store_type in names(CATALOG$types)) {
  con <- new_db(store_type)
  ok <- try(generate_company(con, "Boutique de test", store_type,
                             history_months = 3, traffic_scale = 0.4), silent = TRUE)
  generated[[store_type]] <- if (inherits(ok, "try-error")) NULL else con
  check(sprintf("le métier « %s » se génère", store_type), !inherits(ok, "try-error"))
  if (inherits(ok, "try-error")) {
    cat("      ", conditionMessage(attr(ok, "condition")), "\n")
  }
}

for (store_type in names(generated)) {
  con <- generated[[store_type]]
  if (is.null(con)) next

  ecarts <- db_scalar(con,
    "SELECT COUNT(*) FROM products p WHERE ABS(p.stock -
       COALESCE((SELECT SUM(quantity) FROM stock_moves WHERE product_id = p.id), 0)) > 0.01")
  check(sprintf("%s : stock = somme des mouvements", store_type), ecarts == 0)

  ecarts_vente <- db_scalar(con,
    "SELECT COUNT(*) FROM sales s WHERE ABS(s.subtotal -
       COALESCE((SELECT SUM(line_total) FROM sale_items WHERE sale_id = s.id), 0)) > 0.01")
  check(sprintf("%s : sous-total = somme des lignes", store_type), ecarts_vente == 0)

  valeur <- db_scalar(con, "SELECT COALESCE(SUM(stock * cost_price), 0) FROM products")
  check(sprintf("%s : valeur de stock positive", store_type), valeur > 0)

  futur <- db_scalar(con, sprintf(
    "SELECT COUNT(*) FROM sales WHERE sale_date > '%s'", format(Sys.Date())))
  check(sprintf("%s : aucune vente dans le futur", store_type), futur == 0)
}

# =====================================================================
section("3. Triggers — la centralisation")
# =====================================================================
con <- generated[["generique"]]
product <- db_one(con, "SELECT id, stock FROM products LIMIT 1")

DBI::dbExecute(con,
  "INSERT INTO sales (ref, sold_at, sale_date, payment_method, channel, status)
   VALUES ('TEST-1', datetime('now'), date('now'), 'Espèces', 'Boutique', 'payée')")
sale_id <- db_scalar(con, "SELECT MAX(id) FROM sales")
DBI::dbExecute(con,
  "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, unit_cost, discount)
   VALUES (?, ?, 3, 1000, 600, 0)", params = list(sale_id, product$id))

check("une vente décharge le stock",
      db_scalar(con, "SELECT stock FROM products WHERE id = ?",
                list(product$id)) == product$stock - 3)
check("une vente crée un mouvement de stock",
      db_scalar(con, "SELECT COUNT(*) FROM stock_moves WHERE ref = 'TEST-1'") == 1)
tax <- db_scalar(con, "SELECT tax_rate FROM company")
check("le TTC applique la TVA",
      abs(db_scalar(con, "SELECT total FROM sales WHERE id = ?", list(sale_id)) -
          3000 * (1 + tax)) < 0.01)

stock_avant <- db_scalar(con, "SELECT stock FROM products WHERE id = ?", list(product$id))
DBI::dbExecute(con,
  "INSERT INTO purchases (ref, ordered_on, supplier_id, status)
   VALUES ('TEST-AC', date('now'), 1, 'commandée')")
purchase_id <- db_scalar(con, "SELECT MAX(id) FROM purchases")
DBI::dbExecute(con,
  "INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost)
   VALUES (?, ?, 10, 600)", params = list(purchase_id, product$id))
check("une commande non reçue laisse le stock intact",
      db_scalar(con, "SELECT stock FROM products WHERE id = ?", list(product$id)) == stock_avant)

DBI::dbExecute(con, "UPDATE purchases SET status = 'reçue', received_on = date('now')
                     WHERE id = ?", params = list(purchase_id))
check("la réception crédite le stock",
      db_scalar(con, "SELECT stock FROM products WHERE id = ?",
                list(product$id)) == stock_avant + 10)
check("la réception laisse une trace d'audit",
      db_scalar(con, "SELECT COUNT(*) FROM audit_log WHERE action = 'réception'") > 0)

# =====================================================================
section("4. Requêtes et interface")
# =====================================================================
queries <- list(
  q_departments = q_departments, q_activity = q_activity, q_sales_daily = q_sales_daily,
  q_sales_monthly = q_sales_monthly, q_sales_by_category = q_sales_by_category,
  q_top_products = q_top_products, q_sales_list = q_sales_list, q_affluence = q_affluence,
  q_products = q_products, q_stock_alerts = q_stock_alerts,
  q_stock_valuation = q_stock_valuation, q_stock_moves = q_stock_moves,
  q_suppliers = q_suppliers, q_purchases = q_purchases,
  q_purchases_monthly = q_purchases_monthly, q_reorder_plan = q_reorder_plan,
  q_customers = q_customers, q_segments = q_segments, q_dormant = q_dormant,
  q_acquisition = q_acquisition, q_employees = q_employees, q_headcount = q_headcount,
  q_payroll = q_payroll, q_financial = q_financial, q_expenses = q_expenses)

for (name in names(queries)) {
  res <- try(queries[[name]](con), silent = TRUE)
  check(sprintf("requête %s()", name),
        !inherits(res, "try-error") && is.data.frame(res))
}
kpis <- q_kpis(con, 30)
check("q_kpis() renvoie les indicateurs attendus",
      all(c("revenue", "tickets", "margin_rate", "stock_value", "net_result") %in% names(kpis)))
check("q_kpis() : chiffre d'affaires non nul", kpis$revenue > 0)

suppressPackageStartupMessages({ library(shiny); library(plotly); library(DT); library(bslib) })

check("le thème bslib se construit", inherits(erp_theme(), "bs_theme"))
check("l'écran d'accueil se construit",
      inherits(onboarding_ui("test"), c("shiny.tag", "shiny.tag.list")))
for (module in c("overview", "sales", "stock", "purchasing", "crm", "hr", "finance")) {
  builder <- get(paste0(module, "_ui"))
  res <- try(builder(module), silent = TRUE)
  check(sprintf("l'interface du module « %s » se construit", module),
        !inherits(res, "try-error"))
}

daily <- q_sales_daily(con, 30)
check("graphique en courbe",
      inherits(chart_line(fr_day(daily$sale_date), list("CA" = daily$revenue), "FCFA"), "plotly"))
categories <- q_sales_by_category(con, 30)
check("graphique de répartition",
      inherits(chart_share(categories$category, categories$revenue, "FCFA"), "plotly"))
check("graphique en barres groupées",
      inherits(chart_grouped(fr_period(q_sales_monthly(con)$period),
                             list(a = 1:3, b = 4:6), "FCFA"), "plotly"))
valuation <- q_stock_valuation(con)
check("graphique en haltères",
      inherits(chart_dumbbell(valuation$category, valuation$value, valuation$retail_value,
                              "Revient", "Vente", "FCFA"), "plotly"))
check("tableau interactif",
      inherits(erp_table(q_products(con),
                         list("Produit" = col_spec("name"),
                              "Stock" = col_spec("stock", "num", 1))), "datatables"))
check("flux d'activité", inherits(activity_feed(q_activity(con, 5), "FCFA"), "shiny.tag"))
check("tuile d'indicateur", inherits(kpi_tile("Test", "1 000"), "shiny.tag"))
check("formatage compact", fmt_compact(1234567, "FCFA") == "1,2 M FCFA")
check("libellé de période", fr_period("2026-08") == "août 2026")
check("libellé de jour", fr_day("2026-08-16") == "16/08")

# =====================================================================
section("5. Parité R / Python sur une base commune")
# =====================================================================
args <- commandArgs(trailingOnly = TRUE)
python_db <- if (length(args) > 0) args[1] else ""

if (!nzchar(python_db) || !file.exists(python_db)) {
  cat("  (ignoré : aucune base Python fournie en argument)\n")
} else {
  reference_path <- paste0(python_db, ".kpis.json")
  if (!file.exists(reference_path)) {
    cat("  (ignoré : fichier de référence", basename(reference_path), "absent)\n")
  } else {
    reference <- jsonlite::fromJSON(reference_path)
    pcon <- db_connect(python_db)
    mesure <- q_kpis(pcon, 30)

    compare <- function(label, r_value, py_value, tolerance = 0.01) {
      check(sprintf("parité — %s", label),
            abs(as.numeric(r_value) - as.numeric(py_value)) <= tolerance)
    }
    compare("chiffre d'affaires", mesure$revenue, reference$revenue)
    compare("tickets", mesure$tickets, reference$tickets)
    compare("marge brute", mesure$margin, reference$margin)
    compare("panier moyen", mesure$avg_basket, reference$avg_basket)
    compare("valeur du stock", mesure$stock_value, reference$stock_value)
    compare("alertes de stock", mesure$stock_alerts, reference$stock_alerts)
    compare("effectif", mesure$headcount, reference$headcount)
    compare("résultat du mois", mesure$net_result, reference$net_result)

    check("parité — nombre de produits",
          nrow(q_products(pcon)) == reference$products)
    check("parité — nombre de fournisseurs",
          nrow(q_suppliers(pcon)) == reference$suppliers)
    check("parité — compte de résultat mensuel",
          nrow(q_financial(pcon)) == reference$financial_months)
    DBI::dbDisconnect(pcon)
  }
}

# =====================================================================
cat(sprintf("\n  %s\n", strrep("─", 62)))
if (length(.results$failed)) {
  cat(sprintf("  %d échec(s) sur %d\n\n", length(.results$failed),
              .results$passed + length(.results$failed)))
  quit(status = 1)
}
cat(sprintf("  %d tests passés\n\n", .results$passed))
