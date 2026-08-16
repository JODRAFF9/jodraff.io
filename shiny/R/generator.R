# =====================================================================
#  Générateur d'entreprise (version R, vectorisée).
#
#  Même logique que python/erp/generator.py : à partir du type de boutique
#  et de son nom, on construit tout l'ERP dans la base SQL centrale.
#  Les triggers SQL se chargent ensuite de propager chaque écriture d'un
#  département vers les autres.
# =====================================================================

WEEKDAY_FACTOR <- c(0.95, 0.82, 0.86, 0.92, 0.98, 1.22, 1.45)  # dimanche -> samedi
CHANNELS       <- c("Boutique", "Téléphone", "Livraison", "En ligne")
CHANNEL_W      <- c(0.78, 0.09, 0.08, 0.05)
PAYMENT_W      <- c(0.42, 0.28, 0.14, 0.08, 0.08)

#' Arrondi commercial (multiple de 5 en devise sans décimale).
round_price <- function(value, decimals) {
  if (decimals == 0) pmax(5, round(value / 5) * 5) else round(value, decimals)
}

slug <- function(text, length = 3) {
  clean <- toupper(gsub("[^A-Za-z0-9]", "", iconv(text, to = "ASCII//TRANSLIT")))
  substr(paste0(clean, "XXX"), 1, length)
}

#' Quantité vendue par ligne, corrélée à la gamme de prix.
pick_quantity <- function(n, base_price) {
  ifelse(
    base_price >= 40000, sample(c(1, 2), n, TRUE, c(.95, .05)),
    ifelse(base_price >= 12000, sample(c(1, 2, 3), n, TRUE, c(.86, .11, .03)),
    ifelse(base_price >= 3000,  sample(c(1, 2, 3, 4), n, TRUE, c(.68, .22, .07, .03)),
    ifelse(base_price >= 800,   sample(c(1, 2, 3, 4, 6), n, TRUE, c(.46, .27, .13, .09, .05)),
                                sample(c(1, 2, 3, 4, 6, 12), n, TRUE, c(.30, .26, .16, .14, .10, .04))))))
}

#' Crée l'ERP complet d'une boutique. Retourne un résumé chiffré.
#'
#' @param progress fonction (message, valeur 0-1) pour la barre de progression Shiny.
generate_company <- function(con, name, store_type,
                             currency = "XOF", city = "Abidjan",
                             country = "Côte d'Ivoire", history_months = 12,
                             traffic_scale = 1, seed = 20240, progress = NULL) {

  stopifnot(nzchar(trimws(name)))
  spec <- CATALOG$types[[store_type]]
  if (is.null(spec)) stop("Type de boutique inconnu : ", store_type)

  currencies <- CATALOG$currencies
  cur <- Filter(function(c) c$code == currency, currencies)[[1]]
  scale <- cur$scale
  decimals <- cur$decimals

  set.seed(seed)
  step <- function(message, value) if (!is.null(progress)) progress(message, value)

  step("Réinitialisation de la base centrale…", 0.03)
  db_reset(con)

  today <- Sys.Date()
  start <- as.Date(format(today - round(history_months * 30.44), "%Y-%m-01"))

  # ---- 1. Entreprise & départements ----------------------------------
  step("Création de l'entreprise…", 0.07)
  DBI::dbExecute(con,
    "INSERT INTO company (id, name, store_type, store_label, currency, currency_sym,
                          tax_rate, city, country, opened_on, logo_emoji)
     VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    params = list(trimws(name), store_type, spec$label, cur$code, cur$symbol,
                  spec$tax_rate, city, country, format(start), spec$icon))

  DBI::dbAppendTable(con, "departments", data.frame(
    code     = vapply(DEPARTMENTS, `[[`, "", "code"),
    name     = vapply(DEPARTMENTS, `[[`, "", "name"),
    icon     = vapply(DEPARTMENTS, `[[`, "", "icon"),
    position = seq_along(DEPARTMENTS) - 1L
  ))

  # ---- 2. Fournisseurs ------------------------------------------------
  step("Enregistrement des fournisseurs…", 0.11)
  suppliers <- unlist(spec$suppliers)
  n_sup <- length(suppliers)
  DBI::dbAppendTable(con, "suppliers", data.frame(
    name           = suppliers,
    contact_name   = person_names(n_sup),
    phone          = phone_numbers(n_sup),
    email          = paste0("contact@", tolower(vapply(suppliers, slug, "", 8)), ".com"),
    lead_time_days = sample(c(3, 5, 7, 10, 14, 21), n_sup, TRUE),
    rating         = round(runif(n_sup, 3.1, 5), 1)
  ))
  supplier_ids <- db_query(con, "SELECT id FROM suppliers ORDER BY id")$id

  # ---- 3. Rayons & catalogue produits ---------------------------------
  step("Construction du catalogue produits…", 0.17)
  cat_names <- vapply(spec$categories, `[[`, "", "name")
  DBI::dbAppendTable(con, "categories", data.frame(
    name = cat_names, margin_target = rep(spec$margin_target, length(cat_names))))
  cat_ids <- db_query(con, "SELECT id, name FROM categories ORDER BY id")

  products <- do.call(rbind, lapply(seq_along(spec$categories), function(k) {
    category <- spec$categories[[k]]
    items <- category$products
    cat_weight <- runif(1, 0.7, 1.4)
    data.frame(
      sku        = sprintf("%s-%03d", slug(category$name), seq_along(items)),
      name       = vapply(items, `[[`, "", "name"),
      category_id = cat_ids$id[k],
      unit       = vapply(items, `[[`, "", "unit"),
      base_cost  = vapply(items, function(p) as.numeric(p$cost), 0),
      base_price = vapply(items, function(p) as.numeric(p$price), 0),
      cat_weight = cat_weight
    )
  }))
  n_prod <- nrow(products)
  products$cost_price  <- round_price(products$base_cost * scale, decimals)
  products$sale_price  <- round_price(products$base_price * scale, decimals)
  products$supplier_id <- sample(supplier_ids, n_prod, TRUE)
  products$weight <- products$cat_weight * runif(n_prod, 0.45, 1.8) /
                     pmax(1, (products$base_price / 5000) ^ 0.45)
  products$share  <- products$weight / sum(products$weight)

  DBI::dbAppendTable(con, "products", data.frame(
    sku = products$sku, name = products$name, category_id = products$category_id,
    supplier_id = products$supplier_id, unit = products$unit,
    cost_price = products$cost_price, sale_price = products$sale_price,
    stock = 0, reorder_point = 0))
  products$id <- db_query(con, "SELECT id FROM products ORDER BY id")$id

  # ---- 4. Personnel ----------------------------------------------------
  step("Constitution de l'équipe…", 0.23)
  roles <- spec$roles
  staff <- do.call(rbind, lapply(roles, function(role) {
    headcount <- if (identical(role$department, "Direction")) 1L else sample(1:3, 1)
    data.frame(
      name       = person_names(headcount),
      role       = rep(role$title, headcount),
      department = rep(role$department, headcount),
      salary     = round_price(role$salary * scale * runif(headcount, 0.9, 1.15), decimals),
      phone      = phone_numbers(headcount),
      hired_on   = format(today - sample(60:1800, headcount, TRUE)),
      active     = 1L
    )
  }))
  DBI::dbAppendTable(con, "employees", staff)
  employees <- db_query(con, "SELECT id, department FROM employees ORDER BY id")
  sellers <- employees$id[employees$department %in% c("Ventes", "Direction")]
  if (!length(sellers)) sellers <- employees$id

  # ---- 5. Clients -------------------------------------------------------
  step("Import du fichier clients…", 0.29)
  segments <- CATALOG$customer_segments
  seg_names   <- vapply(segments, `[[`, "", "name")
  seg_weights <- vapply(segments, function(s) as.numeric(s$weight), 0)
  seg_factors <- vapply(segments, function(s) as.numeric(s$basket_factor), 0)
  names(seg_factors) <- seg_names

  n_cust <- max(40, round(spec$daily_tickets * 1.6))
  cust_segments <- sample(seg_names, n_cust, TRUE, prob = seg_weights)
  persons <- person_names(n_cust)
  labels <- ifelse(
    cust_segments %in% c("Particulier", "Fidèle"), persons,
    paste(sample(c("Ets", "SARL", "Groupe", "Coop."), n_cust, TRUE),
          vapply(strsplit(persons, " "), function(p) p[2], "")))
  DBI::dbAppendTable(con, "customers", data.frame(
    name    = labels,
    segment = cust_segments,
    phone   = phone_numbers(n_cust),
    email   = paste0(tolower(vapply(persons, slug, "", 12)), "@mail.com"),
    city    = sample(c(rep(city, 3), "Bouaké", "Yamoussoukro", "San-Pédro", "Korhogo"),
                     n_cust, TRUE),
    created_at = format(start - sample(0:900, n_cust, TRUE))))
  customers <- db_query(con, "SELECT id, segment FROM customers ORDER BY id")
  customers$factor <- unname(seg_factors[customers$segment])

  # ---- 6. Stock initial -------------------------------------------------
  step("Réception du stock initial…", 0.35)
  basket_lines  <- unlist(spec$basket_lines)
  avg_lines     <- mean(basket_lines)
  daily_tickets <- max(4, round(spec$daily_tickets * traffic_scale))
  daily_units   <- daily_tickets * avg_lines * 1.35

  products$daily       <- pmax(0.05, daily_units * products$share)
  products$target_days <- runif(n_prod, 16, 55)
  initial_qty <- pmax(3, round(products$daily * products$target_days))
  products$stock_sim <- initial_qty

  create_purchase(con, start - 3, products, initial_qty, status = "reçue")
  for (i in seq_len(n_prod)) {
    DBI::dbExecute(con, "UPDATE products SET reorder_point = ? WHERE id = ?",
                   params = list(round(max(3, products$daily[i] * 12), 1), products$id[i]))
  }

  # ---- 7. Historique des ventes ------------------------------------------
  step("Génération de l'historique des ventes…", 0.42)
  days <- seq(start, today, by = "day")
  n_days <- length(days)
  seasonality <- unlist(spec$seasonality)
  growth  <- 1 + 0.10 * (seq_len(n_days) - 1) / max(1, n_days - 1)
  months  <- as.integer(format(days, "%m"))
  weekday <- as.integer(format(days, "%u")) %% 7 + 1   # 1 = dimanche
  factor  <- seasonality[months] * WEEKDAY_FACTOR[weekday] * growth * runif(n_days, .85, 1.15)
  tickets <- pmax(0L, as.integer(round(daily_tickets * factor)))
  total_tickets <- sum(tickets)

  sale_day   <- rep(days, times = tickets)
  hours <- sample(8:20, total_tickets, TRUE,
                  prob = c(3, 5, 7, 8, 11, 12, 8, 7, 8, 10, 12, 9, 4))
  identified <- runif(total_tickets) < 0.55
  cust_index <- sample(seq_len(nrow(customers)), total_tickets, TRUE)
  status <- ifelse(runif(total_tickets) < 0.012, "annulée", "payée")

  sales_df <- data.frame(
    ref = sprintf("VT-%s-%05d", format(sale_day, "%y%m%d"), seq_len(total_tickets)),
    sold_at = sprintf("%s %02d:%02d:%02d", format(sale_day), hours,
                      sample(0:59, total_tickets, TRUE), sample(0:59, total_tickets, TRUE)),
    sale_date = format(sale_day),
    customer_id = ifelse(identified, customers$id[cust_index], NA_integer_),
    employee_id = sample(sellers, total_tickets, TRUE),
    payment_method = sample(unlist(CATALOG$payment_methods), total_tickets, TRUE,
                            prob = PAYMENT_W),
    channel = sample(CHANNELS, total_tickets, TRUE, prob = CHANNEL_W),
    status = status
  )

  step("Enregistrement des tickets de caisse…", 0.55)
  DBI::dbAppendTable(con, "sales", sales_df)
  sale_ids <- db_query(con, "SELECT id FROM sales ORDER BY id")$id

  # Lignes de ticket : nombre de lignes tiré par ticket, puis expansion
  basket_factor <- ifelse(identified, customers$factor[cust_index], 1)
  n_lines <- pmax(1L, as.integer(round(
    sample(basket_lines[1]:basket_lines[2], total_tickets, TRUE) *
      (0.6 + 0.4 * basket_factor))))
  total_lines <- sum(n_lines)

  line_sale_id <- rep(sale_ids, times = n_lines)
  line_factor  <- rep(basket_factor, times = n_lines)
  line_product <- sample(seq_len(n_prod), total_lines, TRUE, prob = products$weight)
  quantity <- pick_quantity(total_lines, products$base_price[line_product])
  bulk <- line_factor > 2
  quantity[bulk] <- quantity[bulk] * sample(c(2, 3, 4), sum(bulk), TRUE)
  unit_price <- products$sale_price[line_product]
  discounted <- runif(total_lines) < 0.07
  discount <- rep(0, total_lines)
  discount[discounted] <- round(unit_price[discounted] * quantity[discounted] *
                                  sample(c(.05, .10, .15), sum(discounted), TRUE), 2)

  step("Ventilation des lignes de vente…", 0.68)
  DBI::dbAppendTable(con, "sale_items", data.frame(
    sale_id    = line_sale_id,
    product_id = products$id[line_product],
    quantity   = quantity,
    unit_price = unit_price,
    unit_cost  = products$cost_price[line_product],
    discount   = discount))

  # ---- 8. Réapprovisionnements mensuels ----------------------------------
  step("Commandes de réapprovisionnement…", 0.80)
  line_month <- rep(format(sale_day, "%Y-%m"), times = n_lines)
  line_paid  <- rep(status == "payée", times = n_lines)
  demand <- tapply(quantity[line_paid],
                   list(line_month[line_paid], line_product[line_paid]), sum)
  month_keys <- sort(unique(format(days, "%Y-%m")))

  for (i in seq_along(month_keys)) {
    if (i == 1) next                       # couvert par le stock initial
    previous <- month_keys[i - 1]
    sold <- rep(0, n_prod)
    if (previous %in% rownames(demand)) {
      row <- demand[previous, ]
      idx <- as.integer(colnames(demand))
      sold[idx] <- ifelse(is.na(row), 0, row)
    }
    daily_prev <- ifelse(sold > 0, sold / 30, products$daily * 0.35)
    need <- daily_prev * products$target_days - products$stock_sim
    qty <- round(need * runif(n_prod, 0.85, 1.15))
    qty[qty < 0] <- 0
    products$stock_sim <- products$stock_sim + qty - sold
    order_day <- as.Date(paste0(month_keys[i], "-01")) + sample(0:4, 1)
    if (order_day <= today && any(qty > 0)) {
      create_purchase(con, order_day, products, qty, status = "reçue")
    }
  }

  # Une commande en cours de livraison, visible dans le département Achats
  pending <- rep(0, n_prod)
  top <- order(products$share, decreasing = TRUE)[1:min(8, n_prod)]
  pending[top] <- round(products$daily[top] * 18)
  create_purchase(con, today - 2, products, pending, status = "commandée")

  # ---- 9. Pertes & inventaires --------------------------------------------
  step("Écritures d'inventaire et de pertes…", 0.88)
  n_moves <- max(6, n_days %/% 12)
  move_day <- sample(days, n_moves, TRUE)
  move_type <- sample(c("perte", "inventaire", "retour"), n_moves, TRUE, prob = c(.55, .3, .15))
  move_qty <- ifelse(move_type == "retour", round(runif(n_moves, 1, 3), 1),
              ifelse(move_type == "inventaire", round(runif(n_moves, -4, 4), 1),
                     -round(runif(n_moves, 1, 6), 1)))
  DBI::dbAppendTable(con, "stock_moves", data.frame(
    moved_at   = paste0(format(move_day), " 18:00:00"),
    move_date  = format(move_day),
    product_id = sample(products$id, n_moves, TRUE, prob = products$weight),
    quantity   = move_qty,
    move_type  = move_type,
    source_dept = "STOCK",
    note = c(perte = "Casse / péremption", inventaire = "Écart d'inventaire",
             retour = "Retour client")[move_type]))

  # ---- 10. Charges & paie --------------------------------------------------
  step("Charges d'exploitation et paie…", 0.94)
  margins <- db_query(con, "SELECT period, gross_margin FROM v_sales_monthly")
  expense_labels <- unlist(spec$expense_lines)
  payroll_target <- db_scalar(con, "SELECT COALESCE(SUM(salary), 0) FROM employees WHERE active = 1")

  expense_rows <- do.call(rbind, lapply(month_keys, function(key) {
    first <- as.Date(paste0(key, "-01"))
    margin <- margins$gross_margin[match(key, margins$period)]
    if (is.na(margin)) margin <- 0
    budget <- max(margin * runif(1, 0.30, 0.45) - payroll_target,
                  length(expense_labels) * 25000 * scale)
    shares <- runif(length(expense_labels), 0.6, 1.6)
    data.frame(
      spent_on   = format(pmin(first + sample(0:26, length(expense_labels), TRUE), today)),
      label      = expense_labels,
      category   = expense_category(expense_labels),
      department = expense_department(expense_labels),
      amount     = round_price(budget * shares / sum(shares), decimals))
  }))
  DBI::dbAppendTable(con, "expenses", expense_rows)

  staff_db <- db_query(con, "SELECT id, salary FROM employees WHERE active = 1")
  payroll_rows <- do.call(rbind, lapply(month_keys, function(key) {
    bonus <- round_price(staff_db$salary * runif(nrow(staff_db), 0, 0.12), decimals)
    data.frame(
      period = key, employee_id = staff_db$id, gross = staff_db$salary, bonus = bonus,
      net = round_price((staff_db$salary + bonus) * 0.86, decimals),
      paid_on = format(min(as.Date(paste0(key, "-01")) + 27, today)))
  }))
  DBI::dbAppendTable(con, "payroll", payroll_rows)

  db_log(con, "SYSTEM", "company", "création", 1,
         sprintf("ERP « %s » (%s) généré sur %d mois.", trimws(name), spec$label, history_months))

  step("Consolidation des tableaux de bord…", 0.99)
  list(
    company     = trimws(name),
    store_label = spec$label,
    period      = paste(format(start), "→", format(today)),
    categories  = db_scalar(con, "SELECT COUNT(*) FROM categories"),
    products    = db_scalar(con, "SELECT COUNT(*) FROM products"),
    suppliers   = db_scalar(con, "SELECT COUNT(*) FROM suppliers"),
    customers   = db_scalar(con, "SELECT COUNT(*) FROM customers"),
    employees   = db_scalar(con, "SELECT COUNT(*) FROM employees"),
    sales       = db_scalar(con, "SELECT COUNT(*) FROM sales"),
    sale_items  = db_scalar(con, "SELECT COUNT(*) FROM sale_items"),
    stock_moves = db_scalar(con, "SELECT COUNT(*) FROM stock_moves"),
    revenue     = db_scalar(con, "SELECT COALESCE(SUM(total), 0) FROM sales WHERE status = 'payée'"),
    stock_value = db_scalar(con, "SELECT COALESCE(SUM(stock * cost_price), 0) FROM products")
  )
}

#' Crée une (ou plusieurs) commandes fournisseur, groupées par fournisseur.
create_purchase <- function(con, day, products, quantities, status = "reçue") {
  keep <- quantities > 0
  if (!any(keep)) return(invisible(FALSE))
  suppliers <- unique(products$supplier_id[keep])

  for (n in seq_along(suppliers)) {
    sid <- suppliers[n]
    rows <- keep & products$supplier_id == sid
    ref <- sprintf("AC-%s-%02d%02d", format(day, "%y%m%d"), sid, n)
    received <- if (identical(status, "reçue")) format(day + sample(1:6, 1)) else NA_character_
    DBI::dbExecute(con,
      "INSERT INTO purchases (ref, ordered_on, received_on, supplier_id, status)
       VALUES (?, ?, ?, ?, ?)",
      params = list(ref, format(day), received, sid, status))
    purchase_id <- db_scalar(con, "SELECT MAX(id) FROM purchases")
    DBI::dbAppendTable(con, "purchase_items", data.frame(
      purchase_id = purchase_id,
      product_id  = products$id[rows],
      quantity    = quantities[rows],
      unit_cost   = round(products$cost_price[rows] * runif(sum(rows), 0.94, 1.06), 2)))
  }
  invisible(TRUE)
}

expense_category <- function(labels) {
  mapping <- c(
    "Loyer" = "Immobilier", "Loyer dépôt" = "Immobilier", "Loyer centre-ville" = "Immobilier",
    "Électricité" = "Énergie", "Gaz" = "Énergie", "Eau" = "Énergie",
    "Groupe électrogène" = "Énergie", "Chaîne du froid" = "Énergie",
    "Transport" = "Logistique", "Carburant livraison" = "Logistique",
    "Transitaire & douane" = "Logistique", "Livraison plateforme" = "Logistique",
    "Marketing" = "Commercial", "Publicité réseaux sociaux" = "Commercial",
    "Décoration vitrine" = "Commercial", "Assurance" = "Administratif",
    "Assurance marchandises" = "Administratif", "Licences logiciel" = "Administratif",
    "Licences & taxes" = "Administratif")
  out <- unname(mapping[labels])
  ifelse(is.na(out), "Exploitation", out)
}

expense_department <- function(labels) {
  ifelse(grepl("^Loyer", labels) |
           labels %in% c("Assurance", "Licences logiciel", "Licences & taxes"), "FIN",
  ifelse(labels %in% c("Marketing", "Publicité réseaux sociaux", "Décoration vitrine"), "SALES",
  ifelse(labels %in% c("Transport", "Carburant livraison", "Transitaire & douane",
                       "Livraison plateforme"), "PURCH",
  ifelse(labels == "Formation continue", "HR", "STOCK"))))
}

person_names <- function(n) {
  paste(sample(unlist(CATALOG$first_names), n, TRUE),
        sample(unlist(CATALOG$last_names), n, TRUE))
}

phone_numbers <- function(n) {
  sprintf("+225 %02d %02d %02d %02d", sample(10:99, n, TRUE), sample(10:99, n, TRUE),
          sample(10:99, n, TRUE), sample(10:99, n, TRUE))
}
