"""Une page par département, toutes lisent la même base SQL centrale."""

from . import crm, finance, hr, overview, purchasing, sales, stock

# route -> (code département, fonction de rendu)
ROUTES = {
    "/": ("OVERVIEW", overview.layout),
    "/ventes": ("SALES", sales.layout),
    "/stock": ("STOCK", stock.layout),
    "/achats": ("PURCH", purchasing.layout),
    "/clients": ("CRM", crm.layout),
    "/rh": ("HR", hr.layout),
    "/finance": ("FIN", finance.layout),
}

__all__ = ["ROUTES", "overview", "sales", "stock", "purchasing", "crm", "hr", "finance"]
