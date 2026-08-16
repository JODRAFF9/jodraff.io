# =====================================================================
#  Requêtes métier.
#
#  Ce sont les mêmes vues SQL que celles utilisées par le dashboard Python
#  et l'API REST : v_products, v_sales_daily, v_stock_alerts,
#  v_customer_value, v_employee_performance, v_financial_monthly…
#  Aucune logique métier n'est dupliquée en R.
# =====================================================================

#' Indicateurs clés de la période, avec évolution contre la période précédente.
q_kpis <- function(con, days = 30) {
  current <- db_one(con, sprintf(
    "SELECT COUNT(*) AS tickets,
            COALESCE(SUM(total), 0) AS revenue,
            COALESCE(SUM(subtotal - cost_total), 0) AS margin,
            COALESCE(AVG(total), 0) AS avg_basket,
            COUNT(DISTINCT customer_id) AS customers
       FROM sales WHERE status = 'payée' AND sale_date >= date('now', '-%d day')", days))
  previous <- db_one(con, sprintf(
    "SELECT COUNT(*) AS tickets,
            COALESCE(SUM(total), 0) AS revenue,
            COALESCE(SUM(subtotal - cost_total), 0) AS margin,
            COALESCE(AVG(total), 0) AS avg_basket
       FROM sales WHERE status = 'payée'
        AND sale_date >= date('now', '-%d day') AND sale_date < date('now', '-%d day')",
    days * 2, days))

  delta <- function(key) {
    before <- previous[[key]] %||% 0
    now <- current[[key]] %||% 0
    if (is.na(before) || before == 0) NA_real_ else round((now - before) / before * 100, 1)
  }

  revenue <- current$revenue %||% 0
  margin <- current$margin %||% 0
  list(
    revenue = revenue, revenue_delta = delta("revenue"),
    tickets = current$tickets %||% 0, tickets_delta = delta("tickets"),
    avg_basket = current$avg_basket %||% 0, avg_basket_delta = delta("avg_basket"),
    margin = margin, margin_delta = delta("margin"),
    margin_rate = if (revenue > 0) margin / revenue else 0,
    customers = current$customers %||% 0,
    stock_value = db_scalar(con,
      "SELECT COALESCE(SUM(stock * cost_price), 0) FROM products WHERE active = 1"),
    stock_alerts = db_scalar(con, "SELECT COUNT(*) FROM v_stock_alerts"),
    out_of_stock = db_scalar(con,
      "SELECT COUNT(*) FROM products WHERE active = 1 AND stock <= 0"),
    headcount = db_scalar(con, "SELECT COUNT(*) FROM employees WHERE active = 1"),
    payroll = db_scalar(con,
      "SELECT COALESCE(SUM(salary), 0) FROM employees WHERE active = 1"),
    net_result = db_scalar(con,
      "SELECT COALESCE(net_result, 0) FROM v_financial_monthly
        WHERE period = strftime('%Y-%m', 'now')")
  )
}

#' Une ligne par département : c'est la vue « données centrées ».
q_departments <- function(con) {
  rows <- db_query(con, "SELECT * FROM v_department_dashboard")
  counts <- c(
    SALES = db_scalar(con, "SELECT COUNT(*) FROM sales WHERE status = 'payée'"),
    STOCK = db_scalar(con, "SELECT COUNT(*) FROM products WHERE active = 1"),
    PURCH = db_scalar(con, "SELECT COUNT(*) FROM suppliers WHERE active = 1"),
    CRM   = db_scalar(con, "SELECT COUNT(*) FROM customers"),
    HR    = db_scalar(con, "SELECT COUNT(*) FROM employees WHERE active = 1"),
    FIN   = db_scalar(con, "SELECT COUNT(*) FROM expenses"))
  labels <- c(SALES = "tickets enregistrés", STOCK = "références actives",
              PURCH = "fournisseurs actifs", CRM = "clients au fichier",
              HR = "salariés", FIN = "écritures de charges")
  rows$count <- unname(counts[rows$dept])
  rows$count_label <- unname(labels[rows$dept])
  rows
}

q_activity <- function(con, limit = 12) {
  db_query(con, sprintf(
    "SELECT * FROM (
        SELECT sold_at AS at, 'SALES' AS dept, 'Vente ' || ref AS label, total AS amount
          FROM sales WHERE status = 'payée'
        UNION ALL
        SELECT ordered_on || ' 09:00:00', 'PURCH', 'Commande ' || ref, total FROM purchases
        UNION ALL
        SELECT moved_at, 'STOCK',
               move_type || ', ' || (SELECT name FROM products WHERE id = product_id),
               quantity
          FROM stock_moves WHERE move_type IN ('perte', 'inventaire', 'retour')
        UNION ALL
        SELECT spent_on || ' 12:00:00', 'FIN', 'Charge, ' || label, amount FROM expenses
     ) ORDER BY at DESC LIMIT %d", limit))
}

q_sales_daily <- function(con, days = 90) {
  db_query(con, sprintf(
    "SELECT * FROM v_sales_daily WHERE sale_date >= date('now', '-%d day')
      ORDER BY sale_date", days))
}

q_sales_monthly <- function(con) {
  db_query(con, "SELECT * FROM v_sales_monthly ORDER BY period")
}

q_sales_by_category <- function(con, days = 90) {
  db_query(con, sprintf(
    "SELECT c.name AS category,
            ROUND(SUM(si.line_total), 2) AS revenue,
            ROUND(SUM(si.line_total - si.unit_cost * si.quantity), 2) AS margin
       FROM sale_items si
       JOIN sales s ON s.id = si.sale_id AND s.status = 'payée'
       JOIN products p ON p.id = si.product_id
       JOIN categories c ON c.id = p.category_id
      WHERE s.sale_date >= date('now', '-%d day')
      GROUP BY c.name ORDER BY revenue DESC", days))
}

q_sales_dimension <- function(con, dimension, days = 90) {
  column <- switch(dimension,
    payment = "payment_method", channel = "channel",
    hour = "substr(sold_at, 12, 2)", stop("Dimension inconnue : ", dimension))
  db_query(con, sprintf(
    "SELECT %s AS label, COUNT(*) AS tickets, ROUND(SUM(total), 2) AS revenue
       FROM sales WHERE status = 'payée' AND sale_date >= date('now', '-%d day')
      GROUP BY %s ORDER BY %s", column, days, column, column))
}

q_top_products <- function(con, limit = 10, days = 90) {
  db_query(con, sprintf(
    "SELECT p.name AS product, c.name AS category,
            ROUND(SUM(si.quantity), 1) AS qty_sold,
            ROUND(SUM(si.line_total), 2) AS revenue_ht,
            ROUND(SUM(si.line_total - si.unit_cost * si.quantity), 2) AS margin
       FROM sale_items si
       JOIN sales s ON s.id = si.sale_id AND s.status = 'payée'
       JOIN products p ON p.id = si.product_id
       JOIN categories c ON c.id = p.category_id
      WHERE s.sale_date >= date('now', '-%d day')
      GROUP BY p.id, p.name, c.name ORDER BY revenue_ht DESC LIMIT %d", days, limit))
}

q_sales_list <- function(con, limit = 150) {
  db_query(con, sprintf(
    "SELECT s.ref, s.sold_at, s.status, s.payment_method, s.channel,
            COALESCE(c.name, 'Client de passage') AS customer, e.name AS seller,
            ROUND(s.total, 2) AS total
       FROM sales s
       LEFT JOIN customers c ON c.id = s.customer_id
       LEFT JOIN employees e ON e.id = s.employee_id
      ORDER BY s.sold_at DESC LIMIT %d", limit))
}

q_affluence <- function(con, days = 30) {
  db_query(con, sprintf(
    "SELECT CAST(strftime('%%w', sale_date) AS INTEGER) AS wd,
            CAST(substr(sold_at, 12, 2) AS INTEGER) AS hour, COUNT(*) AS tickets
       FROM sales WHERE status = 'payée' AND sale_date >= date('now', '-%d day')
      GROUP BY wd, hour", days))
}

q_products <- function(con) {
  db_query(con, "SELECT * FROM v_products WHERE active = 1 ORDER BY category, name")
}

q_stock_alerts <- function(con) {
  db_query(con, "SELECT * FROM v_stock_alerts ORDER BY severity, suggested_cost DESC")
}

q_stock_valuation <- function(con) {
  db_query(con,
    "SELECT c.name AS category, COUNT(*) AS refs,
            ROUND(SUM(p.stock), 1) AS units,
            ROUND(SUM(p.stock * p.cost_price), 2) AS value,
            ROUND(SUM(p.stock * p.sale_price), 2) AS retail_value
       FROM products p JOIN categories c ON c.id = p.category_id
      WHERE p.active = 1 GROUP BY c.name ORDER BY value DESC")
}

q_stock_moves <- function(con, limit = 150, days = 60) {
  db_query(con, sprintf(
    "SELECT m.moved_at, p.name AS product, m.move_type, m.source_dept,
            m.quantity, m.ref
       FROM stock_moves m JOIN products p ON p.id = m.product_id
      WHERE m.move_date >= date('now', '-%d day')
      ORDER BY m.moved_at DESC LIMIT %d", days, limit))
}

q_suppliers <- function(con) {
  db_query(con,
    "SELECT s.name, s.contact_name, s.phone, s.lead_time_days, s.rating,
            (SELECT COUNT(*) FROM products WHERE supplier_id = s.id) AS refs,
            ROUND(COALESCE((SELECT SUM(total) FROM purchases
                             WHERE supplier_id = s.id AND status <> 'annulée'), 0), 2) AS spend
       FROM suppliers s ORDER BY spend DESC")
}

q_purchases <- function(con, limit = 80) {
  db_query(con, sprintf(
    "SELECT p.ref, s.name AS supplier, p.ordered_on, p.received_on, p.status,
            ROUND(p.total, 2) AS total
       FROM purchases p JOIN suppliers s ON s.id = p.supplier_id
      ORDER BY p.ordered_on DESC LIMIT %d", limit))
}

q_purchases_monthly <- function(con) {
  db_query(con,
    "SELECT substr(ordered_on, 1, 7) AS period, COUNT(*) AS orders,
            ROUND(SUM(total), 2) AS amount
       FROM purchases WHERE status <> 'annulée'
      GROUP BY substr(ordered_on, 1, 7) ORDER BY period")
}

q_reorder_plan <- function(con) {
  db_query(con,
    "SELECT COALESCE(supplier, 'Non affecté') AS supplier, COUNT(*) AS refs,
            ROUND(SUM(suggested_qty), 1) AS units,
            ROUND(SUM(suggested_cost), 2) AS amount,
            MAX(lead_time_days) AS lead_time_days
       FROM v_stock_alerts GROUP BY supplier ORDER BY amount DESC")
}

q_customers <- function(con, limit = 200) {
  db_query(con, sprintf(
    "SELECT * FROM v_customer_value ORDER BY lifetime_value DESC LIMIT %d", limit))
}

q_segments <- function(con) {
  db_query(con,
    "SELECT segment, COUNT(*) AS customers, ROUND(SUM(lifetime_value), 2) AS revenue,
            ROUND(AVG(avg_basket), 2) AS avg_basket, ROUND(AVG(orders), 1) AS avg_orders
       FROM v_customer_value GROUP BY segment ORDER BY revenue DESC")
}

q_dormant <- function(con, days = 45, limit = 25) {
  db_query(con, sprintf(
    "SELECT customer, days_since_last, lifetime_value FROM v_customer_value
      WHERE orders > 0 AND days_since_last >= %d
      ORDER BY lifetime_value DESC LIMIT %d", days, limit))
}

q_acquisition <- function(con) {
  db_query(con,
    "SELECT substr(created_at, 1, 7) AS period, COUNT(*) AS customers
       FROM customers GROUP BY substr(created_at, 1, 7) ORDER BY period")
}

q_employees <- function(con) {
  db_query(con, "SELECT * FROM v_employee_performance ORDER BY revenue DESC")
}

q_headcount <- function(con) {
  db_query(con,
    "SELECT department, COUNT(*) AS headcount, ROUND(SUM(salary), 2) AS payroll,
            ROUND(AVG(salary), 2) AS avg_salary
       FROM employees WHERE active = 1 GROUP BY department ORDER BY payroll DESC")
}

q_payroll <- function(con) {
  db_query(con,
    "SELECT period, COUNT(*) AS employees, ROUND(SUM(gross), 2) AS gross,
            ROUND(SUM(bonus), 2) AS bonus, ROUND(SUM(net), 2) AS net
       FROM payroll GROUP BY period ORDER BY period")
}

q_financial <- function(con) db_query(con, "SELECT * FROM v_financial_monthly")

q_expenses_by <- function(con, dimension = "category", days = 365) {
  column <- if (dimension == "category") "category" else "department"
  db_query(con, sprintf(
    "SELECT %s AS label, ROUND(SUM(amount), 2) AS amount
       FROM expenses WHERE spent_on >= date('now', '-%d day')
      GROUP BY %s ORDER BY amount DESC", column, days, column))
}

q_expenses <- function(con, limit = 150) {
  db_query(con, sprintf(
    "SELECT spent_on, label, category, department, amount
       FROM expenses ORDER BY spent_on DESC LIMIT %d", limit))
}
