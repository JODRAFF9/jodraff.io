"""Chargement du catalogue partagé des types de boutiques.

Le fichier ``shared/store_types.json`` est la référence commune à la
plateforme R Shiny et à la plateforme Python : modifier ce fichier suffit
à ajouter un nouveau métier (rayons, produits, rôles, fournisseurs...)
dans les deux applications, l'API REST et les fronts web.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Localisation des ressources partagées
# --------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
SHARED_DIR = Path(os.environ.get("ERP_SHARED_DIR", PROJECT_ROOT / "shared"))
CATALOG_PATH = SHARED_DIR / "store_types.json"
SCHEMA_PATH = SHARED_DIR / "schema.sql"
MIGRATIONS_PATH = SHARED_DIR / "migrations.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Lit et met en cache le catalogue JSON partagé."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalogue introuvable : {CATALOG_PATH}. "
            "Définissez ERP_SHARED_DIR vers le dossier 'shared/' du projet."
        )
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


CATALOG: dict[str, Any] = load_catalog()
STORE_TYPES: dict[str, Any] = CATALOG["types"]
CURRENCIES: list[dict[str, Any]] = CATALOG["currencies"]
PAYMENT_METHODS: list[str] = CATALOG["payment_methods"]
CUSTOMER_SEGMENTS: list[dict[str, Any]] = CATALOG["customer_segments"]
FIRST_NAMES: list[str] = CATALOG["first_names"]
LAST_NAMES: list[str] = CATALOG["last_names"]

# --------------------------------------------------------------------------
# Départements de l'ERP : l'axe autour duquel les données sont centralisées
# --------------------------------------------------------------------------
DEPARTMENTS: list[dict[str, Any]] = [
    {"code": "OVERVIEW", "name": "Vue d'ensemble", "position": 0,
     "description": "Consolidation temps réel de tous les départements."},
    {"code": "SALES", "name": "Ventes", "position": 1,
     "description": "Encaissements, tickets, panier moyen, performance vendeurs."},
    {"code": "STOCK", "name": "Stock", "position": 2,
     "description": "Niveaux, mouvements, valorisation, alertes de rupture."},
    {"code": "PURCH", "name": "Achats", "position": 3,
     "description": "Fournisseurs, commandes, réapprovisionnement suggéré."},
    {"code": "CRM", "name": "Clients", "position": 4,
     "description": "Segments, valeur vie client, fidélité, clients dormants."},
    {"code": "HR", "name": "Ressources humaines", "position": 5,
     "description": "Effectif, masse salariale, paie, performance commerciale."},
    {"code": "FIN", "name": "Finance", "position": 6,
     "description": "Compte de résultat, charges, marge, trésorerie."},
]

DEPARTMENT_BY_CODE = {d["code"]: d for d in DEPARTMENTS}


def list_store_types() -> list[dict[str, Any]]:
    """Retourne les types de boutiques sous forme de liste prête pour l'UI."""
    out = []
    for key, spec in STORE_TYPES.items():
        out.append(
            {
                "key": key,
                "label": spec["label"],
                "icon": spec["icon"],
                "tagline": spec["tagline"],
                "tax_rate": spec["tax_rate"],
                "margin_target": spec["margin_target"],
                "n_categories": len(spec["categories"]),
                "n_products": sum(len(c["products"]) for c in spec["categories"]),
                "n_roles": len(spec["roles"]),
            }
        )
    return sorted(out, key=lambda t: t["label"])


def get_store_type(key: str) -> dict[str, Any]:
    """Spécification complète d'un type de boutique."""
    if key not in STORE_TYPES:
        raise KeyError(
            f"Type de boutique inconnu : '{key}'. "
            f"Valeurs possibles : {', '.join(sorted(STORE_TYPES))}"
        )
    return STORE_TYPES[key]


def get_currency(code: str) -> dict[str, Any]:
    """Définition d'une devise (symbole, décimales, facteur de conversion)."""
    for cur in CURRENCIES:
        if cur["code"] == code:
            return cur
    raise KeyError(f"Devise inconnue : '{code}'")


def format_money(amount: float, symbol: str = "FCFA", decimals: int = 0) -> str:
    """Formatage monétaire lisible (espace fine comme séparateur de milliers)."""
    if amount is None:
        return "n.d."
    formatted = f"{amount:,.{decimals}f}".replace(",", " ").replace(".", ",")
    if decimals == 0:
        formatted = formatted.split(",")[0]
    return f"{formatted} {symbol}"


def compact_money(amount: float, symbol: str = "FCFA") -> str:
    """Formatage compact pour les grandes valeurs (1,2 M FCFA)."""
    if amount is None:
        return "n.d."
    a = abs(amount)
    sign = "-" if amount < 0 else ""
    if a >= 1_000_000_000:
        return f"{sign}{a / 1_000_000_000:.1f}".replace(".", ",") + f" Md {symbol}"
    if a >= 1_000_000:
        return f"{sign}{a / 1_000_000:.1f}".replace(".", ",") + f" M {symbol}"
    if a >= 1_000:
        return f"{sign}{a / 1_000:.1f}".replace(".", ",") + f" k {symbol}"
    return format_money(amount, symbol)
