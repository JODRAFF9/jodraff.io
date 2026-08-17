"""Département Achats, fournisseurs, commandes, plan de réapprovisionnement."""

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
    sups = q.suppliers(db=db)
    orders = q.purchases(80, db=db)
    monthly = q.purchases_monthly(db=db)
    plan = q.reorder_plan(db=db)

    spend = db.scalar(
        "SELECT COALESCE(SUM(total), 0) FROM purchases"
        " WHERE status <> 'annulée' AND ordered_on >= date('now', ?)", (f"-{days} day",))
    pending = [o for o in orders if o["status"] == "commandée"]
    plan_amount = sum(p["amount"] or 0 for p in plan)

    return html.Div([
        page_header("Achats",
                    "Le plan de commande n'est pas saisi : il est déduit des niveaux de "
                    "stock et des ventes, puis groupé par fournisseur."),

        html.Div([
            kpi_tile("Achats de la période", compact_money(spend, sym),
                     [f"sur {days} jours"], DEPT_COLOR["PURCH"]),
            kpi_tile("Fournisseurs actifs", str(len([s for s in sups if s["active"]])),
                     [f"délai moyen {_avg(sups, 'lead_time_days'):.0f} jours"],
                     DEPT_COLOR["PURCH"]),
            kpi_tile("Commandes en cours", str(len(pending)),
                     ["en attente de réception"], DEPT_COLOR["STOCK"]),
            kpi_tile("Réappro. suggéré", compact_money(plan_amount, sym),
                     [f"{sum(p['refs'] for p in plan)} références sous le seuil"],
                     DEPT_COLOR["SALES"]),
        ], className="grid grid-4", style={"marginBottom": "16px"}),

        html.Div([
            card("Achats par mois",
                 dcc.Graph(figure=charts.bar_chart(
                     [charts.fr_period(r["period"]) for r in monthly], [r["amount"] for r in monthly],
                     sym, horizontal=False, height=280, color=DEPT_COLOR["PURCH"],
                     show_values=False), config={"displayModeBar": False}) if monthly
                 else empty_state("Aucune commande enregistrée."),
                 note="Montant des commandes fournisseurs, hors commandes annulées.",
                 className="span-2"),
            card("Dépense par fournisseur",
                 dcc.Graph(figure=charts.share_bars(
                     [s["name"] for s in sups[:6]], [s["spend"] for s in sups[:6]], sym,
                     height=max(200, 44 * min(6, len(sups)) + 60)),
                     config={"displayModeBar": False}) if sups
                 else empty_state("Aucun fournisseur.")),
        ], className="grid grid-3"),

        html.Div([
            card("Plan de réapprovisionnement par fournisseur",
                 data_table(
                     plan,
                     [{"name": "Fournisseur", "id": "supplier"},
                      num_col("Références", "refs", 0),
                      num_col("Unités", "units", 0),
                      num_col(f"Montant ({sym})", "amount", 0),
                      num_col("Délai (j)", "lead_time_days", 0)],
                     "tbl-plan", page_size=8) if plan
                 else empty_state("Aucun réapprovisionnement nécessaire."),
                 note="Une commande par fournisseur, prête à être passée."),
            card("Fournisseurs",
                 data_table(
                     sups,
                     [{"name": "Fournisseur", "id": "name"},
                      {"name": "Contact", "id": "contact_name"},
                      {"name": "Téléphone", "id": "phone"},
                      num_col("Délai (j)", "lead_time_days", 0),
                      num_col("Note", "rating", 1),
                      num_col("Références", "refs", 0),
                      num_col(f"Dépense ({sym})", "spend", 0)],
                     "tbl-suppliers", page_size=8),
                 note="Note fournisseur sur 5 : qualité, respect des délais, litiges."),
        ], className="grid grid-2", style={"marginTop": "14px"}),

        html.Div([
            card("Commandes fournisseurs",
                 data_table(
                     orders,
                     [{"name": "Référence", "id": "ref"},
                      {"name": "Fournisseur", "id": "supplier"},
                      {"name": "Commandée le", "id": "ordered_on"},
                      {"name": "Reçue le", "id": "received_on"},
                      {"name": "Statut", "id": "status"},
                      num_col("Lignes", "lines", 0),
                      num_col(f"Total ({sym})", "total", 0)],
                     "tbl-purchases", page_size=12, filter_action="native",
                     style_data_conditional=[
                         {"if": {"filter_query": "{status} = 'commandée'"},
                          "backgroundColor": "#fdf3e2", "color": "#7a5307"},
                     ]),
                 note="Passer une commande au statut « reçue » déclenche l'entrée en "
                      "stock par trigger SQL, sans intervention du magasinier."),
        ], style={"marginTop": "14px"}),
    ])


def _avg(rows: list[dict], key: str) -> float:
    values = [r[key] for r in rows if r.get(key) is not None]
    return sum(values) / len(values) if values else 0
