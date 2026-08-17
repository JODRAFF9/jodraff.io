import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { SalesResponse, SaleRow } from '../core/models';
import { compact, deptColor, num, percent, shortDay } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent, TableRow } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Ventes. */
@Component({
  selector: 'erp-sales',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="Ventes"
        subtitle="Chaque ticket enregistré décharge le stock, alimente la fiche client et le
                  compte de résultat, sans aucune ressaisie." />

      <div class="grid grid-4">
        <erp-kpi label="Chiffre d'affaires" [value]="fmt(d.kpis.revenue)" [accent]="c('SALES')">
          <erp-delta [pct]="d.kpis.revenue_delta" /> sur {{ days() }} j
        </erp-kpi>
        <erp-kpi label="Tickets" [value]="count(d.kpis.tickets)" [accent]="c('SALES')">
          <erp-delta [pct]="d.kpis.tickets_delta" />
        </erp-kpi>
        <erp-kpi label="Panier moyen" [value]="fmt(d.kpis.avg_basket)" [accent]="c('SALES')">
          <erp-delta [pct]="d.kpis.avg_basket_delta" /> par ticket
        </erp-kpi>
        <erp-kpi label="Marge brute" [value]="fmt(d.kpis.margin)" [accent]="c('FIN')">
          taux {{ pct(d.kpis.margin_rate) }}
        </erp-kpi>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Chiffre d'affaires et tickets"
                    note="Deux unités différentes : deux graphiques superposés, jamais un
                          second axe Y.">
            <erp-line-chart [x]="dayLabels()" [series]="revenueSeries()"
                            [symbol]="symbol()" [height]="210" [fill]="true" />
            <erp-line-chart [x]="dayLabels()" [series]="ticketSeries()" [height]="150" />
          </erp-card>
        </div>
        <erp-card title="Modes de paiement" note="Part de chaque moyen d'encaissement.">
          <erp-share-chart [labels]="labels(d.by_payment)" [values]="values(d.by_payment)"
                           [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Ventes par heure"
                    note="Nombre de tickets, utile pour caler les plannings d'équipe.">
            <erp-bar-chart [labels]="hourLabels()" [values]="hourValues()" [height]="250" />
          </erp-card>
        </div>
        <erp-card title="Canaux de vente" note="Boutique, téléphone, livraison, en ligne.">
          <erp-share-chart [labels]="labels(d.by_channel)" [values]="values(d.by_channel)"
                           [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-2 mt">
        <erp-card title="Top 10 des produits" note="Classement par chiffre d'affaires HT.">
          <erp-table [rows]="d.top_products" [columns]="productCols" [symbol]="symbol()"
                     [limit]="10" />
        </erp-card>
        <erp-card title="Journal des ventes" note="Les tickets annulés apparaissent en rouge.">
          <erp-table [rows]="d.recent" [columns]="saleCols" [symbol]="symbol()"
                     [limit]="12" [rowClass]="saleRowClass" />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class SalesComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<SalesResponse | null>(null);
  protected readonly error = signal('');
  protected readonly days = this.api.days;

  protected readonly productCols: Column[] = [
    { key: 'product', label: 'Produit' },
    { key: 'category', label: 'Rayon' },
    { key: 'qty_sold', label: 'Quantité', type: 'num' },
    { key: 'revenue_ht', label: 'CA HT', type: 'money', strong: true },
    { key: 'margin', label: 'Marge', type: 'money' },
  ];

  protected readonly saleCols: Column[] = [
    { key: 'ref', label: 'Référence' },
    { key: 'sold_at', label: 'Date', type: 'date' },
    { key: 'customer', label: 'Client' },
    { key: 'seller', label: 'Vendeur' },
    { key: 'payment_method', label: 'Paiement' },
    { key: 'total', label: 'Total', type: 'money', strong: true },
  ];

  protected readonly saleRowClass = (row: TableRow): string =>
    (row as SaleRow).status === 'annulée' ? 'row-critical' : '';

  constructor() {
    effect(() => {
      this.api.sales(this.api.days()).subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected count(v: number): string { return num(v); }
  protected pct(v: number): string { return percent(v); }
  protected c(code: string): string { return deptColor(code); }
  protected labels(rows: { label: string }[]): string[] { return rows.map((r) => r.label); }
  protected values(rows: { revenue: number }[]): number[] { return rows.map((r) => r.revenue); }

  protected readonly dayLabels = computed(
    () => (this.data()?.daily ?? []).map((r) => shortDay(r.sale_date)));
  protected readonly revenueSeries = computed(
    () => ({ 'CA TTC': (this.data()?.daily ?? []).map((r) => r.revenue) }));
  protected readonly ticketSeries = computed(
    () => ({ Tickets: (this.data()?.daily ?? []).map((r) => r.tickets) }));
  protected readonly hourLabels = computed(
    () => (this.data()?.by_hour ?? []).map((r) => `${r.label} h`));
  protected readonly hourValues = computed(
    () => (this.data()?.by_hour ?? []).map((r) => r.tickets));
}
