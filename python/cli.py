#!/usr/bin/env python3
"""Création d'une boutique en ligne de commande.

Utile pour préparer une base avant de lancer un dashboard ou l'API, et pour
alimenter le front web sans passer par l'écran d'accueil.

Exemples :
    python cli.py types
    python cli.py create "Chez Aminata" supermarche
    python cli.py create "Pharmacie du Plateau" pharmacie --months 24 --currency EUR
    python cli.py stats
    python cli.py reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from erp import queries as q  # noqa: E402
from erp.config import CURRENCIES, compact_money, list_store_types  # noqa: E402
from erp.database import get_db  # noqa: E402
from erp.generator import create_company, reset_database  # noqa: E402


def cmd_types(_args: argparse.Namespace) -> int:
    print("\nTypes de boutiques disponibles\n" + "─" * 78)
    for t in list_store_types():
        print(f"  {t['icon']}  {t['key']:<14} {t['label']}")
        print(f"      {t['tagline']}")
        print(f"      {t['n_categories']} rayons · {t['n_products']} produits · "
              f"{t['n_roles']} métiers · TVA {t['tax_rate'] * 100:.0f} %\n")
    print("Devises : " + ", ".join(f"{c['code']} ({c['symbol']})" for c in CURRENCIES))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    width = 46

    def progress(label: str, pct: float) -> None:
        filled = int(pct * width)
        bar = "█" * filled + "░" * (width - filled)
        print(f"\r  {bar} {pct * 100:3.0f} %  {label[:38]:<38}", end="", flush=True)

    print(f"\nCréation de l'ERP « {args.name} »…\n")
    try:
        summary = create_company(
            args.name, args.type, currency=args.currency, city=args.city,
            country=args.country, history_months=args.months,
            traffic_scale=args.traffic, progress=progress,
        )
    except KeyError as exc:
        print(f"\n\n  Erreur : {exc}\n", file=sys.stderr)
        return 2

    sym = get_db().company()["currency_sym"]
    print("\n\n  " + summary["store_label"])
    print("  " + "─" * 60)
    rows = [
        ("Période couverte", f"{summary['period_start']} → {summary['period_end']}"),
        ("Rayons / produits", f"{summary['categories']} / {summary['products']}"),
        ("Fournisseurs", summary["suppliers"]),
        ("Clients", summary["customers"]),
        ("Salariés", summary["employees"]),
        ("Tickets de caisse", f"{summary['sales']:,}".replace(",", " ")),
        ("Lignes de vente", f"{summary['sale_items']:,}".replace(",", " ")),
        ("Mouvements de stock", f"{summary['stock_moves']:,}".replace(",", " ")),
        ("Chiffre d'affaires", compact_money(summary["revenue"], sym)),
        ("Valeur du stock", compact_money(summary["stock_value"], sym)),
    ]
    for label, value in rows:
        print(f"  {label:<22} {value}")
    print(f"\n  Base : {get_db().path}")
    print("  Dashboard Python : python -m dash_app.app")
    print("  API REST         : uvicorn api.main:app --port 8000")
    print("  Dashboard R      : Rscript -e \"shiny::runApp('../shiny')\"\n")
    return 0


def cmd_stats(_args: argparse.Namespace) -> int:
    db = get_db()
    company = db.company()
    if not company:
        print("Aucune boutique configurée. Lancez : python cli.py create <nom> <type>")
        return 1
    sym = company["currency_sym"]
    k = q.kpis(30)
    print(f"\n  {company['logo_emoji']}  {company['name']}, {company['store_label']}")
    print("  " + "─" * 60)
    print(f"  CA (30 j)          {compact_money(k['revenue'], sym)}"
          f"   ({k['tickets']} tickets)")
    print(f"  Marge brute        {compact_money(k['margin'], sym)}"
          f"   (taux {k['margin_rate'] * 100:.1f} %)")
    print(f"  Panier moyen       {compact_money(k['avg_basket'], sym)}")
    print(f"  Valeur du stock    {compact_money(k['stock_value'], sym)}")
    print(f"  Alertes de stock   {k['stock_alerts']} dont {k['out_of_stock']} rupture(s)")
    print(f"  Effectif           {k['headcount']} salariés")
    print(f"  Résultat du mois   {compact_money(k['net_result'], sym)}\n")
    print("  Départements")
    for d in q.department_summary():
        print(f"    {d['name']:<22} {d['metric']:<32} "
              f"{compact_money(d['value'], sym) if d['dept'] != 'CRM' else int(d['value'])}")
    print()
    return 0


def cmd_reset(_args: argparse.Namespace) -> int:
    reset_database(get_db())
    print("Base réinitialisée. La plateforme repartira sur l'écran d'accueil.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py", description="Plateforme ERP Boutique, outil en ligne de commande.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("types", help="lister les types de boutiques").set_defaults(func=cmd_types)

    create = sub.add_parser("create", help="créer l'ERP d'une boutique")
    create.add_argument("name", help="nom de la boutique")
    create.add_argument("type", help="clé du type de boutique (voir « types »)")
    create.add_argument("--currency", default="XOF")
    create.add_argument("--city", default="Abidjan")
    create.add_argument("--country", default="Côte d'Ivoire")
    create.add_argument("--months", type=int, default=12, help="profondeur d'historique")
    create.add_argument("--traffic", type=float, default=1.0, help="intensité d'activité")
    create.set_defaults(func=cmd_create)

    sub.add_parser("stats", help="afficher les indicateurs").set_defaults(func=cmd_stats)
    sub.add_parser("reset", help="vider la base").set_defaults(func=cmd_reset)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
