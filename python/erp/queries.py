"""Requêtes métier consolidées.

Une seule implémentation, consommée par :
  - le dashboard Plotly Dash  (python/dash_app/)
  - l'API REST FastAPI        (python/api/)  -> front web + Angular

Chaque fonction retourne des structures Python simples (list[dict] / dict)
directement sérialisables en JSON.
"""

from __future__ import annotations

from typing import Any

from .database import Database, get_db

PAID = "status = 'payée'"


def _db(db: Database | None) -> Database:
    return db or get_db()


# ==========================================================================
# Vue d'ensemble — la consolidation inter-départements
# ==========================================================================
def company_info(db: Database | None = None) -> dict | None:
    return _db(db).company()


def kpis(days: int = 30, db: Database | None = None) -> dict[str, Any]:
    """Indicateurs clés de la période, avec évolution contre la période précédente."""
    d = _db(db)
    cur = d.one(
        f"""SELECT COUNT(*)                          AS tickets,
                   COALESCE(SUM(total), 0)           AS revenue,
                   COALESCE(SUM(subtotal - cost_total), 0) AS margin,
                   COALESCE(AVG(total), 0)           AS avg_basket,
                   COUNT(DISTINCT customer_id)       AS customers
              FROM sales
             WHERE {PAID} AND sale_date >= date('now', ?)""",
        (f"-{days} day",),
    ) or {}
    prev = d.one(
        f"""SELECT COUNT(*)                          AS tickets,
                   COALESCE(SUM(total), 0)           AS revenue,
                   COALESCE(SUM(subtotal - cost_total), 0) AS margin,
                   COALESCE(AVG(total), 0)           AS avg_basket
              FROM sales
             WHERE {PAID} AND sale_date >= date('now', ?)
                          AND sale_date <  date('now', ?)""",
        (f"-{days * 2} day", f"-{days} day"),
    ) or {}

    def delta(key: str) -> float | None:
        before, now = prev.get(key) or 0, cur.get(key) or 0
        return round((now - before) / before * 100, 1) if before else None

    revenue = cur.get("revenue") or 0
    margin = cur.get("margin") or 0
    return {
        "period_days": days,
        "revenue": round(revenue, 2),
        "revenue_delta": delta("revenue"),
        "tickets": cur.get("tickets") or 0,
        "tickets_delta": delta("tickets"),
        "avg_basket": round(cur.get("avg_basket") or 0, 2),
        "avg_basket_delta": delta("avg_basket"),
        "margin": round(margin, 2),
        "margin_delta": delta("margin"),
        "margin_rate": round(margin / revenue, 4) if revenue else 0,
        "customers": cur.get("customers") or 0,
        "stock_value": round(d.scalar(
            "SELECT COALESCE(SUM(stock * cost_price), 0) FROM products WHERE active = 1"), 2),
        "stock_alerts": d.scalar("SELECT COUNT(*) FROM v_stock_alerts"),
        "out_of_stock": d.scalar("SELECT COUNT(*) FROM products WHERE active = 1 AND stock <= 0"),
        "headcount": d.scalar("SELECT COUNT(*) FROM employees WHERE active = 1"),
        "payroll": round(d.scalar(
            "SELECT COALESCE(SUM(salary), 0) FROM employees WHERE active = 1"), 2),
        "expenses": round(d.scalar(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE spent_on >= date('now', ?)",
            (f"-{days} day",)), 2),
        "net_result": round(d.scalar(
            "SELECT COALESCE(net_result, 0) FROM v_financial_monthly"
            " WHERE period = strftime('%Y-%m', 'now')"), 2),
    }


def department_summary(db: Database | None = None) -> list[dict]:
    """Une carte par département : c'est la vue « données centrées »."""
    d = _db(db)
    rows = d.query("SELECT * FROM v_department_dashboard")
    extra = {
        "SALES": d.scalar(f"SELECT COUNT(*) FROM sales WHERE {PAID}"),
        "STOCK": d.scalar("SELECT COUNT(*) FROM products WHERE active = 1"),
        "PURCH": d.scalar("SELECT COUNT(*) FROM suppliers WHERE active = 1"),
        "CRM": d.scalar("SELECT COUNT(*) FROM customers"),
        "HR": d.scalar("SELECT COUNT(*) FROM employees WHERE active = 1"),
        "FIN": d.scalar("SELECT COUNT(*) FROM expenses"),
    }
    labels = {
        "SALES": "tickets enregistrés", "STOCK": "références actives",
        "PURCH": "fournisseurs actifs", "CRM": "clients au fichier",
        "HR": "salariés", "FIN": "écritures de charges",
    }
    for r in rows:
        r["count"] = extra.get(r["dept"], 0)
        r["count_label"] = labels.get(r["dept"], "")
    return rows


def recent_activity(limit: int = 12, db: Database | None = None) -> list[dict]:
    """Flux d'activité inter-départements (ventes, achats, mouvements, charges)."""
    return _db(db).query(
        """SELECT * FROM (
               SELECT sold_at AS at, 'SALES' AS dept, 'Vente ' || ref AS label,
                      total AS amount FROM sales WHERE status = 'payée'
               UNION ALL
               SELECT ordered_on || ' 09:00:00', 'PURCH', 'Commande ' || ref, total
                 FROM purchases
               UNION ALL
               SELECT moved_at, 'STOCK',
                      move_type || ' — ' || (SELECT name FROM products WHERE id = product_id),
                      quantity
                 FROM stock_moves WHERE move_type IN ('perte', 'inventaire', 'retour')
               UNION ALL
               SELECT spent_on || ' 12:00:00', 'FIN', 'Charge — ' || label, amount
                 FROM expenses
           ) ORDER BY at DESC LIMIT ?""",
        (limit,),
    )


# ==========================================================================
# Département VENTES
# ==========================================================================
def sales_daily(days: int = 90, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        "SELECT * FROM v_sales_daily WHERE sale_date >= date('now', ?) ORDER BY sale_date",
        (f"-{days} day",),
    )


def sales_monthly(db: Database | None = None) -> list[dict]:
    return _db(db).query("SELECT * FROM v_sales_monthly ORDER BY period")


def sales_by_category(days: int = 90, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        f"""SELECT c.name AS category,
                   ROUND(SUM(si.line_total), 2) AS revenue,
                   ROUND(SUM(si.line_total - si.unit_cost * si.quantity), 2) AS margin,
                   ROUND(SUM(si.quantity), 1) AS quantity
              FROM sale_items si
              JOIN sales s     ON s.id = si.sale_id AND s.{PAID}
              JOIN products p  ON p.id = si.product_id
              JOIN categories c ON c.id = p.category_id
             WHERE s.sale_date >= date('now', ?)
             GROUP BY c.name ORDER BY revenue DESC""",
        (f"-{days} day",),
    )


def sales_by_dimension(dimension: str, days: int = 90, db: Database | None = None) -> list[dict]:
    """Répartition du CA par mode de paiement, canal ou heure."""
    columns = {"payment": "payment_method", "channel": "channel",
               "hour": "substr(sold_at, 12, 2)", "weekday": "strftime('%w', sale_date)"}
    col = columns.get(dimension)
    if not col:
        raise ValueError(f"Dimension inconnue : {dimension}")
    return _db(db).query(
        f"""SELECT {col} AS label, COUNT(*) AS tickets,
                   ROUND(SUM(total), 2) AS revenue
              FROM sales WHERE {PAID} AND sale_date >= date('now', ?)
             GROUP BY {col} ORDER BY {col}""",
        (f"-{days} day",),
    )


def top_products(limit: int = 12, days: int = 90, order_by: str = "revenue_ht",
                 db: Database | None = None) -> list[dict]:
    if order_by not in ("revenue_ht", "margin", "qty_sold"):
        order_by = "revenue_ht"
    return _db(db).query(
        f"""SELECT p.name AS product, c.name AS category,
                   ROUND(SUM(si.quantity), 1) AS qty_sold,
                   ROUND(SUM(si.line_total), 2) AS revenue_ht,
                   ROUND(SUM(si.line_total - si.unit_cost * si.quantity), 2) AS margin
              FROM sale_items si
              JOIN sales s      ON s.id = si.sale_id AND s.{PAID}
              JOIN products p   ON p.id = si.product_id
              JOIN categories c ON c.id = p.category_id
             WHERE s.sale_date >= date('now', ?)
             GROUP BY p.id, p.name, c.name
             ORDER BY {order_by} DESC LIMIT ?""",
        (f"-{days} day", limit),
    )


def sales_list(limit: int = 200, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT s.id, s.ref, s.sold_at, s.status, s.payment_method, s.channel,
                  COALESCE(c.name, 'Client de passage') AS customer,
                  e.name AS seller,
                  ROUND(s.total, 2) AS total,
                  ROUND(s.subtotal - s.cost_total, 2) AS margin,
                  (SELECT COUNT(*) FROM sale_items WHERE sale_id = s.id) AS lines
             FROM sales s
             LEFT JOIN customers c ON c.id = s.customer_id
             LEFT JOIN employees e ON e.id = s.employee_id
            ORDER BY s.sold_at DESC LIMIT ?""",
        (limit,),
    )


def sale_detail(sale_id: int, db: Database | None = None) -> dict | None:
    d = _db(db)
    head = d.one(
        """SELECT s.*, COALESCE(c.name, 'Client de passage') AS customer, e.name AS seller
             FROM sales s
             LEFT JOIN customers c ON c.id = s.customer_id
             LEFT JOIN employees e ON e.id = s.employee_id
            WHERE s.id = ?""", (sale_id,))
    if not head:
        return None
    head["items"] = d.query(
        """SELECT p.name AS product, si.quantity, si.unit_price, si.discount, si.line_total
             FROM sale_items si JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?""", (sale_id,))
    return head


# ==========================================================================
# Département STOCK
# ==========================================================================
def products(db: Database | None = None, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM v_products WHERE active = 1"
    params: list[Any] = []
    if status:
        sql += " AND stock_status = ?"
        params.append(status)
    return _db(db).query(sql + " ORDER BY category, name", params)


def stock_alerts(db: Database | None = None) -> list[dict]:
    return _db(db).query("SELECT * FROM v_stock_alerts ORDER BY severity, suggested_cost DESC")


def stock_valuation(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT c.name AS category,
                  COUNT(*) AS refs,
                  ROUND(SUM(p.stock), 1) AS units,
                  ROUND(SUM(p.stock * p.cost_price), 2) AS value,
                  ROUND(SUM(p.stock * p.sale_price), 2) AS retail_value
             FROM products p JOIN categories c ON c.id = p.category_id
            WHERE p.active = 1 GROUP BY c.name ORDER BY value DESC""")


def stock_moves(limit: int = 200, days: int = 60, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT m.moved_at, m.move_date, p.name AS product, m.quantity,
                  m.move_type, m.source_dept, m.ref, m.note
             FROM stock_moves m JOIN products p ON p.id = m.product_id
            WHERE m.move_date >= date('now', ?)
            ORDER BY m.moved_at DESC LIMIT ?""",
        (f"-{days} day", limit),
    )


def stock_rotation(days: int = 90, db: Database | None = None) -> list[dict]:
    """Rotation : combien de jours de stock reste-t-il au rythme actuel ?"""
    return _db(db).query(
        f"""SELECT p.name AS product, c.name AS category, p.stock, p.unit,
                   ROUND(COALESCE(sold.qty, 0) / ?, 2) AS daily_sales,
                   CASE WHEN COALESCE(sold.qty, 0) > 0
                        THEN ROUND(p.stock / (sold.qty / ?), 1) END AS days_of_stock,
                   ROUND(p.stock * p.cost_price, 2) AS value
              FROM products p
              JOIN categories c ON c.id = p.category_id
              LEFT JOIN (SELECT si.product_id, SUM(si.quantity) AS qty
                           FROM sale_items si JOIN sales s ON s.id = si.sale_id AND s.{PAID}
                          WHERE s.sale_date >= date('now', ?)
                          GROUP BY si.product_id) sold ON sold.product_id = p.id
             WHERE p.active = 1
             ORDER BY days_of_stock IS NULL, days_of_stock""",
        (days, days, f"-{days} day"),
    )


# ==========================================================================
# Département ACHATS
# ==========================================================================
def suppliers(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM products WHERE supplier_id = s.id) AS refs,
                  (SELECT COUNT(*) FROM purchases WHERE supplier_id = s.id) AS orders,
                  ROUND(COALESCE((SELECT SUM(total) FROM purchases
                                   WHERE supplier_id = s.id AND status <> 'annulée'), 0), 2) AS spend
             FROM suppliers s ORDER BY spend DESC""")


def purchases(limit: int = 100, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT p.id, p.ref, p.ordered_on, p.received_on, p.status,
                  ROUND(p.total, 2) AS total, s.name AS supplier,
                  (SELECT COUNT(*) FROM purchase_items WHERE purchase_id = p.id) AS lines
             FROM purchases p JOIN suppliers s ON s.id = p.supplier_id
            ORDER BY p.ordered_on DESC LIMIT ?""", (limit,))


def purchases_monthly(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT substr(ordered_on, 1, 7) AS period,
                  COUNT(*) AS orders, ROUND(SUM(total), 2) AS amount
             FROM purchases WHERE status <> 'annulée'
            GROUP BY substr(ordered_on, 1, 7) ORDER BY period""")


def reorder_plan(db: Database | None = None) -> list[dict]:
    """Proposition de commande générée par le stock, groupée par fournisseur."""
    return _db(db).query(
        """SELECT COALESCE(supplier, 'Non affecté') AS supplier,
                  COUNT(*) AS refs,
                  ROUND(SUM(suggested_qty), 1) AS units,
                  ROUND(SUM(suggested_cost), 2) AS amount,
                  MAX(lead_time_days) AS lead_time_days
             FROM v_stock_alerts GROUP BY supplier ORDER BY amount DESC""")


# ==========================================================================
# Département CLIENTS (CRM)
# ==========================================================================
def customers(limit: int = 200, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        "SELECT * FROM v_customer_value ORDER BY lifetime_value DESC LIMIT ?", (limit,))


def customer_segments(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT segment, COUNT(*) AS customers,
                  ROUND(SUM(lifetime_value), 2) AS revenue,
                  ROUND(AVG(avg_basket), 2) AS avg_basket,
                  ROUND(AVG(orders), 1) AS avg_orders
             FROM v_customer_value GROUP BY segment ORDER BY revenue DESC""")


def dormant_customers(days: int = 60, limit: int = 25, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT * FROM v_customer_value
            WHERE orders > 0 AND days_since_last >= ?
            ORDER BY lifetime_value DESC LIMIT ?""", (days, limit))


def customer_acquisition(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT substr(created_at, 1, 7) AS period, COUNT(*) AS customers
             FROM customers GROUP BY substr(created_at, 1, 7) ORDER BY period""")


# ==========================================================================
# Département RESSOURCES HUMAINES
# ==========================================================================
def employees(db: Database | None = None) -> list[dict]:
    return _db(db).query("SELECT * FROM v_employee_performance ORDER BY revenue DESC")


def headcount_by_department(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT department, COUNT(*) AS headcount,
                  ROUND(SUM(salary), 2) AS payroll,
                  ROUND(AVG(salary), 2) AS avg_salary
             FROM employees WHERE active = 1
            GROUP BY department ORDER BY payroll DESC""")


def payroll_history(db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT period, COUNT(*) AS employees,
                  ROUND(SUM(gross), 2) AS gross, ROUND(SUM(bonus), 2) AS bonus,
                  ROUND(SUM(net), 2) AS net
             FROM payroll GROUP BY period ORDER BY period""")


# ==========================================================================
# Département FINANCE
# ==========================================================================
def financial_monthly(db: Database | None = None) -> list[dict]:
    return _db(db).query("SELECT * FROM v_financial_monthly")


def expenses_by_category(days: int = 365, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT category, COUNT(*) AS entries, ROUND(SUM(amount), 2) AS amount
             FROM expenses WHERE spent_on >= date('now', ?)
            GROUP BY category ORDER BY amount DESC""", (f"-{days} day",))


def expenses_by_department(days: int = 365, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        """SELECT department, ROUND(SUM(amount), 2) AS amount
             FROM expenses WHERE spent_on >= date('now', ?)
            GROUP BY department ORDER BY amount DESC""", (f"-{days} day",))


def expenses_list(limit: int = 200, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        "SELECT * FROM expenses ORDER BY spent_on DESC LIMIT ?", (limit,))


def profit_bridge(db: Database | None = None) -> dict[str, float]:
    """Passage du chiffre d'affaires au résultat, sur le mois en cours."""
    d = _db(db)
    row = d.one(
        "SELECT * FROM v_financial_monthly WHERE period = strftime('%Y-%m', 'now')") or {}
    return {
        "revenue": row.get("revenue", 0) or 0,
        "cogs": -(row.get("cogs", 0) or 0),
        "expenses": -(row.get("expenses", 0) or 0),
        "payroll": -(row.get("payroll", 0) or 0),
        "net_result": row.get("net_result", 0) or 0,
    }


# ==========================================================================
# Écritures (utilisées par l'API et les formulaires des dashboards)
# ==========================================================================
def register_sale(items: list[dict], customer_id: int | None = None,
                  employee_id: int | None = None, payment_method: str = "Espèces",
                  channel: str = "Boutique", db: Database | None = None) -> dict:
    """Enregistre une vente : les triggers déchargent le stock et alimentent la finance."""
    d = _db(db)
    if not items:
        raise ValueError("Une vente doit comporter au moins une ligne.")
    ref = f"VT-{d.scalar('SELECT COUNT(*) FROM sales') + 1:06d}"
    with d.transaction() as conn:
        cur = conn.execute(
            """INSERT INTO sales (ref, sold_at, sale_date, customer_id, employee_id,
                                  payment_method, channel, status)
               VALUES (?, datetime('now'), date('now'), ?, ?, ?, ?, 'payée')""",
            (ref, customer_id, employee_id, payment_method, channel),
        )
        sale_id = cur.lastrowid
        for item in items:
            prod = d.one("SELECT sale_price, cost_price FROM products WHERE id = ?",
                         (item["product_id"],))
            if not prod:
                raise ValueError(f"Produit inconnu : {item['product_id']}")
            conn.execute(
                """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price,
                                           unit_cost, discount)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (sale_id, item["product_id"], float(item["quantity"]),
                 # une clé présente mais nulle (JSON) doit retomber sur le tarif
                 float(item.get("unit_price") or prod["sale_price"]),
                 prod["cost_price"], float(item.get("discount") or 0)),
            )
    d.log("SALES", "sales", "création", sale_id, f"Vente {ref} enregistrée.")
    return sale_detail(sale_id, db=d)


def register_stock_move(product_id: int, quantity: float, move_type: str,
                        note: str = "", db: Database | None = None) -> dict:
    """Mouvement manuel : inventaire, perte ou retour."""
    if move_type not in ("inventaire", "perte", "retour"):
        raise ValueError("Type attendu : inventaire, perte ou retour.")
    d = _db(db)
    move_id = d.execute(
        """INSERT INTO stock_moves (moved_at, move_date, product_id, quantity,
                                    move_type, source_dept, note)
           VALUES (datetime('now'), date('now'), ?, ?, ?, 'STOCK', ?)""",
        (product_id, float(quantity), move_type, note),
    )
    d.log("STOCK", "stock_moves", move_type, move_id, note)
    return d.one(
        """SELECT m.*, p.name AS product, p.stock AS new_stock
             FROM stock_moves m JOIN products p ON p.id = m.product_id
            WHERE m.id = ?""", (move_id,))


def receive_purchase(purchase_id: int, db: Database | None = None) -> dict | None:
    """Réceptionne une commande : le trigger SQL entre la marchandise en stock."""
    d = _db(db)
    d.execute(
        "UPDATE purchases SET status = 'reçue', received_on = date('now') WHERE id = ?",
        (purchase_id,))
    return d.one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))


def create_purchase_order(supplier_id: int, lines: list[dict],
                          db: Database | None = None) -> dict:
    """Crée une commande fournisseur (statut « commandée », stock non impacté)."""
    d = _db(db)
    if not lines:
        raise ValueError("Une commande doit comporter au moins une ligne.")
    ref = f"AC-{d.scalar('SELECT COUNT(*) FROM purchases') + 1:06d}"
    with d.transaction() as conn:
        cur = conn.execute(
            """INSERT INTO purchases (ref, ordered_on, supplier_id, status)
               VALUES (?, date('now'), ?, 'commandée')""", (ref, supplier_id))
        pid = cur.lastrowid
        for line in lines:
            cost = d.scalar("SELECT cost_price FROM products WHERE id = ?",
                            (line["product_id"],))
            conn.execute(
                """INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost)
                   VALUES (?, ?, ?, ?)""",
                (pid, line["product_id"], float(line["quantity"]),
                 float(line.get("unit_cost") or cost)))
    d.log("PURCH", "purchases", "création", pid, f"Commande {ref} créée.")
    return d.one("SELECT * FROM purchases WHERE id = ?", (pid,))


def audit_trail(limit: int = 50, db: Database | None = None) -> list[dict]:
    return _db(db).query(
        "SELECT * FROM audit_log ORDER BY happened_at DESC, id DESC LIMIT ?", (limit,))
