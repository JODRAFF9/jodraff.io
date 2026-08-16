"""Dashboard ERP, plateforme Python (Plotly Dash).

Lancement :
    cd python && python -m dash_app.app        (ou : python dash_app/app.py)
    http://127.0.0.1:8050

Au premier démarrage, la base est vide : l'écran d'accueil demande le type de
boutique et son nom, puis génère l'ERP complet. Ensuite, l'application ouvre
directement le tableau de bord.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet « python dash_app/app.py » comme « python -m dash_app.app »
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update  # noqa: E402

from erp.config import DEPARTMENTS  # noqa: E402
from erp.database import get_db  # noqa: E402
from erp.generator import create_company, reset_database  # noqa: E402
from erp.theme import DEPT_COLOR  # noqa: E402

from . import onboarding  # noqa: E402
from .pages import ROUTES  # noqa: E402

NAV = [
    ("/", "OVERVIEW"), ("/ventes", "SALES"), ("/stock", "STOCK"),
    ("/achats", "PURCH"), ("/clients", "CRM"), ("/rh", "HR"), ("/finance", "FIN"),
]
DEPT = {d["code"]: d for d in DEPARTMENTS}

app = Dash(
    __name__,
    title="ERP Boutique, tableau de bord",
    update_title="Calcul…",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server            # point d'entrée WSGI (gunicorn dash_app.app:server)

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="store-type", data=None),      # type choisi à l'onboarding
    dcc.Store(id="store-refresh", data=0),      # incrémenté quand la base change
    dcc.Store(id="store-days", data=30),        # période analysée (barre du haut)
    html.Div(id="root"),
])


# ==========================================================================
# Coquille de l'application
# ==========================================================================
def sidebar(pathname: str, company: dict) -> html.Div:
    links = []
    for path, code in NAV:
        dept = DEPT[code]
        links.append(dcc.Link(
            [html.Span(dept["icon"], className="nav-icon"), html.Span(dept["name"])],
            href=path,
            className="nav-link active" if path == pathname else "nav-link",
            style={"borderLeftColor": DEPT_COLOR.get(code) if path == pathname else "transparent"},
        ))
    return html.Div([
        html.Div([
            html.Span(company["logo_emoji"], className="brand-logo"),
            html.Div([
                html.Div(company["name"], className="brand-name"),
                html.Div(company["store_label"], className="brand-type"),
            ]),
        ], className="brand"),
        html.Div("Départements", className="nav-label"),
        html.Div(links),
        html.Div([
            html.Div("Base SQL centrale"),
            html.Div(f"{company['currency']} · TVA {company['tax_rate'] * 100:.0f} %",
                     style={"marginTop": "3px"}),
            html.Button("Réinitialiser la plateforme", id="btn-reset",
                        className="btn btn-danger", n_clicks=0,
                        style={"marginTop": "12px", "width": "100%", "fontSize": "12.5px",
                               "padding": "8px 10px"}),
        ], className="sidebar-foot"),
    ], className="sidebar")


def topbar(days: int) -> html.Div:
    return html.Div([
        html.Div([
            html.Span("Période analysée", style={"fontSize": "12px", "color": "#898781",
                                                 "fontWeight": "600"}),
            html.Div([
                html.Button(label, id={"type": "period", "index": value},
                            className="on" if value == days else "", n_clicks=0)
                for label, value in [("7 jours", 7), ("30 jours", 30),
                                     ("90 jours", 90), ("12 mois", 365)]
            ], className="seg"),
        ], className="filter-row"),
    ], style={"display": "flex", "justifyContent": "flex-end", "marginBottom": "6px"})


@app.callback(
    Output("root", "children"),
    Input("url", "pathname"),
    Input("store-refresh", "data"),
    Input("store-days", "data"),
)
def render(pathname: str, _refresh: int, days: int | None) -> html.Div:
    db = get_db()
    if not db.is_configured():
        return onboarding.layout()

    days = days or 30
    company = db.company()
    code, view = ROUTES.get(pathname or "/", ROUTES["/"])
    return html.Div([
        sidebar(pathname or "/", company),
        html.Div([topbar(days), view(db, days)], className="main"),
    ], className="shell")


@app.callback(
    Output("store-days", "data"),
    Input({"type": "period", "index": ALL}, "n_clicks"),
    State("store-days", "data"),
    prevent_initial_call=True,
)
def change_period(_clicks, current):
    trigger = callback_context.triggered_id
    if not trigger or not any(_clicks or []):
        return no_update
    return trigger["index"]


# ==========================================================================
# Onboarding
# ==========================================================================
@app.callback(
    Output("store-type", "data"),
    Output({"type": "store-type", "index": ALL}, "className"),
    Input({"type": "store-type", "index": ALL}, "n_clicks"),
    State({"type": "store-type", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def select_type(_clicks, ids):
    trigger = callback_context.triggered_id
    selected = trigger["index"] if trigger else None
    classes = ["type-card selected" if i["index"] == selected else "type-card" for i in ids]
    return selected, classes


@app.callback(
    Output("onboard-echo", "children"),
    Input("store-type", "data"),
    Input("in-name", "value"),
)
def echo(store_type, name):
    if not store_type:
        return "Choisissez d'abord un type de boutique."
    if not (name or "").strip():
        return "Indiquez maintenant le nom de la boutique."
    return f"Prêt : « {name.strip()} »."


@app.callback(
    Output("onboard-status", "children"),
    Input("btn-create", "n_clicks"),
    State("store-type", "data"),
    State("in-name", "value"),
    State("in-city", "value"),
    State("in-country", "value"),
    State("in-currency", "value"),
    State("in-months", "value"),
    State("in-traffic", "value"),
    prevent_initial_call=True,
)
def create(n_clicks, store_type, name, city, country, currency, months, traffic):
    """Étape unique : le choix de l'utilisateur devient un ERP complet."""
    if not n_clicks:
        return no_update
    if not store_type:
        return _warn("Sélectionnez le type de boutique (étape 1).")
    if not (name or "").strip():
        return _warn("Le nom de la boutique est obligatoire (étape 2).")

    db = get_db()
    summary = create_company(
        name, store_type, currency=currency or "XOF",
        city=city or "Abidjan", country=country or "Côte d'Ivoire",
        history_months=int(months or 12), traffic_scale=float(traffic or 1.0), db=db,
    )
    return onboarding.success_panel(summary, db.company()["currency_sym"])


def _warn(message: str) -> html.Div:
    return html.Div([html.Span("⚠️"), html.Span(message)], className="notice notice-warn")


@app.callback(
    Output("store-refresh", "data"),
    Input("btn-open", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def open_dashboard(n_clicks, refresh):
    """Bascule de l'écran d'accueil vers le tableau de bord."""
    return (refresh or 0) + 1 if n_clicks else no_update


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Output("url", "pathname"),
    Input("btn-reset", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def reset(n_clicks, refresh):
    if not n_clicks:
        return no_update, no_update
    reset_database(get_db())
    return (refresh or 0) + 1, "/"


def main() -> None:
    import os

    app.run(
        host=os.environ.get("ERP_HOST", "127.0.0.1"),
        port=int(os.environ.get("ERP_PORT", 8050)),
        debug=os.environ.get("ERP_DEBUG", "0") == "1",
    )


if __name__ == "__main__":
    main()
