"""Constructeurs de graphiques.

Règles appliquées systématiquement :
  * un seul axe de valeurs — jamais deux échelles Y sur un même graphique ;
  * marques fines, extrémités arrondies, écart de 2 px entre segments empilés ;
  * légende dès 2 séries, étiquettes directes sélectives (jamais toutes) ;
  * grille discrète, axes en encre atténuée ;
  * survol actif par défaut (curseur unifié sur les courbes).
"""

from __future__ import annotations

import plotly.graph_objects as go

from erp.config import compact_money
from erp.theme import SERIES, STATUS, SURFACE, apply_layout, sequential_scale, series_color

HOVER = "<b>%{x}</b><br>%{y:,.0f}<extra></extra>"


def _fmt_axis(fig: go.Figure, symbol: str | None) -> None:
    """Graduations compactes (12 k, 4,2 M) : un axe monétaire brut est illisible."""
    if symbol:
        fig.update_yaxes(tickformat="~s", ticksuffix=f" {symbol}", automargin=True)
    else:
        fig.update_yaxes(tickformat="~s", automargin=True)


def fr_period(period: str) -> str:
    """'2026-02' -> 'févr. 2026' — et force l'axe en catégories, pas en dates."""
    mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
            "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    try:
        year, month = period.split("-")[:2]
        return f"{mois[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return period


def fr_day(day: str) -> str:
    """'2026-08-16' -> '16/08'."""
    try:
        y, m, d = day.split("-")
        return f"{d}/{m}"
    except ValueError:
        return day


def line_chart(x: list, series: dict[str, list], symbol: str | None = None,
               height: int = 290, fill: bool = False, title: str = "") -> go.Figure:
    """Évolution dans le temps. Courbes de 2 px, marqueurs masqués, survol unifié."""
    fig = go.Figure()
    for i, (label, values) in enumerate(series.items()):
        color = series_color(i)
        fig.add_trace(go.Scatter(
            x=x, y=values, name=label, mode="lines",
            line=dict(color=color, width=2, shape="spline", smoothing=0.4),
            fill="tozeroy" if (fill and len(series) == 1) else None,
            fillcolor=_alpha(color, 0.10) if fill else None,
            hovertemplate=f"{label} : %{{y:,.0f}}<extra></extra>",
        ))
    apply_layout(fig, title, height, showlegend=len(series) > 1)
    fig.update_xaxes(type="category", nticks=9, automargin=True)
    _fmt_axis(fig, symbol)
    return fig


def bar_chart(labels: list[str], values: list[float], symbol: str | None = None,
              horizontal: bool = True, height: int = 300, color: str | None = None,
              title: str = "", show_values: bool = True) -> go.Figure:
    """Comparaison de grandeurs. Une seule série -> une seule couleur, pas de légende."""
    c = color or series_color(0)
    text = [compact_money(v, symbol) if symbol else f"{v:,.0f}".replace(",", " ")
            for v in values] if show_values else None
    fig = go.Figure(go.Bar(
        x=values if horizontal else labels,
        y=labels if horizontal else values,
        orientation="h" if horizontal else "v",
        marker=dict(color=c, cornerradius=4),
        text=text, textposition="auto",
        textfont=dict(size=11.5, color=SURFACE["ink_secondary"]),
        hovertemplate="%{y}<br><b>%{x:,.0f}</b><extra></extra>" if horizontal
                      else "%{x}<br><b>%{y:,.0f}</b><extra></extra>",
    ))
    apply_layout(fig, title, height)
    if horizontal:
        fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
        fig.update_xaxes(gridcolor=SURFACE["grid"], showgrid=True, showticklabels=False)
    else:
        _fmt_axis(fig, symbol)
    return fig


def grouped_bars(x: list[str], series: dict[str, list], symbol: str | None = None,
                 height: int = 300, title: str = "", stacked: bool = False) -> go.Figure:
    """Plusieurs séries comparables sur la MÊME échelle (sinon : deux graphiques)."""
    fig = go.Figure()
    for i, (label, values) in enumerate(series.items()):
        fig.add_trace(go.Bar(
            x=x, y=values, name=label,
            marker=dict(color=series_color(i), cornerradius=4,
                        line=dict(width=2, color=SURFACE["chart"]) if stacked else None),
            hovertemplate=f"{label} : %{{y:,.0f}}<extra></extra>",
        ))
    apply_layout(fig, title, height, showlegend=True,
                 barmode="stack" if stacked else "group", bargap=0.28, bargroupgap=0.08)
    fig.update_xaxes(type="category", automargin=True)
    _fmt_axis(fig, symbol)
    return fig


def waterfall(labels: list[str], values: list[float], symbol: str,
              height: int = 320, title: str = "") -> go.Figure:
    """Passage du chiffre d'affaires au résultat (paire divergente bleu / rouge)."""
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        text=[compact_money(v, symbol) for v in values],
        textposition="outside", textfont=dict(size=11.5, color=SURFACE["ink_secondary"]),
        connector=dict(line=dict(color=SURFACE["axis"], width=1)),
        increasing=dict(marker=dict(color=SERIES[0])),
        decreasing=dict(marker=dict(color=STATUS["critical"])),
        totals=dict(marker=dict(color=SERIES[6])),
        hovertemplate="%{x}<br><b>%{y:,.0f}</b><extra></extra>",
    ))
    apply_layout(fig, title, height)
    fig.update_xaxes(type="category", automargin=True)
    _fmt_axis(fig, symbol)
    return fig


def heatmap(z: list[list[float]], x: list[str], y: list[str], height: int = 300,
            title: str = "", unit: str = "") -> go.Figure:
    """Magnitude continue : rampe mono-teinte clair -> foncé, jamais un arc-en-ciel."""
    scale = sequential_scale(9)
    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        colorscale=[[i / (len(scale) - 1), c] for i, c in enumerate(scale)],
        hovertemplate=f"%{{y}} · %{{x}}<br><b>%{{z:,.0f}}{unit}</b><extra></extra>",
        colorbar=dict(thickness=9, outlinewidth=0, len=0.85,
                      tickfont=dict(size=11, color=SURFACE["ink_muted"])),
        xgap=2, ygap=2,
    ))
    apply_layout(fig, title, height)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def dumbbell(labels: list[str], left: list[float], right: list[float],
             left_name: str, right_name: str, symbol: str | None = None,
             height: int = 320, title: str = "") -> go.Figure:
    """Deux mesures de MÊME unité par catégorie (ex. valeur d'achat vs valeur de vente)."""
    fig = go.Figure()
    for i, lab in enumerate(labels):
        fig.add_trace(go.Scatter(
            x=[left[i], right[i]], y=[lab, lab], mode="lines",
            line=dict(color=SURFACE["axis"], width=2), hoverinfo="skip",
            showlegend=False,
        ))
    for values, name, idx in ((left, left_name, 0), (right, right_name, 2)):
        fig.add_trace(go.Scatter(
            x=values, y=labels, mode="markers", name=name,
            marker=dict(size=11, color=series_color(idx),
                        line=dict(width=2, color=SURFACE["chart"])),
            hovertemplate=f"{name} · %{{y}}<br><b>%{{x:,.0f}}</b><extra></extra>",
        ))
    apply_layout(fig, title, height, showlegend=True)
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    _fmt_axis(fig, symbol)
    return fig


def share_bars(labels: list[str], values: list[float], symbol: str,
               height: int = 300, title: str = "") -> go.Figure:
    """Répartition : barres horizontales triées + part en %, plus lisibles qu'un camembert."""
    total = sum(values) or 1
    text = [f"{compact_money(v, symbol)}  ·  {v / total * 100:.0f} %" for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=[series_color(i) for i in range(len(labels))], cornerradius=4),
        text=text, textposition="outside", cliponaxis=False,
        textfont=dict(size=11.5, color=SURFACE["ink_secondary"]),
        hovertemplate="%{y}<br><b>%{x:,.0f}</b><extra></extra>",
    ))
    apply_layout(fig, title, height)
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    fig.update_xaxes(showticklabels=False, showgrid=False,
                     range=[0, max(values) * 1.95 if values else 1])
    return fig


def _alpha(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"
