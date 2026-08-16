"""Briques d'interface réutilisées par toutes les pages du dashboard."""

from __future__ import annotations

from typing import Any

from dash import dash_table, dcc, html

from erp.config import compact_money, format_money
from erp.theme import DEPT_COLOR, STATUS, STOCK_BADGE, SURFACE


def money(value: float, sym: str = "FCFA", compact: bool = True) -> str:
    return compact_money(value, sym) if compact else format_money(value, sym)


def delta_badge(pct: float | None, positive_is_good: bool = True) -> html.Span:
    """Évolution vs période précédente : flèche + signe + valeur (jamais la couleur seule)."""
    if pct is None:
        return html.Span("— nouvelle période", className="delta flat")
    good = (pct >= 0) if positive_is_good else (pct <= 0)
    cls = "flat" if abs(pct) < 0.05 else ("up" if good else "down")
    arrow = "→" if abs(pct) < 0.05 else ("↑" if pct > 0 else "↓")
    return html.Span(f"{arrow} {abs(pct):.1f} %", className=f"delta {cls}")


def kpi_tile(label: str, value: str, foot: Any = None, accent: str = SURFACE["ink_muted"]) -> html.Div:
    """Stat tile : un chiffre qui se lit sans graphique."""
    return html.Div(
        [
            html.Div(className="kpi-accent", style={"background": accent}),
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
            html.Div(foot or "", className="kpi-foot"),
        ],
        className="card kpi",
    )


def card(title: str, children: Any, note: str = "", className: str = "") -> html.Div:
    head = [html.P(title, className="card-title")]
    if note:
        head.append(html.P(note, className="card-note"))
    return html.Div(head + (children if isinstance(children, list) else [children]),
                    className=f"card {className}".strip())


def status_badge(status: str) -> html.Span:
    """Pastille d'état : couleur + icône + libellé."""
    color, icon, label = STOCK_BADGE.get(status, (SURFACE["ink_muted"], "•", status))
    return html.Span(
        [html.Span(className="badge-dot", style={"background": color}),
         html.Span(f"{icon} {label}")],
        className="badge",
        style={"background": _tint(color), "color": _ink(color)},
    )


def _tint(hex_color: str) -> str:
    return {
        STATUS["good"]: "#eaf7ea", STATUS["warning"]: "#fdf3e2",
        STATUS["serious"]: "#fdefe8", STATUS["critical"]: "#fbeded",
    }.get(hex_color, "#f2f1ee")


def _ink(hex_color: str) -> str:
    return {
        STATUS["good"]: "#0a5d0a", STATUS["warning"]: "#7a5307",
        STATUS["serious"]: "#8a3d17", STATUS["critical"]: "#8f2222",
    }.get(hex_color, SURFACE["ink_2"] if "ink_2" in SURFACE else "#52514e")


def data_table(rows: list[dict], columns: list[dict], table_id: str,
               page_size: int = 12, **kwargs) -> dash_table.DataTable:
    """Tableau : c'est aussi la « vue table » exigée par l'accessibilité des graphiques."""
    return dash_table.DataTable(
        id=table_id,
        data=rows,
        columns=columns,
        page_size=page_size,
        sort_action="native",
        filter_action=kwargs.pop("filter_action", "none"),
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f7f7f4", "fontWeight": "620", "border": "0",
            "borderBottom": f"1px solid {SURFACE['axis']}", "fontSize": "12px",
            "color": SURFACE["ink_secondary"], "textTransform": "uppercase",
            "letterSpacing": ".04em", "padding": "9px 10px",
        },
        style_cell={
            "fontFamily": "system-ui, -apple-system, 'Segoe UI', sans-serif",
            "fontSize": "13px", "padding": "9px 10px", "border": "0",
            "borderBottom": f"1px solid {SURFACE['grid']}",
            "color": SURFACE["ink_primary"], "textAlign": "left",
            "maxWidth": "260px", "overflow": "hidden", "textOverflow": "ellipsis",
        },
        style_data_conditional=kwargs.pop("style_data_conditional", []),
        **kwargs,
    )


def num_col(name: str, key: str, decimals: int = 0, money_fmt: bool = False) -> dict:
    """Colonne numérique alignée à droite, chiffres tabulaires."""
    from dash.dash_table.Format import Format, Group, Scheme

    fmt = Format(group=Group.yes, group_delimiter=" ", decimal_delimiter=",",
                 precision=decimals, scheme=Scheme.fixed)
    return {"name": name, "id": key, "type": "numeric", "format": fmt}


def page_header(title: str, subtitle: str, actions: Any = None) -> html.Div:
    return html.Div(
        [
            html.Div([html.H1(title, className="page-title"),
                      html.P(subtitle, className="page-sub")]),
            html.Div(actions or [], className="filter-row"),
        ],
        className="page-head",
    )


def period_selector(component_id: str, value: int = 30) -> html.Div:
    """Sélecteur de période — une seule rangée de filtres au-dessus des graphiques."""
    return html.Div(
        [
            html.Span("Période", style={"fontSize": "12px", "color": SURFACE["ink_muted"],
                                        "fontWeight": "600", "marginRight": "4px"}),
            dcc.RadioItems(
                id=component_id,
                options=[{"label": "7 j", "value": 7}, {"label": "30 j", "value": 30},
                         {"label": "90 j", "value": 90}, {"label": "12 mois", "value": 365}],
                value=value,
                inline=True,
                className="period-radio",
                labelStyle={"marginRight": "12px", "fontSize": "13px", "cursor": "pointer"},
                inputStyle={"marginRight": "5px"},
            ),
        ],
        className="filter-row",
    )


def dept_chip(code: str, name: str, value: str) -> html.Div:
    return html.Div(
        [html.Span(className="dept-dot", style={"background": DEPT_COLOR.get(code, "#898781")}),
         html.Span([html.B(name), " · ", value])],
        className="dept-chip",
    )


def activity_feed(rows: list[dict], symbol: str) -> html.Div:
    """Flux inter-départements : chaque ligne dit d'où vient l'écriture."""
    labels = {"SALES": "VENTE", "PURCH": "ACHAT", "STOCK": "STOCK", "FIN": "CHARGE"}
    out = []
    for r in rows:
        dept = r["dept"]
        amount = r["amount"] or 0
        text = (f"{amount:+.0f} u." if dept == "STOCK"
                else compact_money(amount, symbol))
        at = r["at"] or ""
        when = f"{at[8:10]}/{at[5:7]} {at[11:16]}" if len(at) >= 16 else at
        label = r["label"] or ""
        for prefix in ("Vente ", "Commande ", "Charge \u2014 "):
            if label.startswith(prefix):
                label = label[len(prefix):]
                break
        out.append(html.Div([
            html.Span(labels.get(dept, dept), className="feed-tag",
                      style={"background": DEPT_COLOR.get(dept, "#898781")}),
            html.Span(label, className="feed-label", title=r["label"]),
            html.Span(text, className="feed-amount"),
            html.Span(when, className="feed-time"),
        ], className="feed-row"))
    return html.Div(out, className="feed")


def empty_state(message: str) -> html.Div:
    return html.Div(
        [html.Div("∅", style={"fontSize": "28px", "opacity": .35}), html.P(message)],
        style={"textAlign": "center", "padding": "34px 10px",
               "color": SURFACE["ink_muted"], "fontSize": "13px"},
    )
