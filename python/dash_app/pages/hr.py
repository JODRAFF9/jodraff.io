"""Département Ressources humaines, effectif, masse salariale, paie, performance."""

from __future__ import annotations

from dash import dcc, html

from erp import queries as q
from erp.config import compact_money
from erp.theme import DEPT_COLOR

from .. import charts
from ..components import (card, data_table, empty_state, kpi_tile, num_col,
                          page_header)


def layout(db, days: int = 30) -> html.Div:
    sym = db.company()["currency_sym"]
    staff = q.employees(db=db)
    by_dept = q.headcount_by_department(db=db)
    payroll = q.payroll_history(db=db)

    headcount = len(staff)
    monthly_payroll = sum(d["payroll"] or 0 for d in by_dept)
    revenue_month = db.scalar(
        "SELECT COALESCE(revenue, 0) FROM v_financial_monthly"
        " WHERE period = strftime('%Y-%m', 'now')")
    ratio = (monthly_payroll / revenue_month * 100) if revenue_month else 0
    sellers = [e for e in staff if e["tickets"] > 0]

    return html.Div([
        page_header("Ressources humaines",
                    "L'équipe est reliée aux ventes : le même identifiant salarié sert à la "
                    "paie et au calcul de la performance commerciale."),

        html.Div([
            kpi_tile("Effectif", str(headcount),
                     [f"{len(by_dept)} services"], DEPT_COLOR["HR"]),
            kpi_tile("Masse salariale", compact_money(monthly_payroll, sym),
                     ["par mois, salaires bruts"], DEPT_COLOR["FIN"]),
            kpi_tile("Poids sur le CA", f"{ratio:.1f} %",
                     ["masse salariale / chiffre d'affaires du mois"], DEPT_COLOR["SALES"]),
            kpi_tile("CA par vendeur", compact_money(
                sum(e["revenue"] or 0 for e in sellers) / max(1, len(sellers)), sym),
                     [f"{len(sellers)} salariés encaissent"], DEPT_COLOR["CRM"]),
        ], className="grid grid-4", style={"marginBottom": "16px"}),

        html.Div([
            card("Masse salariale versée par mois",
                 dcc.Graph(figure=charts.grouped_bars(
                     [charts.fr_period(p["period"]) for p in payroll],
                     {"Salaires nets": [p["net"] for p in payroll],
                      "Primes": [p["bonus"] for p in payroll]},
                     sym, height=290, stacked=True),
                     config={"displayModeBar": False}) if payroll
                 else empty_state("Aucun bulletin de paie."),
                 note="Segments empilés séparés par 2 px : les parts restent lisibles.",
                 className="span-2"),
            card("Effectif par service",
                 dcc.Graph(figure=charts.bar_chart(
                     [d["department"] for d in by_dept],
                     [d["headcount"] for d in by_dept], None,
                     horizontal=True, height=max(200, 44 * len(by_dept) + 60),
                     color=DEPT_COLOR["HR"]), config={"displayModeBar": False}) if by_dept
                 else empty_state("Aucun salarié.")),
        ], className="grid grid-3"),

        html.Div([
            card("Coût par service",
                 data_table(
                     by_dept,
                     [{"name": "Service", "id": "department"},
                      num_col("Effectif", "headcount", 0),
                      num_col(f"Masse salariale ({sym})", "payroll", 0),
                      num_col(f"Salaire moyen ({sym})", "avg_salary", 0)],
                     "tbl-dept", page_size=8),
                 note="La vue table du graphique ci-dessus."),
            card("Performance commerciale de l'équipe",
                 data_table(
                     staff,
                     [{"name": "Salarié", "id": "employee"},
                      {"name": "Poste", "id": "role"},
                      {"name": "Service", "id": "department"},
                      num_col(f"Salaire ({sym})", "salary", 0),
                      num_col("Tickets", "tickets", 0),
                      num_col(f"CA généré ({sym})", "revenue", 0),
                      num_col(f"Panier moyen ({sym})", "avg_basket", 0)],
                     "tbl-staff", page_size=10, filter_action="native"),
                 note="Vue SQL v_employee_performance : jointure RH × Ventes. "
                      "Un poste sans encaissement affiche logiquement zéro ticket.",
                 className="span-2"),
        ], className="grid grid-3", style={"marginTop": "14px"}),
    ])
