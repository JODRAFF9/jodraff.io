"""Écran de démarrage de la plateforme.

C'est le point d'entrée décrit dans le cahier des charges : l'utilisateur
indique **le type de boutique** et **son nom**, et l'ERP complet est créé.
Rien d'autre n'est demandé, devise, ville et profondeur d'historique ont
des valeurs par défaut raisonnables.
"""

from __future__ import annotations

from dash import dcc, html

from erp.config import CURRENCIES, DEPARTMENTS, list_store_types


def layout(message: html.Div | None = None) -> html.Div:
    types = list_store_types()
    return html.Div(
        html.Div([
            html.Div("ERP Boutique", className="onboard-mark"),
            html.H1("Créez le tableau de bord de votre boutique"),
            html.P(
                "Dites simplement quel commerce vous exploitez et comment il s'appelle. "
                "La plateforme génère un ERP complet, ventes, stock, achats, clients, "
                "ressources humaines et finance, avec un historique d'activité déjà "
                "consolidé dans une base SQL unique.",
                className="lead"),

            # ---- Étape 1 : le type de boutique ------------------------
            html.Div([
                html.Span("1", className="step-num"), "Quel type de boutique ?",
            ], className="step-label"),
            html.Div(
                [
                    html.Button(
                        [
                            html.Div(t["icon"], className="type-icon"),
                            html.Div(t["label"], className="type-name"),
                            html.Div(t["tagline"], className="type-tag"),
                            html.Div([
                                html.Span(f"{t['n_categories']} rayons"),
                                html.Span(f"{t['n_products']} produits"),
                                html.Span(f"{t['n_roles']} métiers"),
                            ], className="type-meta"),
                        ],
                        id={"type": "store-type", "index": t["key"]},
                        className="type-card",
                        n_clicks=0,
                    )
                    for t in types
                ],
                className="type-grid",
            ),

            # ---- Étape 2 : l'identité de la boutique -------------------
            html.Div([
                html.Span("2", className="step-num"), "Comment s'appelle-t-elle ?",
            ], className="step-label", style={"marginTop": "26px"}),
            html.Div([
                html.Div([
                    html.Label("Nom de la boutique", htmlFor="in-name"),
                    dcc.Input(id="in-name", type="text", placeholder="Ex. : Chez Aminata",
                              debounce=False, autoComplete="off"),
                ], className="field"),
                html.Div([
                    html.Label("Ville", htmlFor="in-city"),
                    dcc.Input(id="in-city", type="text", value="Abidjan"),
                ], className="field"),
                html.Div([
                    html.Label("Pays", htmlFor="in-country"),
                    dcc.Input(id="in-country", type="text", value="Côte d'Ivoire"),
                ], className="field"),
            ], className="grid grid-3", style={"marginBottom": "12px"}),

            html.Details([
                html.Summary("Options avancées",
                             style={"cursor": "pointer", "fontSize": "13px",
                                    "color": "#52514e", "fontWeight": "600",
                                    "padding": "6px 0"}),
                html.Div([
                    html.Div([
                        html.Label("Devise", htmlFor="in-currency"),
                        dcc.Dropdown(
                            id="in-currency",
                            options=[{"label": f"{c['label']} ({c['symbol']})",
                                      "value": c["code"]} for c in CURRENCIES],
                            value="XOF", clearable=False,
                            style={"fontSize": "14px"}),
                    ], className="field"),
                    html.Div([
                        html.Label("Profondeur d'historique", htmlFor="in-months"),
                        dcc.Dropdown(
                            id="in-months",
                            options=[{"label": "6 mois", "value": 6},
                                     {"label": "12 mois", "value": 12},
                                     {"label": "24 mois", "value": 24}],
                            value=12, clearable=False, style={"fontSize": "14px"}),
                        html.Span("Plus l'historique est long, plus la génération "
                                  "prend de temps.", className="hint"),
                    ], className="field"),
                    html.Div([
                        html.Label("Intensité d'activité", htmlFor="in-traffic"),
                        dcc.Dropdown(
                            id="in-traffic",
                            options=[{"label": "Petit commerce (×0,4)", "value": 0.4},
                                     {"label": "Activité normale (×1)", "value": 1.0},
                                     {"label": "Forte affluence (×2)", "value": 2.0}],
                            value=1.0, clearable=False, style={"fontSize": "14px"}),
                    ], className="field"),
                ], className="grid grid-3", style={"marginTop": "10px"}),
            ], style={"marginBottom": "18px"}),

            html.Div(id="onboard-message", children=message or _departments_note()),

            html.Div([
                html.Button("Créer mon tableau de bord", id="btn-create",
                            className="btn", n_clicks=0),
                html.Span(id="onboard-echo",
                          style={"fontSize": "13px", "color": "#52514e"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "14px",
                      "marginTop": "18px"}),

            dcc.Loading(html.Div(id="onboard-status"), type="dot", color="#2a78d6"),
        ], className="onboard"),
        className="onboard-page",
    )


def _departments_note() -> html.Div:
    return html.Div([
        html.Div([
            html.B("Les six départements sont livrés d'office "),
            html.Span(", ".join(d["name"] for d in DEPARTMENTS[1:])),
            html.Div("Ils partagent une seule base de données : une vente décharge le "
                     "stock, met à jour la fiche client et le compte de résultat "
                     "au même instant.",
                     style={"marginTop": "4px", "opacity": .85}),
        ]),
    ], className="notice notice-info")


def success_panel(summary: dict, symbol: str) -> html.Div:
    """Récapitulatif affiché juste après la génération."""
    from erp.config import compact_money

    items = [
        ("Rayons", summary["categories"]), ("Produits", summary["products"]),
        ("Fournisseurs", summary["suppliers"]), ("Clients", summary["customers"]),
        ("Salariés", summary["employees"]),
        ("Tickets de caisse", f"{summary['sales']:,}".replace(",", " ")),
        ("Lignes de vente", f"{summary['sale_items']:,}".replace(",", " ")),
        ("Mouvements de stock", f"{summary['stock_moves']:,}".replace(",", " ")),
        ("Chiffre d'affaires", compact_money(summary["revenue"], symbol)),
        ("Valeur du stock", compact_money(summary["stock_value"], symbol)),
    ]
    return html.Div([
        html.Div([
            html.Div([
                html.B(f"« {summary['company']} » est prête."),
                html.Div(f"{summary['store_label']}, historique du "
                         f"{summary['period_start']} au {summary['period_end']}.",
                         style={"marginTop": "3px", "opacity": .85}),
            ]),
        ], className="notice notice-ok", style={"marginBottom": "14px"}),
        html.Div([
            html.Div([html.Div(str(v), className="v"), html.Div(k, className="k")],
                     className="summary-item")
            for k, v in items
        ], className="summary-grid"),
        html.Button("Ouvrir le tableau de bord →", id="btn-open", className="btn",
                    n_clicks=0, style={"marginTop": "18px"}),
    ])
