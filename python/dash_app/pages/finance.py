"""Département Finance — compte de résultat, charges, passage CA -> résultat."""

from __future__ import annotations

from dash import dcc, html

from erp import queries as q
from erp.config import compact_money
from erp.theme import DEPT_COLOR, STATUS

from .. import charts
from ..components import (card, data_table, delta_badge, empty_state, kpi_tile,
                          num_col, page_header)


def layout(db, days: int = 30) -> html.Div:
    sym = db.company()["currency_sym"]
    monthly = q.financial_monthly(db=db)
    by_cat = q.expenses_by_category(365, db=db)
    by_dept = q.expenses_by_department(365, db=db)
    entries = q.expenses_list(150, db=db)
    bridge = q.profit_bridge(db=db)

    closed = [m for m in monthly[:-1]] or monthly       # le mois en cours est partiel
    last = closed[-1] if closed else {}
    prev = closed[-2] if len(closed) > 1 else {}
    revenue = last.get("revenue", 0) or 0
    net = last.get("net_result", 0) or 0
    margin = revenue - (last.get("cogs", 0) or 0)
    delta = ((net - (prev.get("net_result") or 0)) / abs(prev["net_result"]) * 100
             if prev.get("net_result") else None)

    return html.Div([
        page_header("💰  Finance",
                    "Le compte de résultat n'est pas ressaisi : ventes, coût des marchandises, "
                    "charges et paie remontent automatiquement des autres départements."),

        html.Div([
            kpi_tile(f"Chiffre d'affaires — {last.get('period', '—')}",
                     compact_money(revenue, sym), ["dernier mois clos"], DEPT_COLOR["SALES"]),
            kpi_tile("Marge brute", compact_money(margin, sym),
                     [f"taux {margin / revenue * 100:.1f} %" if revenue else "—"],
                     DEPT_COLOR["FIN"]),
            kpi_tile("Charges + paie",
                     compact_money((last.get("expenses", 0) or 0) + (last.get("payroll", 0) or 0), sym),
                     ["structure et salaires"], DEPT_COLOR["HR"]),
            kpi_tile("Résultat net", compact_money(net, sym),
                     [delta_badge(delta),
                      html.Span("bénéfice" if net >= 0 else "perte",
                                style={"color": STATUS["good"] if net >= 0 else STATUS["critical"],
                                       "fontWeight": "600"})],
                     STATUS["good"] if net >= 0 else STATUS["critical"]),
        ], className="grid grid-4", style={"marginBottom": "16px"}),

        html.Div([
            card("Du chiffre d'affaires au résultat",
                 dcc.Graph(figure=charts.waterfall(
                     ["Chiffre d'affaires", "Coût des marchandises", "Charges",
                      "Masse salariale", "Résultat net"],
                     [bridge["revenue"], bridge["cogs"], bridge["expenses"],
                      bridge["payroll"], bridge["net_result"]], sym, height=320),
                     config={"displayModeBar": False}),
                 note="Mois en cours. Bleu : ce qui entre. Rouge : ce qui sort.",
                 className="span-2"),
            card("Charges par nature",
                 dcc.Graph(figure=charts.share_bars(
                     [c["category"] for c in by_cat], [c["amount"] for c in by_cat], sym,
                     height=max(200, 46 * len(by_cat) + 60)),
                     config={"displayModeBar": False}) if by_cat
                 else empty_state("Aucune charge enregistrée."),
                 note="Sur douze mois glissants."),
        ], className="grid grid-3"),

        html.Div([
            card("Chiffre d'affaires, coût des marchandises et charges par mois",
                 dcc.Graph(figure=charts.grouped_bars(
                     [charts.fr_period(m["period"]) for m in monthly],
                     {"Chiffre d'affaires": [m["revenue"] for m in monthly],
                      "Coût des marchandises": [m["cogs"] for m in monthly],
                      "Charges + paie": [(m["expenses"] or 0) + (m["payroll"] or 0)
                                         for m in monthly]},
                     sym, height=310), config={"displayModeBar": False}) if monthly
                 else empty_state("Pas encore d'historique."),
                 note="Trois mesures dans la même unité, donc un seul axe de valeurs.",
                 className="span-2"),
            card("Charges par département",
                 dcc.Graph(figure=charts.share_bars(
                     [d["department"] for d in by_dept], [d["amount"] for d in by_dept], sym,
                     height=max(190, 46 * len(by_dept) + 60)),
                     config={"displayModeBar": False}) if by_dept
                 else empty_state("Aucune charge."),
                 note="Qui consomme le budget."),
        ], className="grid grid-3", style={"marginTop": "14px"}),

        html.Div([
            card("Compte de résultat mensuel",
                 data_table(
                     monthly,
                     [{"name": "Période", "id": "period"},
                      num_col(f"CA ({sym})", "revenue", 0),
                      num_col(f"Coût march. ({sym})", "cogs", 0),
                      num_col(f"Charges ({sym})", "expenses", 0),
                      num_col(f"Paie ({sym})", "payroll", 0),
                      num_col(f"Résultat ({sym})", "net_result", 0)],
                     "tbl-pl", page_size=13,
                     style_data_conditional=[
                         {"if": {"filter_query": "{net_result} < 0", "column_id": "net_result"},
                          "color": "#8f2222", "fontWeight": "600"},
                     ]),
                 note="Vue SQL v_financial_monthly. Le dernier mois est partiel."),
            card("Journal des charges",
                 data_table(
                     entries,
                     [{"name": "Date", "id": "spent_on"},
                      {"name": "Libellé", "id": "label"},
                      {"name": "Nature", "id": "category"},
                      {"name": "Département", "id": "department"},
                      num_col(f"Montant ({sym})", "amount", 0)],
                     "tbl-expenses", page_size=13, filter_action="native"),
                 note="150 dernières écritures."),
        ], className="grid grid-2", style={"marginTop": "14px"}),
    ])
