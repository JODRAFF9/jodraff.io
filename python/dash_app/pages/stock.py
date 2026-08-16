"""Département Stock, niveaux, valorisation, rotation, alertes et mouvements."""

from __future__ import annotations

from dash import dcc, html

from erp import queries as q
from erp.config import compact_money
from erp.theme import DEPT_COLOR, STATUS

from .. import charts
from ..components import (card, data_table, empty_state, kpi_tile, num_col,
                          page_header)


def layout(db, days: int = 30) -> html.Div:
    sym = db.company()["currency_sym"]
    valuation = q.stock_valuation(db=db)
    alerts = q.stock_alerts(db=db)
    rotation = q.stock_rotation(90, db=db)
    moves = q.stock_moves(150, days, db=db)
    items = q.products(db=db)

    total_value = sum(r["value"] or 0 for r in valuation)
    retail_value = sum(r["retail_value"] or 0 for r in valuation)
    out = [p for p in items if p["stock_status"] == "rupture"]
    losses = db.scalar(
        """SELECT COALESCE(SUM(ABS(m.quantity) * p.cost_price), 0)
             FROM stock_moves m JOIN products p ON p.id = m.product_id
            WHERE m.move_type = 'perte' AND m.move_date >= date('now', ?)""",
        (f"-{days} day",))

    return html.Div([
        page_header("📦  Stock",
                    "Le stock n'est jamais saisi à la main : il résulte des ventes, "
                    "des réceptions fournisseurs et des écritures d'inventaire."),

        html.Div([
            kpi_tile("Valeur du stock", compact_money(total_value, sym),
                     [f"au prix de revient · {len(items)} références"], DEPT_COLOR["STOCK"]),
            kpi_tile("Valeur au prix de vente", compact_money(retail_value, sym),
                     [f"marge potentielle {compact_money(retail_value - total_value, sym)}"],
                     DEPT_COLOR["FIN"]),
            kpi_tile("Ruptures", str(len(out)),
                     [html.Span("⛔ vente impossible",
                                style={"color": STATUS["critical"], "fontWeight": "600"})],
                     STATUS["critical"]),
            kpi_tile("À commander", str(len(alerts)),
                     [html.Span("▲ sous le point de commande")], STATUS["serious"]),
            kpi_tile("Pertes valorisées", compact_money(losses, sym),
                     [f"casse et péremption sur {days} j"], DEPT_COLOR["PURCH"]),
        ], className="grid grid-kpi", style={"marginBottom": "16px"}),

        html.Div([
            card("Valorisation par rayon",
                 dcc.Graph(figure=charts.dumbbell(
                     [r["category"] for r in valuation],
                     [r["value"] for r in valuation],
                     [r["retail_value"] for r in valuation],
                     "Prix de revient", "Prix de vente", sym,
                     height=max(220, 48 * len(valuation) + 70)),
                     config={"displayModeBar": False}),
                 note="L'écart entre les deux points est la marge immobilisée dans le rayon.",
                 className="span-2"),
            card("Répartition de la valeur",
                 dcc.Graph(figure=charts.share_bars(
                     [r["category"] for r in valuation],
                     [r["value"] for r in valuation], sym,
                     height=max(200, 46 * len(valuation) + 60)),
                     config={"displayModeBar": False}) if valuation
                 else empty_state("Catalogue vide.")),
        ], className="grid grid-3"),

        html.Div([
            card("Alertes de réapprovisionnement",
                 data_table(
                     alerts,
                     [{"name": "Produit", "id": "product"},
                      {"name": "Rayon", "id": "category"},
                      {"name": "Fournisseur", "id": "supplier"},
                      {"name": "État", "id": "severity"},
                      num_col("Stock", "stock", 1),
                      num_col("Seuil", "reorder_point", 1),
                      num_col("À commander", "suggested_qty", 0),
                      num_col(f"Coût ({sym})", "suggested_cost", 0)],
                     "tbl-alerts", page_size=10,
                     style_data_conditional=[
                         {"if": {"filter_query": "{severity} = 'rupture'"},
                          "backgroundColor": "#fbeded", "color": "#8f2222",
                          "fontWeight": "600"},
                         {"if": {"filter_query": "{severity} = 'alerte'"},
                          "backgroundColor": "#fdefe8", "color": "#8a3d17"},
                     ]) if alerts else empty_state("Aucune alerte : tous les stocks sont au-dessus du seuil."),
                 note="Calculée par la vue SQL v_stock_alerts, reprise telle quelle "
                      "par le département Achats.",
                 className="span-2"),
            card("Ce que dit la couleur",
                 html.Div([
                     _legend_row(STATUS["critical"], "⛔", "Rupture", "stock à zéro ou négatif"),
                     _legend_row(STATUS["serious"], "▲", "À commander", "sous le point de commande"),
                     _legend_row(STATUS["warning"], "•", "Stock faible", "moins de deux fois le seuil"),
                     _legend_row(STATUS["good"], "✓", "Disponible", "niveau confortable"),
                 ]),
                 note="Une icône et un libellé accompagnent toujours la couleur."),
        ], className="grid grid-3", style={"marginTop": "14px"}),

        html.Div([
            card("Rotation, combien de jours de stock reste-t-il ?",
                 data_table(
                     [r for r in rotation if r["days_of_stock"] is not None][:60],
                     [{"name": "Produit", "id": "product"},
                      {"name": "Rayon", "id": "category"},
                      num_col("Stock", "stock", 1),
                      num_col("Ventes / jour", "daily_sales", 2),
                      num_col("Jours de stock", "days_of_stock", 1),
                      num_col(f"Valeur ({sym})", "value", 0)],
                     "tbl-rotation", page_size=10,
                     style_data_conditional=[
                         {"if": {"filter_query": "{days_of_stock} < 7"},
                          "backgroundColor": "#fdefe8"},
                         {"if": {"filter_query": "{days_of_stock} > 120"},
                          "color": "#7a5307"},
                     ]),
                 note="Rythme observé sur 90 jours. Sous 7 jours : commande urgente. "
                      "Au-delà de 120 jours : capital immobilisé."),
            card("Mouvements de stock",
                 data_table(
                     moves,
                     [{"name": "Date", "id": "moved_at"},
                      {"name": "Produit", "id": "product"},
                      {"name": "Type", "id": "move_type"},
                      {"name": "Origine", "id": "source_dept"},
                      num_col("Quantité", "quantity", 1),
                      {"name": "Référence", "id": "ref"}],
                     "tbl-moves", page_size=10, filter_action="native"),
                 note="Chaque ligne indique le département qui l'a générée."),
        ], className="grid grid-2", style={"marginTop": "14px"}),

        html.Div([
            card("Catalogue complet",
                 data_table(
                     items,
                     [{"name": "SKU", "id": "sku"},
                      {"name": "Produit", "id": "name"},
                      {"name": "Rayon", "id": "category"},
                      {"name": "Fournisseur", "id": "supplier"},
                      {"name": "Unité", "id": "unit"},
                      num_col(f"Achat ({sym})", "cost_price", 0),
                      num_col(f"Vente ({sym})", "sale_price", 0),
                      num_col("Marge %", "margin_rate", 3),
                      num_col("Stock", "stock", 1),
                      {"name": "État", "id": "stock_status"},
                      num_col(f"Valeur ({sym})", "stock_value", 0)],
                     "tbl-products", page_size=15, filter_action="native",
                     style_data_conditional=[
                         {"if": {"filter_query": "{stock_status} = 'rupture'"},
                          "backgroundColor": "#fbeded", "color": "#8f2222"},
                         {"if": {"filter_query": "{stock_status} = 'alerte'"},
                          "backgroundColor": "#fdefe8"},
                     ]),
                 note="Vue SQL v_products : prix, marge unitaire, niveau et état de stock."),
        ], style={"marginTop": "14px"}),
    ])


def _legend_row(color: str, icon: str, label: str, detail: str) -> html.Div:
    return html.Div([
        html.Span(className="badge-dot", style={"background": color, "flex": "0 0 7px"}),
        html.B(f"{icon} {label}", style={"fontSize": "12.5px"}),
        html.Span(detail, style={"fontSize": "12px", "color": "#898781"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "8px 0",
              "borderBottom": "1px solid #e1e0d9"})
