#!/usr/bin/env python3
"""Prépare le test de parité entre les piles Python et R.

Objectif : produire une base SQL avec la pile Python, puis relever les
indicateurs qu'elle en tire. Le test R (`tests/test_shiny.R`) lit ensuite
**la même base** et doit retrouver exactement les mêmes chiffres.

C'est la garantie la plus forte du projet : si les deux piles divergent,
c'est qu'une des deux a réimplémenté une règle au lieu de lire la vue SQL.

    python3 tests/parity_reference.py /chemin/base.db
    Rscript  tests/test_shiny.R      /chemin/base.db
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from erp import queries as q  # noqa: E402
from erp.database import Database  # noqa: E402
from erp.generator import create_company  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: parity_reference.py <chemin/base.db> [type_de_boutique]",
              file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    store_type = sys.argv[2] if len(sys.argv) > 2 else "quincaillerie"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()

    db = Database(path)
    create_company("Boutique de parité", store_type, db=db,
                   history_months=4, traffic_scale=0.5)

    kpis = q.kpis(30, db=db)
    reference = {
        "store_type": store_type,
        "revenue": kpis["revenue"],
        "tickets": kpis["tickets"],
        "margin": kpis["margin"],
        "avg_basket": kpis["avg_basket"],
        "stock_value": kpis["stock_value"],
        "stock_alerts": kpis["stock_alerts"],
        "headcount": kpis["headcount"],
        "net_result": kpis["net_result"],
        "products": len(q.products(db=db)),
        "suppliers": len(q.suppliers(db=db)),
        "financial_months": len(q.financial_monthly(db=db)),
    }

    reference_path = Path(str(path) + ".kpis.json")
    reference_path.write_text(json.dumps(reference, indent=2), encoding="utf-8")

    print(f"  base de parité : {path}")
    print(f"  référence      : {reference_path}")
    print(f"  CA (30 j) {reference['revenue']:,.0f} · {reference['tickets']} tickets · "
          f"{reference['products']} produits")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
