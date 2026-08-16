"""ERP Boutique, noyau Python partagé.

Ce paquet contient tout ce qui ne dépend pas d'une interface :
    config      : catalogue des types de boutiques (shared/store_types.json)
    database    : connexion SQLite, application du schéma SQL, helpers
    generator   : création d'une entreprise + génération de l'historique
    queries     : requêtes métier consolidées (KPI, séries, tableaux)

Il est consommé par :
    dash_app/   : le dashboard Python (Plotly Dash)
    api/        : l'API REST FastAPI (front web + Angular)
    cli.py      : la création de boutique en ligne de commande
"""

from .config import (
    CATALOG,
    STORE_TYPES,
    CURRENCIES,
    DEPARTMENTS,
    get_store_type,
    get_currency,
    list_store_types,
)
from .database import Database, DB_PATH, connect, init_schema
from .generator import create_company, reset_database

__all__ = [
    "CATALOG",
    "STORE_TYPES",
    "CURRENCIES",
    "DEPARTMENTS",
    "get_store_type",
    "get_currency",
    "list_store_types",
    "Database",
    "DB_PATH",
    "connect",
    "init_schema",
    "create_company",
    "reset_database",
]

__version__ = "1.0.0"
