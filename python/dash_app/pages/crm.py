"""Département Clients — segments, valeur vie client, fidélité, clients dormants."""

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
    segments = q.customer_segments(db=db)
    top = q.customers(150, db=db)
    dormant = q.dormant_customers(45, 20, db=db)
    acquisition = q.customer_acquisition(db=db)

    total = db.scalar("SELECT COUNT(*) FROM customers")
    active = db.scalar(
        "SELECT COUNT(DISTINCT customer_id) FROM sales"
        " WHERE status = 'payée' AND sale_date >= date('now', ?)", (f"-{days} day",))
    identified = db.scalar(
        """SELECT ROUND(100.0 * SUM(customer_id IS NOT NULL) / COUNT(*), 1)
             FROM sales WHERE status = 'payée' AND sale_date >= date('now', ?)""",
        (f"-{days} day",))
    ltv = sum(c["lifetime_value"] or 0 for c in top)
    points = db.scalar("SELECT COALESCE(SUM(loyalty_points), 0) FROM customers")

    return html.Div([
        page_header("👥  Clients",
                    "La fiche client se remplit toute seule : chaque encaissement met à "
                    "jour son historique, sa valeur et ses points de fidélité."),

        html.Div([
            kpi_tile("Clients au fichier", f"{total:,}".replace(",", " "),
                     [f"{active} actifs sur {days} j"], DEPT_COLOR["CRM"]),
            kpi_tile("Taux d'identification", f"{identified or 0} %",
                     ["des tickets rattachés à un client"], DEPT_COLOR["SALES"]),
            kpi_tile("Valeur vie cumulée", compact_money(ltv, sym),
                     ["tous clients confondus"], DEPT_COLOR["FIN"]),
            kpi_tile("Points de fidélité", f"{int(points):,}".replace(",", " "),
                     ["1 point par tranche encaissée"], DEPT_COLOR["HR"]),
        ], className="grid grid-4", style={"marginBottom": "16px"}),

        html.Div([
            card("Chiffre d'affaires par segment",
                 dcc.Graph(figure=charts.share_bars(
                     [s["segment"] for s in segments], [s["revenue"] for s in segments],
                     sym, height=max(210, 48 * len(segments) + 60)),
                     config={"displayModeBar": False}) if segments
                 else empty_state("Aucun client."),
                 note="Un professionnel pèse plusieurs fois un particulier : "
                      "le nombre de clients ne dit pas la valeur."),
            card("Poids des segments",
                 data_table(
                     segments,
                     [{"name": "Segment", "id": "segment"},
                      num_col("Clients", "customers", 0),
                      num_col(f"CA ({sym})", "revenue", 0),
                      num_col(f"Panier ({sym})", "avg_basket", 0),
                      num_col("Commandes", "avg_orders", 1)],
                     "tbl-segments", page_size=6),
                 note="La vue table du graphique ci-contre."),
            card("Nouveaux clients par mois",
                 dcc.Graph(figure=charts.bar_chart(
                     [charts.fr_period(r["period"]) for r in acquisition[-14:]],
                     [r["customers"] for r in acquisition[-14:]],
                     None, horizontal=False, height=250, color=DEPT_COLOR["CRM"],
                     show_values=False), config={"displayModeBar": False}) if acquisition
                 else empty_state("Aucune acquisition."),
                 note="Date de première inscription au fichier."),
        ], className="grid grid-3"),

        html.Div([
            card("Meilleurs clients",
                 data_table(
                     top[:60],
                     [{"name": "Client", "id": "customer"},
                      {"name": "Segment", "id": "segment"},
                      {"name": "Ville", "id": "city"},
                      num_col("Commandes", "orders", 0),
                      num_col(f"Valeur vie ({sym})", "lifetime_value", 0),
                      num_col(f"Panier ({sym})", "avg_basket", 0),
                      num_col("Points", "loyalty_points", 0),
                      {"name": "Dernier achat", "id": "last_purchase"}],
                     "tbl-customers", page_size=12, filter_action="native"),
                 note="Vue SQL v_customer_value, classée par valeur vie.",
                 className="span-2"),
            card("Clients à relancer",
                 data_table(
                     dormant,
                     [{"name": "Client", "id": "customer"},
                      num_col("Jours", "days_since_last", 0),
                      num_col(f"Valeur ({sym})", "lifetime_value", 0)],
                     "tbl-dormant", page_size=12) if dormant
                 else empty_state("Aucun client dormant : tout le fichier est actif."),
                 note="Bons clients sans achat depuis plus de 45 jours."),
        ], className="grid grid-3", style={"marginTop": "14px"}),
    ])
