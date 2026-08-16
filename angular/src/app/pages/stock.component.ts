import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { StockResponse, StockAlert } from '../core/models';
import { compact, deptColor } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent, TableRow } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Stock. */
@Component({
  selector: 'erp-stock',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="📦  Stock"
        subtitle="Le stock n'est jamais saisi à la main : il résulte des ventes, des
                  réceptions fournisseurs et des écritures d'inventaire." />

      <div class="grid grid-4">
        <erp-kpi label="Valeur du stock" [value]="fmt(costValue())" [accent]="c('STOCK')">
          au prix de revient · {{ d.products.length }} références
        </erp-kpi>
        <erp-kpi label="Valeur au prix de vente" [value]="fmt(retailValue())" [accent]="c('FIN')">
          marge potentielle {{ fmt(retailValue() - costValue()) }}
        </erp-kpi>
        <erp-kpi label="Ruptures" [value]="'' + outOfStock()" accent="var(--critical)">
          ⛔ vente impossible
        </erp-kpi>
        <erp-kpi label="À commander" [value]="'' + d.alerts.length" accent="var(--serious)">
          ▲ sous le point de commande
        </erp-kpi>
      </div>

      <div class="grid grid-2 mt">
        <erp-card title="Valorisation par rayon"
                  note="Valeur au prix de revient de chaque rayon.">
          <erp-share-chart [labels]="categories()" [values]="costs()" [symbol]="symbol()" />
        </erp-card>
        <erp-card title="Valeur au prix de vente"
                  note="Même rayons, même échelle : l'écart avec le graphique de gauche est
                        la marge immobilisée.">
          <erp-share-chart [labels]="categories()" [values]="retails()" [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-2 mt">
        <erp-card title="Alertes de réapprovisionnement"
                  note="Vue SQL v_stock_alerts, reprise telle quelle par le département Achats.">
          <erp-table [rows]="d.alerts" [columns]="alertCols" [symbol]="symbol()" [limit]="10"
                     [rowClass]="alertRowClass"
                     empty="Aucune alerte : tous les stocks sont au-dessus du seuil." />
        </erp-card>
        <erp-card title="Mouvements de stock"
                  note="Chaque ligne indique le département qui l'a générée.">
          <erp-table [rows]="d.moves" [columns]="moveCols" [symbol]="symbol()" [limit]="12" />
        </erp-card>
      </div>

      <div class="mt">
        <erp-card title="Catalogue complet"
                  note="Vue SQL v_products : prix, marge unitaire, niveau et état de stock.">
          <erp-table [rows]="d.products" [columns]="productCols" [symbol]="symbol()"
                     [limit]="15" />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class StockComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<StockResponse | null>(null);
  protected readonly error = signal('');

  protected readonly alertCols: Column[] = [
    { key: 'product', label: 'Produit' },
    { key: 'supplier', label: 'Fournisseur' },
    { key: 'severity', label: 'État', type: 'badge' },
    { key: 'stock', label: 'Stock', type: 'num', decimals: 1 },
    { key: 'suggested_qty', label: 'À commander', type: 'num' },
    { key: 'suggested_cost', label: 'Coût', type: 'money' },
  ];

  protected readonly moveCols: Column[] = [
    { key: 'moved_at', label: 'Date', type: 'date' },
    { key: 'product', label: 'Produit' },
    { key: 'move_type', label: 'Type' },
    { key: 'source_dept', label: 'Origine' },
    { key: 'quantity', label: 'Quantité', type: 'num', decimals: 1 },
  ];

  protected readonly productCols: Column[] = [
    { key: 'sku', label: 'SKU' },
    { key: 'name', label: 'Produit' },
    { key: 'category', label: 'Rayon' },
    { key: 'cost_price', label: 'Achat', type: 'money' },
    { key: 'sale_price', label: 'Vente', type: 'money' },
    { key: 'margin_rate', label: 'Marge', type: 'percent' },
    { key: 'stock', label: 'Stock', type: 'num', decimals: 1 },
    { key: 'stock_status', label: 'État', type: 'badge' },
    { key: 'stock_value', label: 'Valeur', type: 'money', strong: true },
  ];

  protected readonly alertRowClass = (row: TableRow): string =>
    (row as StockAlert).severity === 'rupture' ? 'row-critical' : 'row-serious';

  constructor() {
    effect(() => {
      this.api.stock(this.api.days()).subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected c(code: string): string { return deptColor(code); }

  protected readonly categories = computed(
    () => (this.data()?.valuation ?? []).map((r) => r.category));
  protected readonly costs = computed(
    () => (this.data()?.valuation ?? []).map((r) => r.value));
  protected readonly retails = computed(
    () => (this.data()?.valuation ?? []).map((r) => r.retail_value));
  protected readonly costValue = computed(
    () => this.costs().reduce((a, b) => a + b, 0));
  protected readonly retailValue = computed(
    () => this.retails().reduce((a, b) => a + b, 0));
  protected readonly outOfStock = computed(
    () => (this.data()?.products ?? []).filter((p) => p.stock_status === 'rupture').length);
}
