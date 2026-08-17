"""Département Ventes, encaissements, panier, canaux, performance vendeurs."""

from __future__ import annotations

from dash import dcc, html

from erp import queries as q
from erp.config import compact_money
from erp.theme import DEPT_COLOR

from .. import charts
from ..components import (card, data_table, delta_badge, empty_state, kpi_tile,
                          num_col, page_header)

WEEKDAYS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]


def layout(db, days: int = 30) -> html.Div:
    sym = db.company()["currency_sym"]
    k = q.kpis(days, db=db)
    daily = q.sales_daily(days, db=db)
    pay = q.sales_by_dimension("payment", days, db=db)
    channel = q.sales_by_dimension("channel", days, db=db)
    tops = q.top_products(10, days, db=db)
    sellers = [e for e in q.employees(db=db) if e["tickets"] > 0][:10]
    recent = q.sales_list(120, db=db)

    return html.Div([
        page_header("Ventes",
                    "Chaque ticket enregistré décharge le stock, alimente la fiche client "
                    "et le compte de résultat, sans aucune ressaisie."),

        html.Div([
            kpi_tile("Chiffre d'affaires", compact_money(k["revenue"], sym),
                     [delta_badge(k["revenue_delta"]), f"sur {days} j"], DEPT_COLOR["SALES"]),
            kpi_tile("Tickets", f"{k['tickets']:,}".replace(",", " "),
                     [delta_badge(k["tickets_delta"])], DEPT_COLOR["SALES"]),
            kpi_tile("Panier moyen", compact_money(k["avg_basket"], sym),
                     [delta_badge(k["avg_basket_delta"])], DEPT_COLOR["SALES"]),
            kpi_tile("Marge brute", compact_money(k["margin"], sym),
                     [f"taux {k['margin_rate'] * 100:.1f} %"], DEPT_COLOR["FIN"]),
        ], className="grid grid-4", style={"marginBottom": "16px"}),

        html.Div([
            card("Chiffre d'affaires et nombre de tickets",
                 [dcc.Graph(figure=charts.line_chart(
                     [charts.fr_day(r["sale_date"]) for r in daily],
                     {"CA TTC": [r["revenue"] for r in daily]}, sym, height=230, fill=True),
                     config={"displayModeBar": False}),
                  dcc.Graph(figure=charts.line_chart(
                      [charts.fr_day(r["sale_date"]) for r in daily],
                      {"Tickets": [r["tickets"] for r in daily]}, None, height=150),
                      config={"displayModeBar": False})],
                 note="Deux unités différentes : deux graphiques superposés, "
                      "jamais un second axe Y.",
                 className="span-2"),
            card("Modes de paiement",
                 dcc.Graph(figure=charts.share_bars(
                     [r["label"] for r in pay], [r["revenue"] for r in pay], sym,
                     height=max(200, 44 * len(pay) + 60)),
                     config={"displayModeBar": False}) if pay
                 else empty_state("Aucune vente sur la période.")),
        ], className="grid grid-3"),

        html.Div([
            card("Affluence par jour et par heure",
                 dcc.Graph(figure=_affluence(db, days),
                           config={"displayModeBar": False}),
                 note="Nombre de tickets. Utile pour caler les plannings d'équipe.",
                 className="span-2"),
            card("Canaux de vente",
                 dcc.Graph(figure=charts.share_bars(
                     [r["label"] for r in channel], [r["revenue"] for r in channel], sym,
                     height=max(190, 44 * len(channel) + 60)),
                     config={"displayModeBar": False}) if channel
                 else empty_state("Aucune donnée.")),
        ], className="grid grid-3", style={"marginTop": "14px"}),

        html.Div([
            card("Top 10 des produits",
                 data_table(
                     tops,
                     [{"name": "Produit", "id": "product"},
                      {"name": "Rayon", "id": "category"},
                      num_col("Quantité", "qty_sold", 0),
                      num_col(f"CA HT ({sym})", "revenue_ht", 0),
                      num_col(f"Marge ({sym})", "margin", 0)],
                     "tbl-top-products", page_size=10),
                 note="Classement par chiffre d'affaires hors taxes."),
            card("Performance des vendeurs",
                 data_table(
                     sellers,
                     [{"name": "Vendeur", "id": "employee"},
                      {"name": "Poste", "id": "role"},
                      num_col("Tickets", "tickets", 0),
                      num_col(f"CA ({sym})", "revenue", 0),
                      num_col(f"Panier ({sym})", "avg_basket", 0)],
                     "tbl-sellers", page_size=10),
                 note="Croisement du département Ventes et du département RH."),
        ], className="grid grid-2", style={"marginTop": "14px"}),

        html.Div([
            card("Journal des ventes",
                 data_table(
                     recent,
                     [{"name": "Référence", "id": "ref"},
                      {"name": "Date", "id": "sold_at"},
                      {"name": "Client", "id": "customer"},
                      {"name": "Vendeur", "id": "seller"},
                      {"name": "Paiement", "id": "payment_method"},
                      {"name": "Canal", "id": "channel"},
                      {"name": "Statut", "id": "status"},
                      num_col("Lignes", "lines", 0),
                      num_col(f"Total ({sym})", "total", 0)],
                     "tbl-sales", page_size=12, filter_action="native",
                     style_data_conditional=[{
                         "if": {"filter_query": "{status} = 'annulée'"},
                         "color": "#8f2222", "fontStyle": "italic",
                     }]),
                 note="120 derniers tickets. Colonnes triables et filtrables."),
        ], style={"marginTop": "14px"}),
    ])


def _affluence(db, days: int):
    """Carte de chaleur jour × heure, magnitude, donc rampe mono-teinte."""
    rows = db.query(
        """SELECT CAST(strftime('%w', sale_date) AS INTEGER) AS wd,
                  CAST(substr(sold_at, 12, 2) AS INTEGER)    AS hour,
                  COUNT(*) AS tickets
             FROM sales WHERE status = 'payée' AND sale_date >= date('now', ?)
            GROUP BY wd, hour""", (f"-{days} day",))
    hours = sorted({r["hour"] for r in rows}) or list(range(8, 21))
    order = [1, 2, 3, 4, 5, 6, 0]                       # lundi -> dimanche
    index = {(r["wd"], r["hour"]): r["tickets"] for r in rows}
    z = [[index.get((wd, h), 0) for h in hours] for wd in order]
    return charts.heatmap(z, [f"{h:02d} h" for h in hours],
                          [WEEKDAYS[wd] for wd in order], height=300, unit=" tickets")
