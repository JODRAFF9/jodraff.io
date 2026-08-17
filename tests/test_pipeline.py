#!/usr/bin/env python3
"""Tests du pipeline, de l'onboarding aux vues consolidées.

Objectif : vérifier que la chaîne complète tient, étape par étape.

    1. le schéma SQL s'applique et les triggers propagent les écritures
    2. le générateur produit une entreprise cohérente pour chaque métier
    3. les requêtes métier répondent sur toutes les vues
    4. les écritures (vente, mouvement, réception) respectent les invariants
    5. l'API REST expose le tout sans régression

Exécution :

    python3 tests/test_pipeline.py          # sans dépendance
    pytest tests/test_pipeline.py -v        # si pytest est installé
"""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from erp import queries as q  # noqa: E402
from erp.config import STORE_TYPES  # noqa: E402
from erp.database import Database  # noqa: E402
from erp.generator import create_company  # noqa: E402

# Un historique court garde la suite rapide ; les invariants sont les mêmes.
FAST = {"history_months": 3, "traffic_scale": 0.4}


# ==========================================================================
# Utilitaires
# ==========================================================================
_compteur = itertools.count()


def fresh_db(tmp: Path, name: str) -> Database:
    """Base neuve et isolée : un fichier distinct par appel.

    Réutiliser un nom de fichier ferait travailler deux tests sur la même
    base, et invaliderait silencieusement les comparaisons entre bases.
    """
    return Database(tmp / f"{name}-{next(_compteur)}.db")


def make_company(tmp: Path, store_type: str = "generique", **kwargs) -> Database:
    db = fresh_db(tmp, store_type)
    create_company("Boutique de test", store_type, db=db, **{**FAST, **kwargs})
    return db


def stock_of(db: Database, product_id: int) -> float:
    return db.scalar("SELECT stock FROM products WHERE id = ?", (product_id,))


# ==========================================================================
# 1. Schéma et triggers, la centralisation des départements
# ==========================================================================
def test_schema_applique_tables_triggers_et_vues(tmp: Path) -> None:
    """Le schéma partagé crée bien tout l'appareillage SQL."""
    db = fresh_db(tmp, "schema")
    kinds = dict(db.query(
        "SELECT type, COUNT(*) AS n FROM sqlite_master GROUP BY type"))
    counts = {r["type"]: r["n"] for r in db.query(
        "SELECT type, COUNT(*) AS n FROM sqlite_master GROUP BY type")}
    assert counts.get("table", 0) >= 16, f"tables manquantes : {counts}"
    assert counts.get("trigger", 0) == 5, "les 5 triggers doivent exister"
    assert counts.get("view", 0) == 9, "les 9 vues consolidées doivent exister"
    assert kinds is not None


def test_schema_est_rejouable(tmp: Path) -> None:
    """Appliquer le schéma deux fois ne casse rien (CREATE IF NOT EXISTS)."""
    path = tmp / "rejouable.db"
    Database(path).close()
    db = Database(path)          # deuxième application
    assert db.scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'") == 5


def test_vente_decharge_le_stock_et_alimente_la_finance(tmp: Path) -> None:
    """Une ligne de vente touche Ventes, Stock et Finance en une écriture."""
    db = make_company(tmp, "generique")
    product = db.one("SELECT id, sale_price, cost_price, stock FROM products LIMIT 1")
    before = product["stock"]
    moves_before = db.scalar("SELECT COUNT(*) FROM stock_moves")

    sale = q.register_sale([{"product_id": product["id"], "quantity": 3}], db=db)

    assert stock_of(db, product["id"]) == before - 3, "le stock doit être déchargé"
    assert db.scalar("SELECT COUNT(*) FROM stock_moves") == moves_before + 1
    move = db.one("SELECT * FROM stock_moves ORDER BY id DESC LIMIT 1")
    assert move["move_type"] == "vente" and move["source_dept"] == "SALES"
    assert move["quantity"] == -3

    tax_rate = db.scalar("SELECT tax_rate FROM company")
    expected = product["sale_price"] * 3
    assert abs(sale["subtotal"] - expected) < 0.01, "sous-total = somme des lignes"
    assert abs(sale["total"] - expected * (1 + tax_rate)) < 0.01, "TTC = HT + TVA"
    assert abs(sale["cost_total"] - product["cost_price"] * 3) < 0.01


def test_commande_fournisseur_nentre_en_stock_qua_la_reception(tmp: Path) -> None:
    """Une commande en cours ne gonfle pas le stock ; sa réception, oui."""
    db = make_company(tmp, "generique")
    product = db.one("SELECT id FROM products LIMIT 1")
    before = stock_of(db, product["id"])

    order = q.create_purchase_order(1, [{"product_id": product["id"], "quantity": 25}], db=db)
    assert order["status"] == "commandée"
    assert stock_of(db, product["id"]) == before, "commande non reçue : stock inchangé"

    q.receive_purchase(order["id"], db=db)
    assert stock_of(db, product["id"]) == before + 25, "réception : stock crédité"

    trace = db.one("SELECT * FROM audit_log WHERE action = 'réception' ORDER BY id DESC")
    assert trace is not None and trace["department"] == "PURCH"


def test_mouvement_manuel_ajuste_le_stock(tmp: Path) -> None:
    """Inventaire, perte et retour passent par le même journal."""
    db = make_company(tmp, "generique")
    product = db.one("SELECT id FROM products LIMIT 1")
    before = stock_of(db, product["id"])

    for move_type, qty in (("perte", -4), ("retour", 2), ("inventaire", -1.5)):
        result = q.register_stock_move(product["id"], qty, move_type, db=db)
        before += qty
        assert abs(result["new_stock"] - before) < 0.01, f"{move_type} mal appliqué"


def test_fidelite_client_credite_a_lencaissement(tmp: Path) -> None:
    """Le CRM se met à jour depuis les Ventes, sans code applicatif."""
    db = make_company(tmp, "generique")
    customer = db.one("SELECT id, loyalty_points FROM customers LIMIT 1")
    product = db.one("SELECT id, sale_price FROM products ORDER BY sale_price DESC LIMIT 1")

    q.register_sale([{"product_id": product["id"], "quantity": 5}],
                    customer_id=customer["id"], db=db)

    after = db.scalar("SELECT loyalty_points FROM customers WHERE id = ?", (customer["id"],))
    assert after > customer["loyalty_points"], "les points doivent progresser"


def test_colonne_generee_line_total(tmp: Path) -> None:
    """line_total est calculée par la base : elle ne peut pas diverger."""
    db = make_company(tmp, "generique")
    row = db.one("SELECT quantity, unit_price, discount, line_total FROM sale_items LIMIT 1")
    expected = row["quantity"] * row["unit_price"] - row["discount"]
    assert abs(row["line_total"] - expected) < 0.01


def test_vente_vide_est_refusee(tmp: Path) -> None:
    db = make_company(tmp, "generique")
    try:
        q.register_sale([], db=db)
    except ValueError:
        return
    raise AssertionError("une vente sans ligne doit être refusée")


def test_type_de_mouvement_invalide_est_refuse(tmp: Path) -> None:
    db = make_company(tmp, "generique")
    product = db.one("SELECT id FROM products LIMIT 1")
    try:
        q.register_stock_move(product["id"], 1, "cadeau", db=db)
    except ValueError:
        return
    raise AssertionError("un type de mouvement inconnu doit être refusé")


# ==========================================================================
# 2. Générateur, un métier, une entreprise cohérente
# ==========================================================================
def test_tous_les_metiers_se_generent(tmp: Path) -> None:
    """Les 7 métiers du catalogue produisent une base exploitable."""
    for store_type in STORE_TYPES:
        db = make_company(tmp, store_type)
        summary = {
            "produits": db.scalar("SELECT COUNT(*) FROM products"),
            "ventes": db.scalar("SELECT COUNT(*) FROM sales"),
            "employés": db.scalar("SELECT COUNT(*) FROM employees"),
        }
        assert summary["produits"] > 0, f"{store_type} : catalogue vide"
        assert summary["ventes"] > 0, f"{store_type} : aucune vente"
        assert summary["employés"] > 0, f"{store_type} : aucun salarié"
        db.close()


def test_invariants_comptables_et_de_stock(tmp: Path) -> None:
    """Les grands invariants de la base, sur chaque métier."""
    for store_type in STORE_TYPES:
        db = make_company(tmp, store_type)

        ecarts_stock = db.scalar(
            """SELECT COUNT(*) FROM products p WHERE ABS(p.stock -
                 COALESCE((SELECT SUM(quantity) FROM stock_moves
                            WHERE product_id = p.id), 0)) > 0.01""")
        assert ecarts_stock == 0, f"{store_type} : stock ≠ somme des mouvements"

        ecarts_vente = db.scalar(
            """SELECT COUNT(*) FROM sales s WHERE ABS(s.subtotal -
                 COALESCE((SELECT SUM(line_total) FROM sale_items
                            WHERE sale_id = s.id), 0)) > 0.01""")
        assert ecarts_vente == 0, f"{store_type} : sous-total ≠ somme des lignes"

        assert db.query("PRAGMA foreign_key_check") == [], f"{store_type} : clés étrangères"
        assert db.scalar("SELECT COUNT(*) FROM pragma_integrity_check()"
                         " WHERE integrity_check <> 'ok'") == 0
        db.close()


def test_stock_final_positif_et_valorise(tmp: Path) -> None:
    """Régression : le réapprovisionnement doit laisser un stock crédible.

    Un stock global négatif signifie que l'acheteur simulé sous-commande, c'est le défaut qu'avait la boucle mensuelle de la version R.
    """
    for store_type in STORE_TYPES:
        db = make_company(tmp, store_type)
        valeur = db.scalar("SELECT COALESCE(SUM(stock * cost_price), 0) FROM products")
        negatifs = db.scalar("SELECT COUNT(*) FROM products WHERE stock < 0")
        total = db.scalar("SELECT COUNT(*) FROM products")
        assert valeur > 0, f"{store_type} : valeur de stock négative ({valeur:.0f})"
        assert negatifs <= total * 0.35, \
            f"{store_type} : {negatifs}/{total} produits en stock négatif"
        db.close()


def test_aucune_ecriture_dans_le_futur(tmp: Path) -> None:
    """Une charge datée de le mois prochain trahirait un décalage de calendrier."""
    db = make_company(tmp, "supermarche")
    today = date.today().isoformat()
    assert db.scalar("SELECT COUNT(*) FROM sales WHERE sale_date > ?", (today,)) == 0
    assert db.scalar("SELECT COUNT(*) FROM expenses WHERE spent_on > ?", (today,)) == 0
    assert db.scalar("SELECT COUNT(*) FROM stock_moves WHERE move_date > ?", (today,)) == 0


def test_devises_converties(tmp: Path) -> None:
    """Le catalogue est libellé en FCFA ; les autres devises sont converties."""
    xof = make_company(tmp, "electronique", currency="XOF")
    eur = make_company(tmp, "electronique", currency="EUR")
    prix_xof = xof.scalar("SELECT AVG(sale_price) FROM products")
    prix_eur = eur.scalar("SELECT AVG(sale_price) FROM products")
    assert prix_eur < prix_xof / 100, "la conversion en euros n'a pas eu lieu"
    assert eur.company()["currency_sym"] == "€"


def test_seuils_de_reapprovisionnement_definis(tmp: Path) -> None:
    db = make_company(tmp, "pharmacie")
    assert db.scalar("SELECT COUNT(*) FROM products WHERE reorder_point <= 0") == 0


def test_metier_inconnu_refuse(tmp: Path) -> None:
    db = fresh_db(tmp, "inconnu")
    try:
        create_company("X", "boulangerie-imaginaire", db=db, **FAST)
    except KeyError:
        return
    raise AssertionError("un type de boutique inconnu doit être refusé")


def test_nom_vide_refuse(tmp: Path) -> None:
    db = fresh_db(tmp, "sansnom")
    try:
        create_company("   ", "generique", db=db, **FAST)
    except ValueError:
        return
    raise AssertionError("un nom vide doit être refusé")


# ==========================================================================
# 3. Requêtes métier, les six départements répondent
# ==========================================================================
def test_toutes_les_requetes_repondent(tmp: Path) -> None:
    """Chaque fonction de queries.py s'exécute sur une base réelle."""
    db = make_company(tmp, "quincaillerie")
    listes = [
        q.department_summary, q.recent_activity, q.sales_daily, q.sales_monthly,
        q.sales_by_category, q.top_products, q.sales_list, q.products,
        q.stock_alerts, q.stock_valuation, q.stock_moves, q.stock_rotation,
        q.suppliers, q.purchases, q.purchases_monthly, q.reorder_plan,
        q.customers, q.customer_segments, q.dormant_customers, q.customer_acquisition,
        q.employees, q.headcount_by_department, q.payroll_history,
        q.financial_monthly, q.expenses_by_category, q.expenses_by_department,
        q.expenses_list, q.audit_trail,
    ]
    for fonction in listes:
        resultat = fonction(db=db)
        assert isinstance(resultat, list), f"{fonction.__name__} doit renvoyer une liste"

    for dimension in ("payment", "channel", "hour", "weekday"):
        assert q.sales_by_dimension(dimension, db=db)

    kpis = q.kpis(30, db=db)
    for cle in ("revenue", "tickets", "avg_basket", "margin", "margin_rate",
                "stock_value", "stock_alerts", "net_result"):
        assert cle in kpis, f"KPI manquant : {cle}"
    assert kpis["revenue"] > 0

    bridge = q.profit_bridge(db=db)
    assert set(bridge) == {"revenue", "cogs", "expenses", "payroll", "net_result"}


def test_les_six_departements_sont_consolides(tmp: Path) -> None:
    """La vue « données centrées » couvre exactement les six départements."""
    db = make_company(tmp, "restaurant")
    cartes = q.department_summary(db=db)
    assert {c["dept"] for c in cartes} == {"SALES", "STOCK", "PURCH", "CRM", "HR", "FIN"}
    for carte in cartes:
        assert carte["count"] >= 0 and carte["metric"]


def test_alertes_de_stock_coherentes(tmp: Path) -> None:
    """Toute alerte correspond à un produit réellement sous son seuil."""
    db = make_company(tmp, "supermarche")
    for alerte in q.stock_alerts(db=db):
        produit = db.one("SELECT stock, reorder_point FROM products WHERE id = ?",
                         (alerte["product_id"],))
        assert produit["stock"] <= produit["reorder_point"]
        assert alerte["severity"] in ("alerte", "rupture")
        if alerte["severity"] == "rupture":
            assert produit["stock"] <= 0


def test_compte_de_resultat_coherent(tmp: Path) -> None:
    """résultat = marge brute − charges − paie, pour chaque mois."""
    db = make_company(tmp, "mode")
    for mois in q.financial_monthly(db=db):
        marge_brute = db.scalar(
            "SELECT COALESCE(SUM(subtotal - cost_total), 0) FROM sales"
            " WHERE status = 'payée' AND substr(sale_date, 1, 7) = ?", (mois["period"],))
        attendu = marge_brute - mois["expenses"] - mois["payroll"]
        assert abs(mois["net_result"] - attendu) < 1, f"résultat incohérent en {mois['period']}"


# ==========================================================================
# 4. API REST, le contrat des fronts web
# ==========================================================================
def test_api_repond_sur_toutes_les_routes(tmp: Path) -> None:
    """L'API sert les mêmes chiffres que les requêtes internes."""
    try:
        from fastapi.testclient import TestClient
        TestClient                      # le client exige aussi httpx
    except Exception as manque:         # noqa: BLE001
        print(f"    (ignoré : {manque})")
        return

    os.environ["ERP_DB_PATH"] = str(tmp / "api.db")
    import erp.database as database
    database._SINGLETON = None                      # base dédiée au test
    database.DB_PATH = Path(os.environ["ERP_DB_PATH"])

    import importlib
    from api import main as api_main
    importlib.reload(api_main)
    client = TestClient(api_main.app)

    sante = client.get("/api/health").json()
    assert sante["configured"] is False, "la base de test doit démarrer vide"
    assert client.get("/api/overview").status_code == 409, \
        "sans boutique, l'API doit répondre 409"

    catalogue = client.get("/api/store-types").json()
    assert len(catalogue["types"]) == len(STORE_TYPES)
    assert len(catalogue["departments"]) == 7

    creation = client.post("/api/company", json={
        "name": "Boutique API", "store_type": "generique",
        "history_months": 3, "traffic_scale": 0.4})
    assert creation.status_code == 201, creation.text
    assert creation.json()["summary"]["sales"] > 0

    for route in ("/api/overview", "/api/kpis", "/api/departments", "/api/activity",
                  "/api/sales", "/api/stock", "/api/purchasing", "/api/customers",
                  "/api/hr", "/api/finance", "/api/products", "/api/theme", "/api/audit"):
        reponse = client.get(route)
        assert reponse.status_code == 200, f"{route} → {reponse.status_code}"

    produit = client.get("/api/products").json()[0]
    stock_initial = produit["stock"]

    vente = client.post("/api/sales", json={
        "items": [{"product_id": produit["id"], "quantity": 2}]})
    assert vente.status_code == 201
    apres = [p for p in client.get("/api/products").json() if p["id"] == produit["id"]][0]
    assert apres["stock"] == stock_initial - 2, "l'API doit décharger le stock"

    commande = client.post("/api/purchases", json={
        "supplier_id": 1, "lines": [{"product_id": produit["id"], "quantity": 10}]}).json()
    client.post(f"/api/purchases/{commande['id']}/receive")
    final = [p for p in client.get("/api/products").json() if p["id"] == produit["id"]][0]
    assert final["stock"] == stock_initial - 2 + 10

    assert client.post("/api/sales", json={"items": []}).status_code == 422
    assert client.get("/api/sales/999999").status_code == 404

    database._SINGLETON = None
    os.environ.pop("ERP_DB_PATH", None)


# ==========================================================================
# 5. Ressources partagées, le contrat entre les interfaces
# ==========================================================================
def test_catalogue_des_metiers_complet(tmp: Path) -> None:
    """Chaque métier doit fournir tout ce dont le générateur a besoin."""
    for cle, spec in STORE_TYPES.items():
        for champ in ("label", "icon", "tagline", "tax_rate", "margin_target",
                      "daily_tickets", "basket_lines", "seasonality", "roles",
                      "suppliers", "expense_lines", "categories"):
            assert champ in spec, f"{cle} : champ « {champ} » manquant"
        assert len(spec["seasonality"]) == 12, f"{cle} : 12 coefficients attendus"
        assert len(spec["basket_lines"]) == 2 and spec["basket_lines"][0] >= 1
        assert 0 <= spec["tax_rate"] <= 0.3
        assert spec["categories"], f"{cle} : aucun rayon"
        for rayon in spec["categories"]:
            assert rayon["products"], f"{cle}/{rayon['name']} : aucun produit"
            for produit in rayon["products"]:
                assert produit["price"] > produit["cost"] > 0, \
                    f"{cle} : {produit['name']} vendu à perte"


def test_theme_partage_coherent(tmp: Path) -> None:
    """La palette est le contrat visuel commun aux quatre interfaces."""
    from erp.theme import SERIES, STATUS, SURFACE

    assert len(SERIES) == 4, "quatre couleurs de série suffisent"
    assert len(set(SERIES)) == 4, "aucune couleur de série en double"
    for couleur in SERIES:
        assert couleur.startswith("#") and len(couleur) == 7
    assert set(STATUS) == {"good", "warning", "serious", "critical"}
    assert not set(STATUS.values()) & set(SERIES), \
        "une couleur de statut ne doit jamais servir de couleur de série"
    for jeton in ("chart", "page", "ink_primary", "grid", "axis", "border"):
        assert jeton in SURFACE


def _hex_vers_teinte(couleur: str) -> float:
    """Teinte en degrés (0-360) d'une couleur hexadécimale."""
    import colorsys

    r, v, b = (int(couleur[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, v, b)[0] * 360


def test_aucune_teinte_bleue(tmp: Path) -> None:
    """Contrainte de charte : le bleu est proscrit dans toute la palette."""
    from erp.theme import DEPT_COLOR, SEQUENTIAL, SERIES, STATUS

    a_verifier = list(SERIES) + list(STATUS.values()) + list(DEPT_COLOR.values()) + SEQUENTIAL
    for couleur in a_verifier:
        teinte = _hex_vers_teinte(couleur)
        assert not (185 <= teinte <= 260), f"{couleur} est bleu (teinte {teinte:.0f} degrés)"


def test_aucune_transparence_dans_les_styles(tmp: Path) -> None:
    """Toutes les couleurs doivent être opaques, dans les quatre interfaces."""
    feuilles = [
        ROOT / "web" / "css" / "styles.css",
        ROOT / "python" / "dash_app" / "assets" / "erp.css",
        ROOT / "shiny" / "www" / "styles.css",
        ROOT / "angular" / "src" / "styles.css",
    ]
    for feuille in feuilles:
        contenu = feuille.read_text(encoding="utf-8")
        for interdit in ("rgba(", "hsla(", "opacity:", "box-shadow"):
            assert interdit not in contenu, f"{feuille.name} contient « {interdit} »"


def test_aucune_emoticone_dans_l_interface(tmp: Path) -> None:
    """L'interface n'utilise ni émoticône ni pictogramme décoratif."""
    import re

    emoticones = re.compile(
        "[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]")
    dossiers = [
        (ROOT / "web", ("*.js", "*.html", "*.css")),
        (ROOT / "python" / "dash_app", ("*.py", "*.css")),
        (ROOT / "python" / "erp", ("*.py",)),
        (ROOT / "shiny", ("*.R", "*.css")),
        (ROOT / "angular" / "src", ("*.ts", "*.html", "*.css")),
        (ROOT / "shared", ("*.json", "*.sql")),
        (ROOT / "python", ("cli.py",)),
    ]
    fautifs = []
    for dossier, motifs in dossiers:
        for motif in motifs:
            for fichier in dossier.rglob(motif):
                if "node_modules" in str(fichier) or "dist" in str(fichier):
                    continue
                for numero, ligne in enumerate(
                        fichier.read_text(encoding="utf-8").splitlines(), start=1):
                    if emoticones.search(ligne):
                        fautifs.append(f"{fichier.name}:{numero}")
    assert not fautifs, "émoticônes trouvées : " + ", ".join(fautifs[:8])


def test_typographie_serif_partout(tmp: Path) -> None:
    """La charte impose Times New Roman aux quatre interfaces."""
    from erp.theme import FONT

    assert "Times New Roman" in FONT
    for feuille in (ROOT / "web" / "css" / "styles.css",
                    ROOT / "angular" / "src" / "styles.css",
                    ROOT / "shiny" / "www" / "styles.css",
                    ROOT / "python" / "dash_app" / "assets" / "erp.css"):
        assert "Times New Roman" in feuille.read_text(encoding="utf-8"), feuille.name


# ==========================================================================
# Exécution
# ==========================================================================
def main() -> int:
    tests = [(nom, objet) for nom, objet in sorted(globals().items())
             if nom.startswith("test_") and callable(objet)]
    echecs = []
    print(f"\n  Pipeline ERP, {len(tests)} tests\n  " + "─" * 62)

    with tempfile.TemporaryDirectory() as dossier:
        tmp = Path(dossier)
        for nom, fonction in tests:
            libelle = nom[5:].replace("_", " ")
            try:
                fonction(tmp)
                print(f"  ✓ {libelle}")
            except AssertionError as erreur:
                echecs.append((nom, str(erreur)))
                print(f"  ✗ {libelle}\n      {erreur}")
            except Exception as erreur:                     # noqa: BLE001
                echecs.append((nom, f"{type(erreur).__name__}: {erreur}"))
                print(f"  ✗ {libelle}\n      {type(erreur).__name__}: {erreur}")

    print("  " + "─" * 62)
    if echecs:
        print(f"  {len(echecs)} échec(s) sur {len(tests)}\n")
        return 1
    print(f"  {len(tests)} tests passés\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
