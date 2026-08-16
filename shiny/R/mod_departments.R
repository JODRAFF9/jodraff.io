# =====================================================================
#  Un module par département. Tous lisent la MÊME base SQL centrale :
#  aucun ne possède ses données en propre.
#
#  Chaque module expose <dept>_ui(id) et <dept>_server(id, con, period).
#  `period` est un reactive() qui donne le nombre de jours analysés.
# =====================================================================

# ---------------------------------------------------------------------
# Vue d'ensemble
# ---------------------------------------------------------------------
overview_ui <- function(id) {
  ns <- NS(id)
  tagList(
    uiOutput(ns("head")),
    uiOutput(ns("kpis")),
    div(class = "mt", uiOutput(ns("departments"))),
    div(class = "grid grid-3 mt",
        erp_card("Chiffre d'affaires quotidien",
                 plotly::plotlyOutput(ns("daily"), height = "280px"),
                 note = "Source : département Ventes. Survolez la courbe pour le détail.",
                 class = "span-2"),
        erp_card("Répartition par rayon", plotly::plotlyOutput(ns("category"), height = "300px"),
                 note = "Chiffre d'affaires HT de la période.")),
    div(class = "grid grid-3 mt",
        erp_card("Chiffre d'affaires et marge par mois",
                 plotly::plotlyOutput(ns("monthly"), height = "300px"),
                 note = "Deux mesures de même unité, donc un seul axe de valeurs.",
                 class = "span-2"),
        erp_card("Dernières écritures", uiOutput(ns("feed")),
                 note = "Ventes, achats, mouvements de stock et charges, tous départements."))
  )
}

overview_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    company <- reactive(db_company(con))
    symbol <- reactive(company()$currency_sym)

    output$head <- renderUI({
      info <- company()
      page_header(
        paste(info$logo_emoji, " ", info$name),
        sprintf("%s, %s, %s. Toutes les cartes sont calculées en direct sur la base SQL centrale.",
                info$store_label, info$city, info$country))
    })

    output$kpis <- renderUI({
      k <- q_kpis(con, period())
      sym <- symbol()
      kpi_grid(
        kpi_tile("Chiffre d'affaires", fmt_compact(k$revenue, sym),
                 tagList(delta_html(k$revenue_delta), sprintf("sur %d j", period())),
                 dept_color("SALES")),
        kpi_tile("Marge brute", fmt_compact(k$margin, sym),
                 tagList(delta_html(k$margin_delta),
                         sprintf("taux %s %%", fr_num(k$margin_rate * 100, 1))),
                 dept_color("FIN")),
        kpi_tile("Tickets", fr_num(k$tickets),
                 tagList(delta_html(k$tickets_delta),
                         sprintf("%d clients identifiés", k$customers)),
                 dept_color("CRM")),
        kpi_tile("Panier moyen", fmt_compact(k$avg_basket, sym),
                 tagList(delta_html(k$avg_basket_delta), "par ticket"), dept_color("SALES")),
        kpi_tile("Valeur du stock", fmt_compact(k$stock_value, sym),
                 sprintf("⛔ %d rupture(s) · ▲ %d à commander", k$out_of_stock, k$stock_alerts),
                 dept_color("STOCK")),
        kpi_tile("Résultat du mois", fmt_compact(k$net_result, sym),
                 paste("masse salariale", fmt_compact(k$payroll, sym)), dept_color("HR")))
    })

    output$departments <- renderUI({
      rows <- q_departments(con)
      sym <- symbol()
      erp_card(
        "Départements connectés à la base centrale",
        div(class = "dept-strip",
            lapply(seq_len(nrow(rows)), function(i) {
              dept_chip(rows$dept[i], rows$name[i],
                        sprintf("%s %s", fr_num(rows$count[i]), rows$count_label[i]))
            })),
        div(class = "summary-grid", style = "margin-top:12px",
            lapply(seq_len(nrow(rows)), function(i) {
              value <- if (rows$dept[i] == "CRM") fr_num(rows$value[i])
                       else fmt_compact(rows$value[i], sym)
              div(class = "summary-item",
                  style = paste0("border-left:3px solid ", dept_color(rows$dept[i])),
                  div(class = "k", rows$metric[i]),
                  div(class = "v", value))
            })),
        note = paste("Une écriture faite dans un département met immédiatement à jour",
                     "les indicateurs des autres, c'est le rôle des triggers SQL."))
    })

    output$daily <- plotly::renderPlotly({
      data <- q_sales_daily(con, max(period(), 30))
      chart_line(fr_day(data$sale_date), list("CA TTC" = data$revenue),
                 symbol(), height = 280, fill = TRUE)
    })

    output$category <- plotly::renderPlotly({
      data <- q_sales_by_category(con, period())
      chart_share(data$category, data$revenue, symbol(), height = 300)
    })

    output$monthly <- plotly::renderPlotly({
      data <- q_sales_monthly(con)
      chart_grouped(fr_period(data$period),
                    list("CA HT" = data$revenue_ht, "Marge brute" = data$gross_margin),
                    symbol(), height = 300)
    })

    output$feed <- renderUI(activity_feed(q_activity(con, 11), symbol()))
  })
}

# ---------------------------------------------------------------------
# Ventes
# ---------------------------------------------------------------------
sales_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F9FE  Ventes",
      paste("Chaque ticket enregistré décharge le stock, alimente la fiche client",
            "et le compte de résultat, sans aucune ressaisie.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Chiffre d'affaires et tickets",
                 plotly::plotlyOutput(ns("revenue"), height = "210px"),
                 plotly::plotlyOutput(ns("tickets"), height = "150px"),
                 note = "Deux unités différentes : deux graphiques superposés, jamais un second axe Y.",
                 class = "span-2"),
        erp_card("Modes de paiement", plotly::plotlyOutput(ns("payment"), height = "280px"))),
    div(class = "grid grid-3 mt",
        erp_card("Affluence par jour et par heure", plotly::plotlyOutput(ns("affluence"), height = "300px"),
                 note = "Nombre de tickets. Utile pour caler les plannings d'équipe.",
                 class = "span-2"),
        erp_card("Canaux de vente", plotly::plotlyOutput(ns("channel"), height = "260px"))),
    div(class = "grid grid-2 mt",
        erp_card("Top 10 des produits", DT::DTOutput(ns("top")),
                 note = "Classement par chiffre d'affaires hors taxes."),
        erp_card("Performance des vendeurs", DT::DTOutput(ns("sellers")),
                 note = "Croisement du département Ventes et du département RH.")),
    div(class = "mt",
        erp_card("Journal des ventes", DT::DTOutput(ns("journal")),
                 note = "150 derniers tickets, triables et filtrables."))
  )
}

sales_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)

    output$kpis <- renderUI({
      k <- q_kpis(con, period())
      sym <- symbol()
      div(class = "grid grid-4",
        kpi_tile("Chiffre d'affaires", fmt_compact(k$revenue, sym),
                 tagList(delta_html(k$revenue_delta), sprintf("sur %d j", period())),
                 dept_color("SALES")),
        kpi_tile("Tickets", fr_num(k$tickets), delta_html(k$tickets_delta), dept_color("SALES")),
        kpi_tile("Panier moyen", fmt_compact(k$avg_basket, sym),
                 delta_html(k$avg_basket_delta), dept_color("SALES")),
        kpi_tile("Marge brute", fmt_compact(k$margin, sym),
                 sprintf("taux %s %%", fr_num(k$margin_rate * 100, 1)), dept_color("FIN")))
    })

    daily <- reactive(q_sales_daily(con, period()))

    output$revenue <- plotly::renderPlotly({
      data <- daily()
      chart_line(fr_day(data$sale_date), list("CA TTC" = data$revenue),
                 symbol(), height = 210, fill = TRUE)
    })
    output$tickets <- plotly::renderPlotly({
      data <- daily()
      chart_line(fr_day(data$sale_date), list("Tickets" = data$tickets), height = 150)
    })
    output$payment <- plotly::renderPlotly({
      data <- q_sales_dimension(con, "payment", period())
      chart_share(data$label, data$revenue, symbol(), height = 280)
    })
    output$channel <- plotly::renderPlotly({
      data <- q_sales_dimension(con, "channel", period())
      chart_share(data$label, data$revenue, symbol(), height = 260)
    })
    output$affluence <- plotly::renderPlotly({
      data <- q_affluence(con, period())
      if (nrow(data) == 0) return(chart_empty("Aucune vente sur la période."))
      hours <- sort(unique(data$hour))
      order <- c(1, 2, 3, 4, 5, 6, 0)
      names_days <- c("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
      matrix_z <- t(vapply(order, function(wd) {
        vapply(hours, function(h) {
          value <- data$tickets[data$wd == wd & data$hour == h]
          if (length(value) == 0) 0 else value[1]
        }, 0)
      }, numeric(length(hours))))
      chart_heatmap(matrix_z, sprintf("%02d h", hours), names_days,
                    height = 300, unit = " tickets")
    })

    output$top <- DT::renderDT({
      erp_table(q_top_products(con, 10, period()), list(
        "Produit" = col_spec("product"), "Rayon" = col_spec("category"),
        "Quantité" = col_spec("qty_sold", "num"),
        "CA HT" = col_spec("revenue_ht", "money"),
        "Marge" = col_spec("margin", "money")), page_length = 10)
    })

    output$sellers <- DT::renderDT({
      data <- q_employees(con)
      data <- data[data$tickets > 0, , drop = FALSE]
      erp_table(data, list(
        "Vendeur" = col_spec("employee"), "Poste" = col_spec("role"),
        "Tickets" = col_spec("tickets", "num"),
        "CA généré" = col_spec("revenue", "money"),
        "Panier moyen" = col_spec("avg_basket", "money")), page_length = 10)
    })

    output$journal <- DT::renderDT({
      erp_table(q_sales_list(con, 150), list(
        "Référence" = col_spec("ref"), "Date" = col_spec("sold_at"),
        "Client" = col_spec("customer"), "Vendeur" = col_spec("seller"),
        "Paiement" = col_spec("payment_method"), "Canal" = col_spec("channel"),
        "Statut" = col_spec("status"), "Total" = col_spec("total", "money")),
        page_length = 12)
    })
  })
}

# ---------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------
stock_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F4E6  Stock",
      paste("Le stock n'est jamais saisi à la main : il résulte des ventes, des",
            "réceptions fournisseurs et des écritures d'inventaire.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Valorisation par rayon", plotly::plotlyOutput(ns("valuation"), height = "320px"),
                 note = "L'écart entre les deux points est la marge immobilisée dans le rayon.",
                 class = "span-2"),
        erp_card("Répartition de la valeur", plotly::plotlyOutput(ns("share"), height = "300px"))),
    div(class = "grid grid-2 mt",
        erp_card("Alertes de réapprovisionnement", DT::DTOutput(ns("alerts")),
                 note = "Vue SQL v_stock_alerts, reprise telle quelle par le département Achats."),
        erp_card("Mouvements de stock", DT::DTOutput(ns("moves")),
                 note = "Chaque ligne indique le département qui l'a générée.")),
    div(class = "mt",
        erp_card("Catalogue complet", DT::DTOutput(ns("catalog")),
                 note = "Vue SQL v_products : prix, marge unitaire, niveau et état de stock."))
  )
}

stock_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)
    valuation <- reactive(q_stock_valuation(con))

    output$kpis <- renderUI({
      sym <- symbol()
      value <- valuation()
      alerts <- q_stock_alerts(con)
      products <- q_products(con)
      out <- sum(products$stock_status == "rupture")
      total <- sum(value$value)
      retail <- sum(value$retail_value)
      kpi_grid(
        kpi_tile("Valeur du stock", fmt_compact(total, sym),
                 sprintf("au prix de revient · %d références", nrow(products)),
                 dept_color("STOCK")),
        kpi_tile("Valeur au prix de vente", fmt_compact(retail, sym),
                 paste("marge potentielle", fmt_compact(retail - total, sym)),
                 dept_color("FIN")),
        kpi_tile("Ruptures", as.character(out), "⛔ vente impossible", STATUS$critical),
        kpi_tile("À commander", as.character(nrow(alerts)),
                 "▲ sous le point de commande", STATUS$serious))
    })

    output$valuation <- plotly::renderPlotly({
      data <- valuation()
      chart_dumbbell(data$category, data$value, data$retail_value,
                     "Prix de revient", "Prix de vente", symbol(), height = 320)
    })
    output$share <- plotly::renderPlotly({
      data <- valuation()
      chart_share(data$category, data$value, symbol(), height = 300)
    })

    output$alerts <- DT::renderDT({
      erp_table(q_stock_alerts(con), list(
        "Produit" = col_spec("product"), "Rayon" = col_spec("category"),
        "Fournisseur" = col_spec("supplier"), "État" = col_spec("severity"),
        "Stock" = col_spec("stock", "num", 1),
        "Seuil" = col_spec("reorder_point", "num", 1),
        "À commander" = col_spec("suggested_qty", "num"),
        "Coût" = col_spec("suggested_cost", "money")), page_length = 10)
    })

    output$moves <- DT::renderDT({
      erp_table(q_stock_moves(con, 150, period()), list(
        "Date" = col_spec("moved_at"), "Produit" = col_spec("product"),
        "Type" = col_spec("move_type"), "Origine" = col_spec("source_dept"),
        "Quantité" = col_spec("quantity", "num", 1)), page_length = 10)
    })

    output$catalog <- DT::renderDT({
      erp_table(q_products(con), list(
        "SKU" = col_spec("sku"), "Produit" = col_spec("name"),
        "Rayon" = col_spec("category"), "Fournisseur" = col_spec("supplier"),
        "Achat" = col_spec("cost_price", "money"),
        "Vente" = col_spec("sale_price", "money"),
        "Stock" = col_spec("stock", "num", 1),
        "État" = col_spec("stock_status"),
        "Valeur" = col_spec("stock_value", "money")), page_length = 15)
    })
  })
}

# ---------------------------------------------------------------------
# Achats
# ---------------------------------------------------------------------
purchasing_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F69A  Achats",
      paste("Le plan de commande n'est pas saisi : il est déduit des niveaux de stock",
            "et des ventes, puis groupé par fournisseur.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Achats par mois", plotly::plotlyOutput(ns("monthly"), height = "280px"),
                 note = "Montant des commandes fournisseurs, hors commandes annulées.",
                 class = "span-2"),
        erp_card("Dépense par fournisseur", plotly::plotlyOutput(ns("suppliers"), height = "300px"))),
    div(class = "grid grid-2 mt",
        erp_card("Plan de réapprovisionnement", DT::DTOutput(ns("plan")),
                 note = "Une commande par fournisseur, prête à être passée."),
        erp_card("Fournisseurs", DT::DTOutput(ns("directory")),
                 note = "Note sur 5 : qualité, respect des délais, litiges.")),
    div(class = "mt",
        erp_card("Commandes fournisseurs", DT::DTOutput(ns("orders")),
                 note = paste("Passer une commande au statut « reçue » déclenche l'entrée",
                              "en stock par trigger SQL.")))
  )
}

purchasing_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)

    output$kpis <- renderUI({
      sym <- symbol()
      orders <- q_purchases(con, 200)
      plan <- q_reorder_plan(con)
      spend <- db_scalar(con, sprintf(
        "SELECT COALESCE(SUM(total), 0) FROM purchases
          WHERE status <> 'annulée' AND ordered_on >= date('now', '-%d day')", period()))
      div(class = "grid grid-4",
        kpi_tile("Achats de la période", fmt_compact(spend, sym),
                 sprintf("sur %d jours", period()), dept_color("PURCH")),
        kpi_tile("Fournisseurs actifs",
                 as.character(db_scalar(con, "SELECT COUNT(*) FROM suppliers WHERE active = 1")),
                 "au référentiel", dept_color("PURCH")),
        kpi_tile("Commandes en cours", as.character(sum(orders$status == "commandée")),
                 "en attente de réception", dept_color("STOCK")),
        kpi_tile("Réappro. suggéré", fmt_compact(sum(plan$amount), sym),
                 sprintf("%s références sous le seuil", fr_num(sum(plan$refs))),
                 dept_color("SALES")))
    })

    output$monthly <- plotly::renderPlotly({
      data <- q_purchases_monthly(con)
      chart_bars(fr_period(data$period), data$amount, symbol(), height = 280,
                 color = dept_color("PURCH"))
    })
    output$suppliers <- plotly::renderPlotly({
      data <- head(q_suppliers(con), 6)
      chart_share(data$name, data$spend, symbol(), height = 300)
    })

    output$plan <- DT::renderDT({
      erp_table(q_reorder_plan(con), list(
        "Fournisseur" = col_spec("supplier"), "Références" = col_spec("refs", "num"),
        "Unités" = col_spec("units", "num"), "Montant" = col_spec("amount", "money"),
        "Délai (j)" = col_spec("lead_time_days", "num")), page_length = 8)
    })
    output$directory <- DT::renderDT({
      erp_table(q_suppliers(con), list(
        "Fournisseur" = col_spec("name"), "Contact" = col_spec("contact_name"),
        "Téléphone" = col_spec("phone"), "Délai (j)" = col_spec("lead_time_days", "num"),
        "Note" = col_spec("rating", "num", 1), "Références" = col_spec("refs", "num"),
        "Dépense" = col_spec("spend", "money")), page_length = 8)
    })
    output$orders <- DT::renderDT({
      erp_table(q_purchases(con, 80), list(
        "Référence" = col_spec("ref"), "Fournisseur" = col_spec("supplier"),
        "Commandée le" = col_spec("ordered_on"), "Reçue le" = col_spec("received_on"),
        "Statut" = col_spec("status"), "Total" = col_spec("total", "money")),
        page_length = 12)
    })
  })
}

# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------
crm_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F465  Clients",
      paste("La fiche client se remplit toute seule : chaque encaissement met à jour",
            "son historique, sa valeur et ses points de fidélité.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Chiffre d'affaires par segment", plotly::plotlyOutput(ns("segments"), height = "300px"),
                 note = "Un professionnel pèse plusieurs fois un particulier."),
        erp_card("Poids des segments", DT::DTOutput(ns("segment_table")),
                 note = "La vue table du graphique ci-contre."),
        erp_card("Nouveaux clients par mois", plotly::plotlyOutput(ns("acquisition"), height = "260px"),
                 note = "Date de première inscription au fichier.")),
    div(class = "grid grid-3 mt",
        erp_card("Meilleurs clients", DT::DTOutput(ns("customers")),
                 note = "Vue SQL v_customer_value, classée par valeur vie.", class = "span-2"),
        erp_card("Clients à relancer", DT::DTOutput(ns("dormant")),
                 note = "Bons clients sans achat depuis plus de 45 jours."))
  )
}

crm_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)

    output$kpis <- renderUI({
      sym <- symbol()
      customers <- q_customers(con, 1000)
      active <- db_scalar(con, sprintf(
        "SELECT COUNT(DISTINCT customer_id) FROM sales
          WHERE status = 'payée' AND sale_date >= date('now', '-%d day')", period()))
      div(class = "grid grid-4",
        kpi_tile("Clients au fichier", fr_num(nrow(customers)),
                 sprintf("%d actifs sur %d j", active, period()), dept_color("CRM")),
        kpi_tile("Valeur vie cumulée", fmt_compact(sum(customers$lifetime_value), sym),
                 "tous clients confondus", dept_color("FIN")),
        kpi_tile("Points de fidélité", fr_num(sum(customers$loyalty_points)),
                 "1 point par tranche encaissée", dept_color("HR")),
        kpi_tile("À relancer", as.character(nrow(q_dormant(con))),
                 "sans achat depuis 45 jours", STATUS$serious))
    })

    output$segments <- plotly::renderPlotly({
      data <- q_segments(con)
      chart_share(data$segment, data$revenue, symbol(), height = 300)
    })
    output$acquisition <- plotly::renderPlotly({
      data <- tail(q_acquisition(con), 12)
      chart_bars(fr_period(data$period), data$customers, height = 260,
                 color = dept_color("CRM"))
    })
    output$segment_table <- DT::renderDT({
      erp_table(q_segments(con), list(
        "Segment" = col_spec("segment"), "Clients" = col_spec("customers", "num"),
        "CA" = col_spec("revenue", "money"), "Panier" = col_spec("avg_basket", "money")),
        page_length = 6)
    })
    output$customers <- DT::renderDT({
      erp_table(q_customers(con, 200), list(
        "Client" = col_spec("customer"), "Segment" = col_spec("segment"),
        "Ville" = col_spec("city"), "Commandes" = col_spec("orders", "num"),
        "Valeur vie" = col_spec("lifetime_value", "money"),
        "Points" = col_spec("loyalty_points", "num"),
        "Dernier achat" = col_spec("last_purchase")), page_length = 12)
    })
    output$dormant <- DT::renderDT({
      erp_table(q_dormant(con), list(
        "Client" = col_spec("customer"), "Jours" = col_spec("days_since_last", "num"),
        "Valeur" = col_spec("lifetime_value", "money")), page_length = 12)
    })
  })
}

# ---------------------------------------------------------------------
# Ressources humaines
# ---------------------------------------------------------------------
hr_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F9D1  Ressources humaines",
      paste("L'équipe est reliée aux ventes : le même identifiant salarié sert à la paie",
            "et au calcul de la performance commerciale.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Masse salariale versée par mois", plotly::plotlyOutput(ns("payroll"), height = "290px"),
                 note = "Segments empilés séparés par 2 px : les parts restent lisibles.",
                 class = "span-2"),
        erp_card("Effectif par service", plotly::plotlyOutput(ns("headcount"), height = "280px"))),
    div(class = "grid grid-3 mt",
        erp_card("Coût par service", DT::DTOutput(ns("departments")),
                 note = "La vue table du graphique ci-dessus."),
        erp_card("Performance commerciale de l'équipe", DT::DTOutput(ns("staff")),
                 note = paste("Vue SQL v_employee_performance : jointure RH × Ventes.",
                              "Un poste sans encaissement affiche zéro ticket."),
                 class = "span-2"))
  )
}

hr_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)

    output$kpis <- renderUI({
      sym <- symbol()
      staff <- q_employees(con)
      by_dept <- q_headcount(con)
      sellers <- staff[staff$tickets > 0, , drop = FALSE]
      revenue_month <- db_scalar(con,
        "SELECT COALESCE(revenue, 0) FROM v_financial_monthly
          WHERE period = strftime('%Y-%m', 'now')")
      payroll <- sum(by_dept$payroll)
      div(class = "grid grid-4",
        kpi_tile("Effectif", as.character(nrow(staff)),
                 sprintf("%d services", nrow(by_dept)), dept_color("HR")),
        kpi_tile("Masse salariale", fmt_compact(payroll, sym),
                 "par mois, salaires bruts", dept_color("FIN")),
        kpi_tile("Poids sur le CA",
                 if (revenue_month > 0) sprintf("%s %%", fr_num(payroll / revenue_month * 100, 1))
                 else "n.d.",
                 "masse salariale / CA du mois", dept_color("SALES")),
        kpi_tile("CA par vendeur",
                 fmt_compact(if (nrow(sellers)) sum(sellers$revenue) / nrow(sellers) else 0, sym),
                 sprintf("%d salariés encaissent", nrow(sellers)), dept_color("CRM")))
    })

    output$payroll <- plotly::renderPlotly({
      data <- q_payroll(con)
      chart_grouped(fr_period(data$period),
                    list("Salaires nets" = data$net, "Primes" = data$bonus),
                    symbol(), height = 290, stacked = TRUE)
    })
    output$headcount <- plotly::renderPlotly({
      data <- q_headcount(con)
      chart_share(data$department, data$headcount, "", height = 280)
    })
    output$departments <- DT::renderDT({
      erp_table(q_headcount(con), list(
        "Service" = col_spec("department"), "Effectif" = col_spec("headcount", "num"),
        "Masse salariale" = col_spec("payroll", "money"),
        "Salaire moyen" = col_spec("avg_salary", "money")), page_length = 8)
    })
    output$staff <- DT::renderDT({
      erp_table(q_employees(con), list(
        "Salarié" = col_spec("employee"), "Poste" = col_spec("role"),
        "Service" = col_spec("department"), "Salaire" = col_spec("salary", "money"),
        "Tickets" = col_spec("tickets", "num"),
        "CA généré" = col_spec("revenue", "money"),
        "Panier moyen" = col_spec("avg_basket", "money")), page_length = 10)
    })
  })
}

# ---------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------
finance_ui <- function(id) {
  ns <- NS(id)
  tagList(
    page_header("\U0001F4B0  Finance",
      paste("Le compte de résultat n'est pas ressaisi : ventes, coût des marchandises,",
            "charges et paie remontent automatiquement des autres départements.")),
    uiOutput(ns("kpis")),
    div(class = "grid grid-3 mt",
        erp_card("Chiffre d'affaires, coût des marchandises et charges",
                 plotly::plotlyOutput(ns("monthly"), height = "310px"),
                 note = "Trois mesures dans la même unité, donc un seul axe de valeurs.",
                 class = "span-2"),
        erp_card("Charges par nature", plotly::plotlyOutput(ns("categories"), height = "300px"),
                 note = "Sur douze mois glissants.")),
    div(class = "grid grid-2 mt",
        erp_card("Compte de résultat mensuel", DT::DTOutput(ns("statement")),
                 note = "Vue SQL v_financial_monthly. Le dernier mois est partiel."),
        erp_card("Journal des charges", DT::DTOutput(ns("expenses")),
                 note = "150 dernières écritures."))
  )
}

finance_server <- function(id, con, period) {
  moduleServer(id, function(input, output, session) {
    symbol <- reactive(db_company(con)$currency_sym)
    monthly <- reactive(q_financial(con))

    output$kpis <- renderUI({
      sym <- symbol()
      data <- monthly()
      closed <- if (nrow(data) > 1) data[seq_len(nrow(data) - 1), , drop = FALSE] else data
      last <- closed[nrow(closed), ]
      margin <- last$revenue - last$cogs
      div(class = "grid grid-4",
        kpi_tile(paste("CA", fr_period(last$period)), fmt_compact(last$revenue, sym),
                 "dernier mois clos", dept_color("SALES")),
        kpi_tile("Marge brute", fmt_compact(margin, sym),
                 if (last$revenue > 0) sprintf("taux %s %%", fr_num(margin / last$revenue * 100, 1))
                 else "n.d.", dept_color("FIN")),
        kpi_tile("Charges + paie", fmt_compact(last$expenses + last$payroll, sym),
                 "structure et salaires", dept_color("HR")),
        kpi_tile("Résultat net", fmt_compact(last$net_result, sym),
                 if (last$net_result >= 0) "✓ bénéfice" else "⛔ perte",
                 if (last$net_result >= 0) STATUS$good else STATUS$critical))
    })

    output$monthly <- plotly::renderPlotly({
      data <- monthly()
      chart_grouped(fr_period(data$period), list(
        "Chiffre d'affaires" = data$revenue,
        "Coût des marchandises" = data$cogs,
        "Charges + paie" = data$expenses + data$payroll), symbol(), height = 310)
    })
    output$categories <- plotly::renderPlotly({
      data <- q_expenses_by(con, "category")
      chart_share(data$label, data$amount, symbol(), height = 300)
    })
    output$statement <- DT::renderDT({
      erp_table(monthly(), list(
        "Période" = col_spec("period"), "CA" = col_spec("revenue", "money"),
        "Coût march." = col_spec("cogs", "money"),
        "Charges" = col_spec("expenses", "money"), "Paie" = col_spec("payroll", "money"),
        "Résultat" = col_spec("net_result", "money")), page_length = 13)
    })
    output$expenses <- DT::renderDT({
      erp_table(q_expenses(con, 150), list(
        "Date" = col_spec("spent_on"), "Libellé" = col_spec("label"),
        "Nature" = col_spec("category"), "Département" = col_spec("department"),
        "Montant" = col_spec("amount", "money")), page_length = 13)
    })
  })
}
