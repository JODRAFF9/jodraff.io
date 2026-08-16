"""Vue d'ensemble — la consolidation de tous les départements.

C'est la page qui matérialise le principe « données centrées » : chaque carte
provient d'un département différent, mais toutes lisent les mêmes tables.
"""

from __future__ import annotations

from dash import dcc, html

from erp import queries as q
from erp.config import DEPARTMENTS, compact_money
from erp.theme import DEPT_COLOR

from .. import charts
from ..components import (activity_feed, card, delta_badge, dept_chip, empty_state,
                          kpi_tile, page_header)


def layout(db, days: int = 30) -> html.Div:
    company = db.company()
    sym = company["currency_sym"]
    k = q.kpis(days, db=db)
    depts = q.department_summary(db=db)
    daily = q.sales_daily(days if days > 7 else 30, db=db)
    by_cat = q.sales_by_category(days, db=db)
    monthly = q.sales_monthly(db=db)

    return html.Div([
        page_header(
            f"{company['logo_emoji']}  {company['name']}",
            f"{company['store_label']} — {company['city']}, {company['country']}. "
            f"Toutes les cartes ci-dessous sont calculées en direct sur la base SQL centrale.",
        ),

        # --- rangée d'indicateurs clés --------------------------------
        html.Div([
            kpi_tile("Chiffre d'affaires", compact_money(k["revenue"], sym),
                     [delta_badge(k["revenue_delta"]), f"sur {days} j"], DEPT_COLOR["SALES"]),
            kpi_tile("Marge brute", compact_money(k["margin"], sym),
                     [delta_badge(k["margin_delta"]),
                      f"taux {k['margin_rate'] * 100:.1f} %"], DEPT_COLOR["FIN"]),
            kpi_tile("Tickets", f"{k['tickets']:,}".replace(",", " "),
                     [delta_badge(k["tickets_delta"]),
                      f"{k['customers']} clients identifiés"], DEPT_COLOR["CRM"]),
            kpi_tile("Panier moyen", compact_money(k["avg_basket"], sym),
                     [delta_badge(k["avg_basket_delta"]), "par ticket"], DEPT_COLOR["SALES"]),
            kpi_tile("Valeur du stock", compact_money(k["stock_value"], sym),
                     [html.Span(f"⛔ {k['out_of_stock']} rupture(s)"),
                      html.Span(f"· ▲ {k['stock_alerts']} à commander")], DEPT_COLOR["STOCK"]),
            kpi_tile("Résultat du mois", compact_money(k["net_result"], sym),
                     [f"masse salariale {compact_money(k['payroll'], sym)}"], DEPT_COLOR["HR"]),
        ], className="grid grid-kpi", style={"marginBottom": "16px"}),

        # --- bandeau départements -------------------------------------
        card(
            "Départements connectés à la base centrale",
            [
                html.Div([
                    dept_chip(d["dept"], d["name"],
                              f"{d['count']} {d['count_label']}")
                    for d in depts
                ], className="dept-strip"),
                html.Div([
                    html.Div([
                        html.Div(d["metric"], style={"fontSize": "11.5px", "color": "#898781"}),
                        html.Div(
                            compact_money(d["value"], sym) if d["dept"] != "CRM"
                            else f"{int(d['value'])}",
                            style={"fontSize": "17px", "fontWeight": "640",
                                   "letterSpacing": "-.02em", "marginTop": "3px"}),
                    ], className="summary-item",
                        style={"borderLeft": f"3px solid {DEPT_COLOR.get(d['dept'], '#898781')}"})
                    for d in depts
                ], className="summary-grid", style={"marginTop": "12px"}),
            ],
            note="Une écriture faite dans un département met immédiatement à jour "
                 "les indicateurs des autres — c'est le rôle des triggers SQL.",
        ),

        # --- graphiques ------------------------------------------------
        html.Div([
            card("Chiffre d'affaires quotidien",
                 dcc.Graph(figure=charts.line_chart(
                     [charts.fr_day(r["sale_date"]) for r in daily],
                     {"CA TTC": [r["revenue"] for r in daily]},
                     sym, height=280, fill=True),
                     config={"displayModeBar": False}),
                 note="Source : département Ventes. Survolez la courbe pour le détail.",
                 className="span-2"),
            card("Répartition par rayon",
                 dcc.Graph(figure=charts.share_bars(
                     [r["category"] for r in by_cat],
                     [r["revenue"] for r in by_cat], sym,
                     height=max(200, 46 * len(by_cat) + 60)),
                     config={"displayModeBar": False}) if by_cat
                 else empty_state("Aucune vente sur la période."),
                 note=f"Chiffre d'affaires HT des {days} derniers jours."),
        ], className="grid grid-3", style={"marginTop": "14px"}),

        html.Div([
            card("Chiffre d'affaires et marge par mois",
                 dcc.Graph(figure=charts.grouped_bars(
                     [charts.fr_period(r["period"]) for r in monthly],
                     {"CA HT": [r["revenue_ht"] for r in monthly],
                      "Marge brute": [r["gross_margin"] for r in monthly]},
                     sym, height=300),
                     config={"displayModeBar": False}),
                 note="Deux mesures de même unité, donc un seul axe de valeurs.",
                 className="span-2"),
            card("Dernières écritures",
                 activity_feed(q.recent_activity(11, db=db), sym),
                 note="Ventes, achats, mouvements de stock et charges, tous départements."),
        ], className="grid grid-3", style={"marginTop": "14px"}),
    ])
