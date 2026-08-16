"""API REST de l'ERP (FastAPI).

C'est la porte d'entrée des clients web : le front HTML/CSS/JS (``web/``) et
l'application Angular (``angular/``) ne parlent qu'à cette API, qui lit et
écrit dans la **même base SQL** que les dashboards R Shiny et Python.

Lancement :
    cd python && uvicorn api.main:app --reload --port 8000
    Documentation interactive : http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Body, FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from erp import queries as q  # noqa: E402
from erp.config import CURRENCIES, DEPARTMENTS, list_store_types  # noqa: E402
from erp.database import get_db  # noqa: E402
from erp.generator import create_company, reset_database  # noqa: E402
from erp.theme import load_theme  # noqa: E402

app = FastAPI(
    title="ERP Boutique, API",
    version="1.0.0",
    description=(
        "API de la plateforme de gestion de boutique. Toutes les routes lisent "
        "la base SQL centrale partagée par les six départements : Ventes, Stock, "
        "Achats, Clients, Ressources humaines et Finance."
    ),
    contact={"name": "ERP Boutique"},
)

# Les fronts sont servis depuis un autre port en développement.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================================
# Modèles d'entrée
# ==========================================================================
class CompanyCreate(BaseModel):
    """Les deux seules informations demandées à l'utilisateur, plus des options."""

    name: str = Field(..., min_length=1, examples=["Chez Aminata"])
    store_type: str = Field(..., examples=["supermarche"])
    currency: str = "XOF"
    city: str = "Abidjan"
    country: str = "Côte d'Ivoire"
    history_months: int = Field(12, ge=1, le=36)
    traffic_scale: float = Field(1.0, gt=0, le=5)


class SaleLine(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_price: float | None = None
    discount: float = 0


class SaleCreate(BaseModel):
    items: list[SaleLine]
    customer_id: int | None = None
    employee_id: int | None = None
    payment_method: str = "Espèces"
    channel: str = "Boutique"


class StockMoveCreate(BaseModel):
    product_id: int
    quantity: float
    move_type: str = Field(..., examples=["inventaire", "perte", "retour"])
    note: str = ""


class PurchaseLine(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_cost: float | None = None


class PurchaseCreate(BaseModel):
    supplier_id: int
    lines: list[PurchaseLine]


# ==========================================================================
# Configuration & plateforme
# ==========================================================================
def _require_company() -> dict:
    company = get_db().company()
    if not company:
        raise HTTPException(
            status_code=409,
            detail="Aucune boutique configurée. Appelez POST /api/company d'abord.",
        )
    return company


@app.get("/api/health", tags=["Plateforme"])
def health() -> dict:
    db = get_db()
    return {"status": "ok", "configured": db.is_configured(), "database": str(db.path)}


@app.get("/api/store-types", tags=["Plateforme"])
def store_types() -> dict:
    """Catalogue des métiers proposés au démarrage (shared/store_types.json)."""
    return {
        "types": list_store_types(),
        "currencies": CURRENCIES,
        "departments": DEPARTMENTS,
    }


@app.get("/api/theme", tags=["Plateforme"])
def theme() -> dict:
    """Jetons de design partagés, les fronts n'inventent aucune couleur."""
    return load_theme()


@app.get("/api/company", tags=["Plateforme"])
def company() -> dict:
    return _require_company()


@app.post("/api/company", status_code=201, tags=["Plateforme"])
def create(payload: CompanyCreate) -> dict:
    """Crée l'ERP complet à partir du type de boutique et de son nom."""
    try:
        summary = create_company(
            payload.name, payload.store_type,
            currency=payload.currency, city=payload.city, country=payload.country,
            history_months=payload.history_months, traffic_scale=payload.traffic_scale,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"summary": summary, "company": get_db().company()}


@app.delete("/api/company", tags=["Plateforme"])
def delete_company() -> dict:
    reset_database(get_db())
    return {"status": "réinitialisée"}


# ==========================================================================
# Vue d'ensemble
# ==========================================================================
@app.get("/api/overview", tags=["Vue d'ensemble"])
def overview(days: int = Query(30, ge=1, le=1095)) -> dict:
    _require_company()
    return {
        "company": get_db().company(),
        "kpis": q.kpis(days),
        "departments": q.department_summary(),
        "sales_daily": q.sales_daily(max(days, 30)),
        "sales_monthly": q.sales_monthly(),
        "sales_by_category": q.sales_by_category(days),
        "activity": q.recent_activity(12),
    }


@app.get("/api/kpis", tags=["Vue d'ensemble"])
def kpis(days: int = Query(30, ge=1, le=1095)) -> dict:
    _require_company()
    return q.kpis(days)


@app.get("/api/departments", tags=["Vue d'ensemble"])
def departments() -> list[dict]:
    _require_company()
    return q.department_summary()


@app.get("/api/activity", tags=["Vue d'ensemble"])
def activity(limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    _require_company()
    return q.recent_activity(limit)


@app.get("/api/audit", tags=["Vue d'ensemble"])
def audit(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return q.audit_trail(limit)


# ==========================================================================
# Ventes
# ==========================================================================
@app.get("/api/sales", tags=["Ventes"])
def sales(days: int = Query(30, ge=1, le=1095), limit: int = Query(150, ge=1, le=1000)) -> dict:
    _require_company()
    return {
        "kpis": q.kpis(days),
        "daily": q.sales_daily(days),
        "monthly": q.sales_monthly(),
        "by_category": q.sales_by_category(days),
        "by_payment": q.sales_by_dimension("payment", days),
        "by_channel": q.sales_by_dimension("channel", days),
        "by_hour": q.sales_by_dimension("hour", days),
        "top_products": q.top_products(10, days),
        "recent": q.sales_list(limit),
    }


@app.get("/api/sales/{sale_id}", tags=["Ventes"])
def sale(sale_id: int) -> dict:
    detail = q.sale_detail(sale_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Vente {sale_id} introuvable.")
    return detail


@app.post("/api/sales", status_code=201, tags=["Ventes"])
def create_sale(payload: SaleCreate) -> dict:
    """Enregistre une vente. Le stock et la finance sont mis à jour par trigger SQL."""
    _require_company()
    try:
        return q.register_sale(
            [line.model_dump() for line in payload.items],
            customer_id=payload.customer_id, employee_id=payload.employee_id,
            payment_method=payload.payment_method, channel=payload.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ==========================================================================
# Stock
# ==========================================================================
@app.get("/api/stock", tags=["Stock"])
def stock(days: int = Query(60, ge=1, le=1095)) -> dict:
    _require_company()
    return {
        "products": q.products(),
        "alerts": q.stock_alerts(),
        "valuation": q.stock_valuation(),
        "rotation": q.stock_rotation(90),
        "moves": q.stock_moves(150, days),
    }


@app.get("/api/products", tags=["Stock"])
def products(status: str | None = Query(None, pattern="^(ok|faible|alerte|rupture)$")) -> list[dict]:
    _require_company()
    return q.products(status=status)


@app.post("/api/stock/moves", status_code=201, tags=["Stock"])
def stock_move(payload: StockMoveCreate) -> dict:
    _require_company()
    try:
        return q.register_stock_move(payload.product_id, payload.quantity,
                                     payload.move_type, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ==========================================================================
# Achats
# ==========================================================================
@app.get("/api/purchasing", tags=["Achats"])
def purchasing() -> dict:
    _require_company()
    return {
        "suppliers": q.suppliers(),
        "orders": q.purchases(80),
        "monthly": q.purchases_monthly(),
        "reorder_plan": q.reorder_plan(),
    }


@app.post("/api/purchases", status_code=201, tags=["Achats"])
def create_purchase(payload: PurchaseCreate) -> dict:
    _require_company()
    try:
        return q.create_purchase_order(payload.supplier_id,
                                       [line.model_dump() for line in payload.lines])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/purchases/{purchase_id}/receive", tags=["Achats"])
def receive(purchase_id: int) -> dict:
    """Réception : le trigger SQL fait entrer la marchandise en stock."""
    result = q.receive_purchase(purchase_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Commande {purchase_id} introuvable.")
    return result


# ==========================================================================
# Clients, RH, Finance
# ==========================================================================
@app.get("/api/customers", tags=["Clients"])
def customers(limit: int = Query(200, ge=1, le=2000)) -> dict:
    _require_company()
    return {
        "customers": q.customers(limit),
        "segments": q.customer_segments(),
        "dormant": q.dormant_customers(45, 25),
        "acquisition": q.customer_acquisition(),
    }


@app.get("/api/hr", tags=["Ressources humaines"])
def hr() -> dict:
    _require_company()
    return {
        "employees": q.employees(),
        "by_department": q.headcount_by_department(),
        "payroll": q.payroll_history(),
    }


@app.get("/api/finance", tags=["Finance"])
def finance() -> dict:
    _require_company()
    return {
        "monthly": q.financial_monthly(),
        "bridge": q.profit_bridge(),
        "by_category": q.expenses_by_category(),
        "by_department": q.expenses_by_department(),
        "entries": q.expenses_list(150),
    }


@app.exception_handler(KeyError)
def key_error_handler(_request, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def main() -> None:
    import os

    import uvicorn

    uvicorn.run("api.main:app", host=os.environ.get("ERP_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("ERP_API_PORT", 8000)), reload=False)


if __name__ == "__main__":
    main()
