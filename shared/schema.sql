-- =====================================================================
--  ERP Boutique — Schéma SQL central
--  ---------------------------------------------------------------
--  Source unique de vérité partagée par TOUS les clients :
--    - le dashboard R Shiny      (shiny/)
--    - le dashboard Python/Dash  (python/dash_app/)
--    - l'API REST FastAPI        (python/api/)
--    - le front web HTML/CSS/JS  (web/)
--    - l'application Angular     (angular/)
--
--  Principe « données des départements centrées » :
--  chaque département (Ventes, Stock, Achats, CRM, RH, Finance) écrit
--  dans les MÊMES tables. Les triggers propagent automatiquement une
--  écriture d'un département vers les autres :
--     une ligne de vente      -> mouvement de stock sortant + total vente
--     une ligne d'achat       -> mouvement de stock entrant + coût moyen
--     un mouvement de stock   -> niveau de stock du produit
--     tout                    -> vues financières consolidées
--
--  Dialecte : SQLite 3 (portable, zéro serveur). Les types sont écrits
--  en SQL standard pour faciliter un portage PostgreSQL/MySQL.
-- =====================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------
-- 0. Métadonnées applicatives
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 1. Entreprise (ligne unique, créée à l'onboarding)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    name         TEXT    NOT NULL,
    store_type   TEXT    NOT NULL,          -- clé dans shared/store_types.json
    store_label  TEXT    NOT NULL,
    currency     TEXT    NOT NULL DEFAULT 'XOF',
    currency_sym TEXT    NOT NULL DEFAULT 'FCFA',
    tax_rate     REAL    NOT NULL DEFAULT 0.18,
    city         TEXT,
    country      TEXT,
    opened_on    TEXT,
    logo_emoji   TEXT    DEFAULT '🏪',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 2. Départements — l'axe de centralisation des données
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT UNIQUE NOT NULL,          -- SALES, STOCK, PURCH, CRM, HR, FIN
    name      TEXT NOT NULL,
    icon      TEXT,
    position  INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------
-- 3. Référentiels
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    margin_target REAL DEFAULT 0.25
);

CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    contact_name   TEXT,
    phone          TEXT,
    email          TEXT,
    lead_time_days INTEGER NOT NULL DEFAULT 7,
    rating         REAL    NOT NULL DEFAULT 4.0 CHECK (rating BETWEEN 0 AND 5),
    active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    supplier_id   INTEGER REFERENCES suppliers(id),
    unit          TEXT NOT NULL DEFAULT 'pièce',
    cost_price    REAL NOT NULL CHECK (cost_price >= 0),
    sale_price    REAL NOT NULL CHECK (sale_price >= 0),
    stock         REAL NOT NULL DEFAULT 0,   -- maintenu par les triggers
    reorder_point REAL NOT NULL DEFAULT 10,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    segment        TEXT NOT NULL DEFAULT 'Particulier',
    phone          TEXT,
    email          TEXT,
    city           TEXT,
    loyalty_points INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employees (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL,
    department   TEXT NOT NULL,
    salary       REAL NOT NULL DEFAULT 0,
    phone        TEXT,
    hired_on     TEXT,
    active       INTEGER NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------
-- 4. Ventes (département VENTES)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ref            TEXT UNIQUE NOT NULL,
    sold_at        TEXT NOT NULL,            -- 'YYYY-MM-DD HH:MM:SS'
    sale_date      TEXT NOT NULL,            -- 'YYYY-MM-DD' (dénormalisé pour l'agrégation)
    customer_id    INTEGER REFERENCES customers(id),
    employee_id    INTEGER REFERENCES employees(id),
    payment_method TEXT NOT NULL DEFAULT 'Espèces',
    channel        TEXT NOT NULL DEFAULT 'Boutique',
    status         TEXT NOT NULL DEFAULT 'payée',  -- payée | en attente | annulée
    subtotal       REAL NOT NULL DEFAULT 0,   -- HT, maintenu par trigger
    tax_amount     REAL NOT NULL DEFAULT 0,
    total          REAL NOT NULL DEFAULT 0,   -- TTC
    cost_total     REAL NOT NULL DEFAULT 0,   -- COGS, maintenu par trigger
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sale_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id    INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   REAL NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL,
    unit_cost  REAL NOT NULL DEFAULT 0,
    discount   REAL NOT NULL DEFAULT 0,
    line_total REAL GENERATED ALWAYS AS (quantity * unit_price - discount) STORED
);

-- ---------------------------------------------------------------------
-- 5. Achats (département ACHATS)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ref          TEXT UNIQUE NOT NULL,
    ordered_on   TEXT NOT NULL,
    received_on  TEXT,
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id),
    status       TEXT NOT NULL DEFAULT 'reçue',  -- brouillon | commandée | reçue | annulée
    total        REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    REAL NOT NULL CHECK (quantity > 0),
    unit_cost   REAL NOT NULL,
    line_total  REAL GENERATED ALWAYS AS (quantity * unit_cost) STORED
);

-- ---------------------------------------------------------------------
-- 6. Stock (département STOCK) — journal de tous les mouvements
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_moves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    moved_at    TEXT NOT NULL DEFAULT (datetime('now')),
    move_date   TEXT NOT NULL,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    REAL NOT NULL,              -- signé : + entrée / - sortie
    move_type   TEXT NOT NULL,              -- achat | vente | inventaire | perte | retour
    source_dept TEXT NOT NULL DEFAULT 'STOCK',
    ref         TEXT,
    note        TEXT
);

-- ---------------------------------------------------------------------
-- 7. Finance (département FINANCE)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    spent_on    TEXT NOT NULL,
    label       TEXT NOT NULL,
    category    TEXT NOT NULL,
    department  TEXT NOT NULL DEFAULT 'FIN',
    amount      REAL NOT NULL CHECK (amount >= 0),
    note        TEXT
);

CREATE TABLE IF NOT EXISTS payroll (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period      TEXT NOT NULL,              -- 'YYYY-MM'
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    gross       REAL NOT NULL,
    bonus       REAL NOT NULL DEFAULT 0,
    net         REAL NOT NULL,
    paid_on     TEXT,
    UNIQUE (period, employee_id)
);

-- ---------------------------------------------------------------------
-- 8. Journal d'audit inter-départements
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    happened_at TEXT NOT NULL DEFAULT (datetime('now')),
    department  TEXT NOT NULL,
    entity      TEXT NOT NULL,
    entity_id   INTEGER,
    action      TEXT NOT NULL,
    detail      TEXT
);

-- ---------------------------------------------------------------------
-- 9. Index
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sales_date       ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer   ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_employee   ON sales(employee_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale  ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_prod  ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_moves_product    ON stock_moves(product_id);
CREATE INDEX IF NOT EXISTS idx_moves_date       ON stock_moves(move_date);
CREATE INDEX IF NOT EXISTS idx_products_cat     ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_purch_items_pur  ON purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date    ON expenses(spent_on);

-- =====================================================================
-- 10. TRIGGERS — la centralisation en action
-- =====================================================================

-- 10.1 Une ligne de vente sort du stock et alimente le total de la vente
CREATE TRIGGER IF NOT EXISTS trg_sale_item_insert
AFTER INSERT ON sale_items
BEGIN
    INSERT INTO stock_moves (moved_at, move_date, product_id, quantity, move_type, source_dept, ref)
    SELECT s.sold_at, s.sale_date, NEW.product_id, -NEW.quantity, 'vente', 'SALES', s.ref
    FROM sales s WHERE s.id = NEW.sale_id;

    UPDATE products
       SET stock = stock - NEW.quantity
     WHERE id = NEW.product_id;

    UPDATE sales
       SET subtotal   = subtotal + NEW.line_total,
           cost_total = cost_total + (NEW.unit_cost * NEW.quantity),
           tax_amount = (subtotal + NEW.line_total) * (SELECT tax_rate FROM company WHERE id = 1),
           total      = (subtotal + NEW.line_total) * (1 + (SELECT tax_rate FROM company WHERE id = 1))
     WHERE id = NEW.sale_id;
END;

-- 10.2 Une ligne d'achat DÉJÀ REÇUE entre en stock et met à jour le coût de revient.
--      Une commande encore en cours de livraison n'impacte pas le stock.
CREATE TRIGGER IF NOT EXISTS trg_purchase_item_insert
AFTER INSERT ON purchase_items
BEGIN
    INSERT INTO stock_moves (moved_at, move_date, product_id, quantity, move_type, source_dept, ref)
    SELECT p.ordered_on || ' 09:00:00', COALESCE(p.received_on, p.ordered_on),
           NEW.product_id, NEW.quantity, 'achat', 'PURCH', p.ref
    FROM purchases p WHERE p.id = NEW.purchase_id AND p.status = 'reçue';

    UPDATE products
       SET stock      = stock + NEW.quantity,
           cost_price = ROUND((cost_price * 0.7) + (NEW.unit_cost * 0.3), 2)  -- coût moyen lissé
     WHERE id = NEW.product_id
       AND (SELECT status FROM purchases WHERE id = NEW.purchase_id) = 'reçue';

    UPDATE purchases
       SET total = total + NEW.line_total
     WHERE id = NEW.purchase_id;
END;

-- 10.2 bis  Réception d'une commande : Achats -> Stock en un seul changement d'état
CREATE TRIGGER IF NOT EXISTS trg_purchase_received
AFTER UPDATE OF status ON purchases
WHEN NEW.status = 'reçue' AND OLD.status <> 'reçue'
BEGIN
    INSERT INTO stock_moves (moved_at, move_date, product_id, quantity, move_type, source_dept, ref)
    SELECT datetime('now'), COALESCE(NEW.received_on, date('now')),
           pi.product_id, pi.quantity, 'achat', 'PURCH', NEW.ref
    FROM purchase_items pi WHERE pi.purchase_id = NEW.id;

    UPDATE products
       SET stock = stock + (SELECT COALESCE(SUM(pi.quantity), 0) FROM purchase_items pi
                             WHERE pi.purchase_id = NEW.id AND pi.product_id = products.id)
     WHERE id IN (SELECT product_id FROM purchase_items WHERE purchase_id = NEW.id);

    INSERT INTO audit_log (department, entity, entity_id, action, detail)
    VALUES ('PURCH', 'purchases', NEW.id, 'réception',
            'Commande ' || NEW.ref || ' réceptionnée en stock.');
END;

-- 10.3 Tout mouvement de stock saisi manuellement (inventaire, perte, retour)
--      ajuste le niveau de stock du produit
CREATE TRIGGER IF NOT EXISTS trg_stock_move_manual
AFTER INSERT ON stock_moves
WHEN NEW.move_type IN ('inventaire', 'perte', 'retour')
BEGIN
    UPDATE products SET stock = stock + NEW.quantity WHERE id = NEW.product_id;
END;

-- 10.4 Fidélité client : 1 point par tranche de 1000 encaissée
CREATE TRIGGER IF NOT EXISTS trg_sale_loyalty
AFTER UPDATE OF total ON sales
WHEN NEW.customer_id IS NOT NULL AND NEW.status = 'payée'
BEGIN
    UPDATE customers
       SET loyalty_points = loyalty_points + CAST((NEW.total - OLD.total) / 1000 AS INTEGER)
     WHERE id = NEW.customer_id;
END;

-- =====================================================================
-- 11. VUES — lecture consolidée, identique pour R, Python, l'API et le web
-- =====================================================================

-- 11.1 Catalogue enrichi
CREATE VIEW IF NOT EXISTS v_products AS
SELECT p.id, p.sku, p.name, c.name AS category, s.name AS supplier,
       p.unit, p.cost_price, p.sale_price,
       ROUND(p.sale_price - p.cost_price, 2)                                    AS unit_margin,
       CASE WHEN p.sale_price > 0
            THEN ROUND((p.sale_price - p.cost_price) / p.sale_price, 4) END     AS margin_rate,
       p.stock, p.reorder_point,
       ROUND(p.stock * p.cost_price, 2)                                         AS stock_value,
       CASE WHEN p.stock <= 0                 THEN 'rupture'
            WHEN p.stock <= p.reorder_point   THEN 'alerte'
            WHEN p.stock <= p.reorder_point*2 THEN 'faible'
            ELSE 'ok' END                                                       AS stock_status,
       p.active
FROM products p
JOIN categories c ON c.id = p.category_id
LEFT JOIN suppliers s ON s.id = p.supplier_id;

-- 11.2 Ventes par jour
CREATE VIEW IF NOT EXISTS v_sales_daily AS
SELECT sale_date,
       COUNT(*)                                   AS tickets,
       ROUND(SUM(total), 2)                       AS revenue,
       ROUND(SUM(subtotal), 2)                    AS revenue_ht,
       ROUND(SUM(cost_total), 2)                  AS cogs,
       ROUND(SUM(subtotal - cost_total), 2)       AS gross_margin,
       ROUND(AVG(total), 2)                       AS avg_basket
FROM sales
WHERE status = 'payée'
GROUP BY sale_date;

-- 11.3 Ventes par mois
CREATE VIEW IF NOT EXISTS v_sales_monthly AS
SELECT substr(sale_date, 1, 7)                    AS period,
       COUNT(*)                                   AS tickets,
       ROUND(SUM(total), 2)                       AS revenue,
       ROUND(SUM(subtotal), 2)                    AS revenue_ht,
       ROUND(SUM(cost_total), 2)                  AS cogs,
       ROUND(SUM(subtotal - cost_total), 2)       AS gross_margin,
       ROUND(AVG(total), 2)                       AS avg_basket
FROM sales
WHERE status = 'payée'
GROUP BY substr(sale_date, 1, 7);

-- 11.4 Performance produit
CREATE VIEW IF NOT EXISTS v_product_performance AS
SELECT p.id AS product_id, p.name AS product, c.name AS category,
       ROUND(SUM(si.quantity), 2)                        AS qty_sold,
       ROUND(SUM(si.line_total), 2)                      AS revenue_ht,
       ROUND(SUM(si.line_total - si.unit_cost * si.quantity), 2) AS margin,
       COUNT(DISTINCT si.sale_id)                        AS tickets
FROM sale_items si
JOIN sales s    ON s.id = si.sale_id AND s.status = 'payée'
JOIN products p ON p.id = si.product_id
JOIN categories c ON c.id = p.category_id
GROUP BY p.id, p.name, c.name;

-- 11.5 Alertes de réapprovisionnement (Stock -> Achats)
CREATE VIEW IF NOT EXISTS v_stock_alerts AS
SELECT p.id AS product_id, p.sku, p.name AS product, c.name AS category,
       s.name AS supplier, s.lead_time_days,
       p.stock, p.reorder_point, p.unit,
       ROUND(MAX(p.reorder_point * 2 - p.stock, 0), 2) AS suggested_qty,
       ROUND(MAX(p.reorder_point * 2 - p.stock, 0) * p.cost_price, 2) AS suggested_cost,
       CASE WHEN p.stock <= 0 THEN 'rupture' ELSE 'alerte' END AS severity
FROM products p
JOIN categories c ON c.id = p.category_id
LEFT JOIN suppliers s ON s.id = p.supplier_id
WHERE p.active = 1 AND p.stock <= p.reorder_point;

-- 11.6 Valeur client (CRM)
CREATE VIEW IF NOT EXISTS v_customer_value AS
SELECT cu.id AS customer_id, cu.name AS customer, cu.segment, cu.city, cu.loyalty_points,
       COUNT(s.id)                        AS orders,
       ROUND(COALESCE(SUM(s.total), 0), 2) AS lifetime_value,
       ROUND(COALESCE(AVG(s.total), 0), 2) AS avg_basket,
       MAX(s.sale_date)                    AS last_purchase,
       CAST(julianday('now') - julianday(MAX(s.sale_date)) AS INTEGER) AS days_since_last
FROM customers cu
LEFT JOIN sales s ON s.customer_id = cu.id AND s.status = 'payée'
GROUP BY cu.id, cu.name, cu.segment, cu.city, cu.loyalty_points;

-- 11.7 Performance vendeur (Ventes + RH)
CREATE VIEW IF NOT EXISTS v_employee_performance AS
SELECT e.id AS employee_id, e.name AS employee, e.role, e.department, e.salary,
       COUNT(s.id)                          AS tickets,
       ROUND(COALESCE(SUM(s.total), 0), 2)  AS revenue,
       ROUND(COALESCE(AVG(s.total), 0), 2)  AS avg_basket
FROM employees e
LEFT JOIN sales s ON s.employee_id = e.id AND s.status = 'payée'
WHERE e.active = 1
GROUP BY e.id, e.name, e.role, e.department, e.salary;

-- 11.8 Compte de résultat mensuel consolidé (toutes sources)
CREATE VIEW IF NOT EXISTS v_financial_monthly AS
WITH months AS (
    SELECT DISTINCT substr(sale_date, 1, 7) AS period FROM sales
    UNION SELECT DISTINCT substr(spent_on, 1, 7) FROM expenses
    UNION SELECT DISTINCT period FROM payroll
)
SELECT m.period,
       ROUND(COALESCE((SELECT SUM(total)      FROM sales WHERE substr(sale_date,1,7)=m.period AND status='payée'), 0), 2) AS revenue,
       ROUND(COALESCE((SELECT SUM(cost_total) FROM sales WHERE substr(sale_date,1,7)=m.period AND status='payée'), 0), 2) AS cogs,
       ROUND(COALESCE((SELECT SUM(amount)     FROM expenses WHERE substr(spent_on,1,7)=m.period), 0), 2)                  AS expenses,
       ROUND(COALESCE((SELECT SUM(net)        FROM payroll  WHERE period=m.period), 0), 2)                                AS payroll,
       ROUND(
           COALESCE((SELECT SUM(subtotal - cost_total) FROM sales WHERE substr(sale_date,1,7)=m.period AND status='payée'), 0)
         - COALESCE((SELECT SUM(amount) FROM expenses WHERE substr(spent_on,1,7)=m.period), 0)
         - COALESCE((SELECT SUM(net)    FROM payroll  WHERE period=m.period), 0), 2)                                      AS net_result
FROM months m
ORDER BY m.period;

-- 11.9 Tableau de bord par département — la vue « données centrées »
CREATE VIEW IF NOT EXISTS v_department_dashboard AS
SELECT 'SALES' AS dept, 'Ventes'  AS name, 'Chiffre d''affaires (30 j)' AS metric,
       ROUND(COALESCE((SELECT SUM(total) FROM sales
                        WHERE status='payée' AND sale_date >= date('now','-30 day')), 0), 2) AS value
UNION ALL
SELECT 'STOCK', 'Stock', 'Valeur du stock',
       ROUND(COALESCE((SELECT SUM(stock * cost_price) FROM products WHERE active=1), 0), 2)
UNION ALL
SELECT 'PURCH', 'Achats', 'Achats (30 j)',
       ROUND(COALESCE((SELECT SUM(total) FROM purchases
                        WHERE ordered_on >= date('now','-30 day') AND status <> 'annulée'), 0), 2)
UNION ALL
SELECT 'CRM', 'Clients', 'Clients actifs (90 j)',
       COALESCE((SELECT COUNT(DISTINCT customer_id) FROM sales
                  WHERE status='payée' AND sale_date >= date('now','-90 day')), 0)
UNION ALL
SELECT 'HR', 'Ressources humaines', 'Masse salariale mensuelle',
       ROUND(COALESCE((SELECT SUM(salary) FROM employees WHERE active=1), 0), 2)
UNION ALL
SELECT 'FIN', 'Finance', 'Résultat net (mois en cours)',
       ROUND(COALESCE((SELECT net_result FROM v_financial_monthly
                        WHERE period = strftime('%Y-%m','now')), 0), 2);
