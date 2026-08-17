"""Générateur d'entreprise : c'est le cœur de la « plateforme ».

À partir de deux informations données par l'utilisateur au tout début, **le type de boutique** et **son nom**, le générateur construit un ERP
complet dans la base SQL centrale :

    référentiels (rayons, produits, fournisseurs, clients, personnel)
      -> stock initial (commandes fournisseurs)
        -> historique de ventes réaliste (saisonnalité, jours de semaine)
          -> réapprovisionnements mensuels, pertes, inventaires
            -> charges d'exploitation et paie
              -> vues consolidées immédiatement exploitables

Les triggers SQL font le reste : chaque écriture d'un département se
propage automatiquement vers les autres.
"""

from __future__ import annotations

import random
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Callable

from .config import (
    CUSTOMER_SEGMENTS,
    DEPARTMENTS,
    FIRST_NAMES,
    LAST_NAMES,
    PAYMENT_METHODS,
    get_currency,
    get_store_type,
)
from .database import Database, get_db

Progress = Callable[[str, float], None] | None

# Coefficient d'activité par jour de la semaine (lundi = 0)
WEEKDAY_FACTOR = [0.82, 0.86, 0.92, 0.98, 1.22, 1.45, 0.95]
CHANNELS = [("Boutique", 0.78), ("Téléphone", 0.09), ("Livraison", 0.08), ("En ligne", 0.05)]

TABLES_TO_CLEAR = [
    "sale_items", "sales", "purchase_items", "purchases", "stock_moves",
    "expenses", "payroll", "audit_log", "products", "categories",
    "suppliers", "customers", "employees", "departments", "company", "app_meta",
]


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------
def _slug(text: str, length: int = 3) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    letters = "".join(ch for ch in norm if ch.isalnum()).upper()
    return (letters + "XXX")[:length]


def _weighted_choice(rng: random.Random, items: list, weights: list[float]):
    return rng.choices(items, weights=weights, k=1)[0]


def _round_price(value: float, decimals: int) -> float:
    if decimals == 0:
        # arrondi commercial au multiple de 5 le plus proche
        return float(max(5, int(round(value / 5.0)) * 5))
    return round(value, decimals)


def _person_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _phone(rng: random.Random) -> str:
    return f"+225 {rng.randint(1, 9)}{rng.randint(0, 9)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def reset_database(db: Database | None = None) -> None:
    """Vide toutes les tables métier (l'onboarding repart de zéro)."""
    db = db or get_db()
    with db.transaction() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in TABLES_TO_CLEAR:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
        conn.execute("PRAGMA foreign_keys = ON")


# --------------------------------------------------------------------------
# Générateur principal
# --------------------------------------------------------------------------
def create_company(
    name: str,
    store_type: str,
    *,
    currency: str = "XOF",
    city: str = "Abidjan",
    country: str = "Côte d'Ivoire",
    history_months: int = 12,
    traffic_scale: float = 1.0,
    seed: int = 20240,
    db: Database | None = None,
    progress: Progress = None,
) -> dict[str, Any]:
    """Crée l'ERP complet d'une boutique et retourne un résumé chiffré."""
    if not name or not name.strip():
        raise ValueError("Le nom de la boutique est obligatoire.")

    spec = get_store_type(store_type)
    cur = get_currency(currency)
    db = db or get_db()
    rng = random.Random(seed)

    def step(label: str, pct: float) -> None:
        if progress:
            progress(label, pct)

    step("Réinitialisation de la base centrale…", 0.02)
    reset_database(db)

    today = date.today()
    start = (today - timedelta(days=int(history_months * 30.44))).replace(day=1)
    scale = cur["scale"]
    decimals = cur["decimals"]

    # ---- 1. Entreprise & départements ---------------------------------
    step("Création de l'entreprise…", 0.06)
    db.execute(
        """INSERT INTO company (id, name, store_type, store_label, currency, currency_sym,
                                tax_rate, city, country, opened_on, logo_mark)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name.strip(), store_type, spec["label"], cur["code"], cur["symbol"],
         spec["tax_rate"], city, country, start.isoformat(), spec["icon"]),
    )
    db.executemany(
        "INSERT INTO departments (code, name, icon, position) VALUES (?, ?, ?, ?)",
        [(d["code"], d["name"], "", d["position"]) for d in DEPARTMENTS],
    )
    db.set_meta("onboarded_at", datetime.now().isoformat(timespec="seconds"))
    db.set_meta("history_months", history_months)
    db.set_meta("seed", seed)

    # ---- 2. Fournisseurs ----------------------------------------------
    step("Enregistrement des fournisseurs…", 0.10)
    supplier_ids: list[int] = []
    for sup in spec["suppliers"]:
        sid = db.execute(
            """INSERT INTO suppliers (name, contact_name, phone, email, lead_time_days, rating)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sup, _person_name(rng), _phone(rng),
             f"contact@{_slug(sup, 8).lower()}.com",
             rng.choice([3, 5, 7, 10, 14, 21]),
             round(rng.uniform(3.1, 5.0), 1)),
        )
        supplier_ids.append(sid)

    # ---- 3. Rayons & catalogue produits -------------------------------
    step("Construction du catalogue produits…", 0.16)
    products: list[dict[str, Any]] = []
    for cat in spec["categories"]:
        cat_id = db.execute(
            "INSERT INTO categories (name, margin_target) VALUES (?, ?)",
            (cat["name"], spec["margin_target"]),
        )
        cat_weight = rng.uniform(0.7, 1.4)
        for idx, prod in enumerate(cat["products"], start=1):
            cost = _round_price(prod["cost"] * scale, decimals)
            price = _round_price(prod["price"] * scale, decimals)
            sku = f"{_slug(cat['name'])}-{idx:03d}"
            weight = cat_weight * rng.uniform(0.45, 1.8)
            # les articles chers tournent moins vite
            weight /= max(1.0, (prod["price"] / 5000.0) ** 0.45)
            pid = db.execute(
                """INSERT INTO products (sku, name, category_id, supplier_id, unit,
                                         cost_price, sale_price, stock, reorder_point)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (sku, prod["name"], cat_id, rng.choice(supplier_ids), prod["unit"],
                 cost, price, 0),
            )
            products.append({
                "id": pid, "name": prod["name"], "cost": cost, "price": price,
                "base_price": prod["price"], "category": cat["name"],
                "weight": weight, "sold": 0,
            })

    total_weight = sum(p["weight"] for p in products)
    for p in products:
        p["share"] = p["weight"] / total_weight

    # ---- 4. Personnel --------------------------------------------------
    step("Constitution de l'équipe…", 0.22)
    employees: list[dict[str, Any]] = []
    for role in spec["roles"]:
        headcount = 1 if role["department"] == "Direction" else rng.randint(1, 3)
        for _ in range(headcount):
            hired = today - timedelta(days=rng.randint(60, 1800))
            eid = db.execute(
                """INSERT INTO employees (name, role, department, salary, phone, hired_on, active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (_person_name(rng), role["title"], role["department"],
                 _round_price(role["salary"] * scale * rng.uniform(0.9, 1.15), decimals),
                 _phone(rng), hired.isoformat()),
            )
            employees.append({"id": eid, "department": role["department"]})
    sellers = [e["id"] for e in employees if e["department"] in ("Ventes", "Direction")] or \
              [e["id"] for e in employees]

    # ---- 5. Clients ----------------------------------------------------
    step("Import du fichier clients…", 0.28)
    n_customers = max(40, int(spec["daily_tickets"] * 1.6))
    seg_names = [s["name"] for s in CUSTOMER_SEGMENTS]
    seg_weights = [s["weight"] for s in CUSTOMER_SEGMENTS]
    seg_factor = {s["name"]: s["basket_factor"] for s in CUSTOMER_SEGMENTS}
    cities = [city, city, city, "Bouaké", "Yamoussoukro", "San-Pédro", "Korhogo"]
    customers: list[dict[str, Any]] = []
    for _ in range(n_customers):
        segment = _weighted_choice(rng, seg_names, seg_weights)
        person = _person_name(rng)
        label = person if segment in ("Particulier", "Fidèle") else \
            f"{rng.choice(['Ets', 'SARL', 'Groupe', 'Coop.'])} {person.split()[1]}"
        cid = db.execute(
            """INSERT INTO customers (name, segment, phone, email, city, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (label, segment, _phone(rng),
             f"{_slug(person, 12).lower()}@mail.com", rng.choice(cities),
             (start - timedelta(days=rng.randint(0, 900))).isoformat()),
        )
        customers.append({"id": cid, "segment": segment, "factor": seg_factor[segment]})

    # ---- 6 à 8. Stock initial, ventes et réapprovisionnements ----------
    # Ces trois étapes sont générées **chronologiquement dans une seule
    # boucle** : l'acheteur ne connaît que le passé au moment où il commande.
    # C'est ce qui produit des niveaux de stock crédibles, surstocks d'un
    # côté, alertes et ruptures de l'autre, au lieu d'une base parfaite.
    step("Réception du stock initial…", 0.34)
    avg_lines = sum(spec["basket_lines"]) / 2
    daily_tickets = max(4, int(spec["daily_tickets"] * traffic_scale))
    daily_units = daily_tickets * avg_lines * 1.35  # ~1,35 unité par ligne

    for p in products:
        p["daily"] = max(0.05, daily_units * p["share"])
        # politique d'appro propre à chaque article (jours de couverture visés)
        p["target_days"] = rng.uniform(16, 55)
        p["stock_sim"] = 0.0

    initial = {p["id"]: max(3.0, round(p["daily"] * p["target_days"])) for p in products}
    _create_purchase(db, rng, start - timedelta(days=3), supplier_ids, products,
                     initial, status="reçue")
    for p in products:
        p["stock_sim"] = float(initial[p["id"]])
        db.execute("UPDATE products SET reorder_point = ? WHERE id = ?",
                   (round(max(3.0, p["daily"] * 12), 1), p["id"]))

    step("Génération de l'historique des ventes…", 0.40)
    seasonality = spec["seasonality"]
    lines_min, lines_max = spec["basket_lines"]
    prod_ids = [p["id"] for p in products]
    prod_weights = [p["weight"] for p in products]
    by_id = {p["id"]: p for p in products}

    n_days = (today - start).days + 1
    ticket_no = 0
    monthly_demand: dict[str, dict[int, float]] = {}
    current_month: str | None = None
    conn = db.conn

    def monthly_restock(order_day: date, previous_month: str) -> None:
        """Commande de réapprovisionnement basée sur le mois écoulé."""
        prev = monthly_demand.get(previous_month, {})
        qty_map: dict[int, float] = {}
        for prod in products:
            sold = prev.get(prod["id"], 0.0)
            daily = (sold / 30.0) if sold else prod["daily"] * 0.35
            need = daily * prod["target_days"] - prod["stock_sim"]
            qty = round(need * rng.uniform(0.85, 1.15))
            if qty > 0:
                qty_map[prod["id"]] = float(qty)
                prod["stock_sim"] += qty
        if qty_map:
            _create_purchase(db, rng, order_day, supplier_ids, products, qty_map, status="reçue")

    for offset in range(n_days):
        day = start + timedelta(days=offset)
        month_key = day.strftime("%Y-%m")

        if month_key != current_month:
            if current_month is not None:
                monthly_restock(day + timedelta(days=rng.randint(0, 4)), current_month)
                step(f"Ventes, {day.strftime('%m/%Y')}…",
                     0.40 + 0.44 * offset / max(1, n_days))
            current_month = month_key
        demand = monthly_demand.setdefault(month_key, {})

        growth = 1.0 + 0.10 * (offset / max(1, n_days))     # croissance douce
        factor = (seasonality[day.month - 1] * WEEKDAY_FACTOR[day.weekday()]
                  * growth * rng.uniform(0.85, 1.15))
        tickets = max(0, int(round(daily_tickets * factor)))
        if tickets == 0:
            continue

        # --- en-têtes de tickets insérés en lot -------------------------
        sale_rows = []
        contexts = []
        for _ in range(tickets):
            ticket_no += 1
            hour = _weighted_choice(
                rng,
                [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                [3, 5, 7, 8, 11, 12, 8, 7, 8, 10, 12, 9, 4],
            )
            sold_at = f"{day.isoformat()} {hour:02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
            customer = rng.choice(customers) if rng.random() < 0.55 else None
            status = "annulée" if rng.random() < 0.012 else "payée"
            sale_rows.append((
                f"VT-{day.strftime('%y%m%d')}-{ticket_no:05d}", sold_at, day.isoformat(),
                customer["id"] if customer else None, rng.choice(sellers),
                _weighted_choice(rng, PAYMENT_METHODS, [0.42, 0.28, 0.14, 0.08, 0.08]),
                _weighted_choice(rng, [c[0] for c in CHANNELS], [c[1] for c in CHANNELS]),
                status,
            ))
            contexts.append((customer["factor"] if customer else 1.0, status))

        base_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM sales").fetchone()[0]
        conn.executemany(
            """INSERT INTO sales (ref, sold_at, sale_date, customer_id, employee_id,
                                  payment_method, channel, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            sale_rows,
        )

        # --- lignes de ticket insérées en lot (les triggers font le reste)
        item_rows = []
        for i, (basket_factor, status) in enumerate(contexts, start=1):
            sale_id = base_id + i
            n_lines = max(1, int(round(rng.randint(lines_min, lines_max)
                                       * (0.6 + 0.4 * basket_factor))))
            picked: set[int] = set()
            for pid in rng.choices(prod_ids, weights=prod_weights, k=n_lines):
                if pid in picked:
                    continue
                picked.add(pid)
                prod = by_id[pid]
                qty = float(_pick_quantity(rng, prod["base_price"]))
                if basket_factor > 2:                 # professionnels, institutions
                    qty *= rng.choice([2, 3, 4])
                discount = 0.0
                if rng.random() < 0.07:               # remise ponctuelle
                    discount = round(prod["price"] * qty * rng.choice([0.05, 0.10, 0.15]), 2)
                item_rows.append((sale_id, pid, qty, prod["price"], prod["cost"], discount))
                if status == "payée":
                    demand[pid] = demand.get(pid, 0.0) + qty
                    prod["stock_sim"] -= qty
                    prod["sold"] += qty
        conn.executemany(
            """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, unit_cost, discount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            item_rows,
        )
        if offset % 15 == 0:
            conn.commit()
    conn.commit()

    # Une commande en cours de livraison, visible dans le département Achats
    step("Commandes fournisseurs en cours…", 0.86)
    last_month = sorted(monthly_demand)[-1] if monthly_demand else None
    pending = {}
    if last_month:
        for pid, qty in sorted(monthly_demand[last_month].items(),
                               key=lambda kv: -kv[1])[:8]:
            if qty > 1:
                pending[pid] = float(round(qty * 0.6))
    if pending:
        _create_purchase(db, rng, today - timedelta(days=2), supplier_ids, products,
                         pending, status="commandée")

    # ---- 9. Pertes & inventaires (département Stock) -------------------
    step("Écritures d'inventaire et de pertes…", 0.90)
    loss_rows = []
    for _ in range(max(6, n_days // 12)):
        day = start + timedelta(days=rng.randint(0, max(1, n_days - 1)))
        p = _weighted_choice(rng, products, prod_weights)
        kind = rng.choices(["perte", "inventaire", "retour"], [0.55, 0.3, 0.15])[0]
        qty = -round(rng.uniform(1, 6), 1) if kind != "retour" else round(rng.uniform(1, 3), 1)
        if kind == "inventaire":
            qty = round(rng.uniform(-4, 4), 1)
        loss_rows.append((f"{day.isoformat()} 18:00:00", day.isoformat(), p["id"], qty, kind,
                          "STOCK", None,
                          {"perte": "Casse / péremption", "inventaire": "Écart d'inventaire",
                           "retour": "Retour client"}[kind]))
    db.executemany(
        """INSERT INTO stock_moves (moved_at, move_date, product_id, quantity, move_type,
                                    source_dept, ref, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        loss_rows,
    )

    # ---- 10. Charges & paie (département Finance / RH) -----------------
    step("Charges d'exploitation et paie…", 0.94)
    months = sorted(monthly_demand) or [today.strftime("%Y-%m")]
    # Les charges d'exploitation sont calées sur la MARGE BRUTE du mois, pas sur
    # le chiffre d'affaires : une activité à faible marge (électronique) ne
    # supporte pas la même structure de coûts qu'une activité à forte marge.
    margin_by_month = {
        r["period"]: (r["gross_margin"] or 0)
        for r in db.query("SELECT period, gross_margin FROM v_sales_monthly")
    }
    payroll_target = db.scalar("SELECT COALESCE(SUM(salary), 0) FROM employees WHERE active = 1")
    expense_rows, payroll_rows = [], []
    for month_key in months:
        first = datetime.strptime(month_key + "-01", "%Y-%m-%d").date()
        margin = margin_by_month.get(month_key, 0) or 0
        # 30 % à 45 % de la marge brute part en charges de structure, le reste
        # doit couvrir la masse salariale et dégager le résultat.
        budget = max(margin * rng.uniform(0.30, 0.45) - payroll_target,
                     len(spec["expense_lines"]) * 25000 * scale)
        shares = [rng.uniform(0.6, 1.6) for _ in spec["expense_lines"]]
        total_share = sum(shares)
        for label, share in zip(spec["expense_lines"], shares):
            expense_rows.append((
                min(first + timedelta(days=rng.randint(0, 26)), today).isoformat(),
                label, _expense_category(label),
                _expense_department(label),
                _round_price(budget * share / total_share, decimals), None,
            ))
        for emp in db.query("SELECT id, salary FROM employees WHERE active = 1"):
            bonus = _round_price(emp["salary"] * rng.uniform(0, 0.12), decimals)
            gross = emp["salary"] + bonus
            payroll_rows.append((month_key, emp["id"], emp["salary"], bonus,
                                 _round_price(gross * 0.86, decimals),
                                 min(first + timedelta(days=27), today).isoformat()))
    db.executemany(
        "INSERT INTO expenses (spent_on, label, category, department, amount, note)"
        " VALUES (?, ?, ?, ?, ?, ?)", expense_rows)
    db.executemany(
        "INSERT INTO payroll (period, employee_id, gross, bonus, net, paid_on)"
        " VALUES (?, ?, ?, ?, ?, ?)", payroll_rows)

    # ---- 11. Journal & résumé ------------------------------------------
    step("Consolidation des tableaux de bord…", 0.98)
    db.log("SYSTEM", "company", "création", 1,
           f"ERP « {name} » ({spec['label']}) généré sur {history_months} mois.")

    summary = {
        "company": name.strip(),
        "store_type": store_type,
        "store_label": spec["label"],
        "currency": cur["code"],
        "period_start": start.isoformat(),
        "period_end": today.isoformat(),
        "categories": db.scalar("SELECT COUNT(*) FROM categories"),
        "products": db.scalar("SELECT COUNT(*) FROM products"),
        "suppliers": db.scalar("SELECT COUNT(*) FROM suppliers"),
        "customers": db.scalar("SELECT COUNT(*) FROM customers"),
        "employees": db.scalar("SELECT COUNT(*) FROM employees"),
        "sales": db.scalar("SELECT COUNT(*) FROM sales"),
        "sale_items": db.scalar("SELECT COUNT(*) FROM sale_items"),
        "purchases": db.scalar("SELECT COUNT(*) FROM purchases"),
        "stock_moves": db.scalar("SELECT COUNT(*) FROM stock_moves"),
        "revenue": db.scalar("SELECT COALESCE(SUM(total),0) FROM sales WHERE status='payée'"),
        "stock_value": db.scalar("SELECT COALESCE(SUM(stock*cost_price),0) FROM products"),
    }
    step("Terminé.", 1.0)
    return summary


def _pick_quantity(rng: random.Random, base_price: float) -> int:
    """Quantité vendue par ligne, corrélée à la gamme de prix de l'article.

    On n'achète pas un téléviseur comme on achète du savon : les articles
    chers partent à l'unité, les produits de grande consommation par lots.
    """
    if base_price >= 40000:
        return rng.choices([1, 2], [95, 5])[0]
    if base_price >= 12000:
        return rng.choices([1, 2, 3], [86, 11, 3])[0]
    if base_price >= 3000:
        return rng.choices([1, 2, 3, 4], [68, 22, 7, 3])[0]
    if base_price >= 800:
        return rng.choices([1, 2, 3, 4, 6], [46, 27, 13, 9, 5])[0]
    return rng.choices([1, 2, 3, 4, 6, 12], [30, 26, 16, 14, 10, 4])[0]


def _create_purchase(db: Database, rng: random.Random, day: date,
                     supplier_ids: list[int], products: list[dict],
                     qty_by_product: dict[int, float], status: str = "reçue") -> None:
    """Crée une (ou plusieurs) commandes fournisseur groupées par fournisseur."""
    by_supplier: dict[int, list[tuple[int, float]]] = {}
    supplier_of = {
        r["id"]: r["supplier_id"]
        for r in db.query("SELECT id, supplier_id FROM products")
    }
    for pid, qty in qty_by_product.items():
        if qty <= 0:
            continue
        sid = supplier_of.get(pid) or rng.choice(supplier_ids)
        by_supplier.setdefault(sid, []).append((pid, float(qty)))

    costs = {r["id"]: r["cost_price"] for r in db.query("SELECT id, cost_price FROM products")}
    conn = db.conn
    for n, (sid, lines) in enumerate(sorted(by_supplier.items()), start=1):
        ref = f"AC-{day.strftime('%y%m%d')}-{sid:02d}{n:02d}"
        cur = conn.execute(
            """INSERT INTO purchases (ref, ordered_on, received_on, supplier_id, status)
               VALUES (?, ?, ?, ?, ?)""",
            (ref, day.isoformat(),
             (day + timedelta(days=rng.randint(1, 6))).isoformat() if status == "reçue" else None,
             sid, status),
        )
        pid_rows = [
            (cur.lastrowid, pid, qty, round(costs.get(pid, 100) * rng.uniform(0.94, 1.06), 2))
            for pid, qty in lines
        ]
        conn.executemany(
            "INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost)"
            " VALUES (?, ?, ?, ?)", pid_rows)
    conn.commit()


def _expense_category(label: str) -> str:
    mapping = {
        "Loyer": "Immobilier", "Loyer dépôt": "Immobilier", "Loyer centre-ville": "Immobilier",
        "Électricité": "Énergie", "Gaz": "Énergie", "Eau": "Énergie",
        "Groupe électrogène": "Énergie", "Chaîne du froid": "Énergie",
        "Transport": "Logistique", "Carburant livraison": "Logistique",
        "Transitaire & douane": "Logistique", "Livraison plateforme": "Logistique",
        "Marketing": "Commercial", "Publicité": "Commercial",
        "Publicité réseaux sociaux": "Commercial", "Décoration vitrine": "Commercial",
        "Assurance": "Administratif", "Assurance marchandises": "Administratif",
        "Licences logiciel": "Administratif", "Licences & taxes": "Administratif",
    }
    return mapping.get(label, "Exploitation")


def _expense_department(label: str) -> str:
    if label.startswith("Loyer") or label in ("Assurance", "Licences logiciel", "Licences & taxes"):
        return "FIN"
    if label in ("Marketing", "Publicité", "Publicité réseaux sociaux", "Décoration vitrine"):
        return "SALES"
    if label in ("Transport", "Carburant livraison", "Transitaire & douane", "Livraison plateforme"):
        return "PURCH"
    if label in ("Formation continue",):
        return "HR"
    return "STOCK"
