"""Système visuel partagé (lecture de ``shared/theme.json``).

La palette catégorielle est validée : bande de clarté, plancher de chroma,
séparation daltonisme sur les paires adjacentes et plancher vision normale.
Règles appliquées partout dans les dashboards :

* les couleurs de série sont assignées dans un **ordre fixe**, un filtre qui
  réduit le nombre de séries ne repeint jamais les survivantes ;
* les couleurs de **statut** (rupture, alerte…) sont réservées et toujours
  accompagnées d'une icône et d'un libellé ;
* le texte porte les jetons d'encre, jamais la couleur de la série ;
* pas de double axe Y, deux mesures d'échelles différentes = deux graphiques.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

from .config import SHARED_DIR


@lru_cache(maxsize=1)
def load_theme() -> dict[str, Any]:
    with (SHARED_DIR / "theme.json").open(encoding="utf-8") as fh:
        return json.load(fh)


THEME = load_theme()
SERIES: list[str] = THEME["categorical"]["light"]
SEQUENTIAL: list[str] = THEME["sequential"]["light"]
STATUS: dict[str, str] = {k: v for k, v in THEME["status"].items() if k != "note"}
SURFACE: dict[str, str] = THEME["surface"]["light"]
DEPT_COLOR: dict[str, str] = THEME["departments"]
FONT = THEME["typography"]["font_family"]

# Statut de stock -> (couleur, icône, libellé). L'icône et le libellé sont
# obligatoires : la couleur ne porte jamais l'information seule.
STOCK_BADGE = {
    "rupture": (STATUS["critical"], "⛔", "Rupture"),
    "alerte": (STATUS["serious"], "▲", "À commander"),
    "faible": (STATUS["warning"], "•", "Stock faible"),
    "ok": (STATUS["good"], "✓", "Disponible"),
}


def series_color(index: int) -> str:
    """Couleur de la n-ième série (ordre fixe, repliée au-delà de 8)."""
    return SERIES[index % len(SERIES)]


def color_map(labels: list[str]) -> dict[str, str]:
    """Associe durablement une couleur à chaque libellé (ordre d'apparition)."""
    return {label: series_color(i) for i, label in enumerate(labels)}


def sequential_scale(n: int) -> list[str]:
    """n pas d'une rampe séquentielle mono-teinte, du clair au foncé."""
    if n <= 1:
        return [SEQUENTIAL[7]]
    usable = SEQUENTIAL[3:]                       # respecte le plancher ordinal
    step = (len(usable) - 1) / (n - 1)
    return [usable[int(round(i * step))] for i in range(n)]


# --------------------------------------------------------------------------
# Gabarit Plotly : grille discrète, axes en encre atténuée, pas de fioriture
# --------------------------------------------------------------------------
ERP_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, size=13, color=SURFACE["ink_secondary"]),
        title=dict(font=dict(size=15, color=SURFACE["ink_primary"]), x=0, xanchor="left"),
        paper_bgcolor=SURFACE["chart"],
        plot_bgcolor=SURFACE["chart"],
        colorway=SERIES,
        margin=dict(l=56, r=20, t=48, b=44),
        hoverlabel=dict(font=dict(family=FONT, size=12), bgcolor="#ffffff",
                        bordercolor=SURFACE["axis"]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=12, color=SURFACE["ink_secondary"]),
                    bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=SURFACE["axis"],
                   ticks="outside", tickcolor=SURFACE["axis"], ticklen=4,
                   tickfont=dict(color=SURFACE["ink_muted"], size=12)),
        yaxis=dict(gridcolor=SURFACE["grid"], zeroline=False, showline=False,
                   tickfont=dict(color=SURFACE["ink_muted"], size=12)),
    )
)
pio.templates["erp"] = ERP_TEMPLATE
pio.templates.default = "erp"


def apply_layout(fig: go.Figure, title: str = "", height: int = 300, **kwargs) -> go.Figure:
    """Finition commune à tous les graphiques."""
    fig.update_layout(template="erp", title=title or None, height=height,
                      showlegend=kwargs.pop("showlegend", False), **kwargs)
    return fig
