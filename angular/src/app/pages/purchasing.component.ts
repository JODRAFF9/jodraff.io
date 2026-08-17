import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { PurchasingResponse, PurchaseOrder } from '../core/models';
import { compact, deptColor, periodLabel, seriesColor } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent, TableRow } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Achats. */
@Component({
  selector: 'erp-purchasing',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="Achats"
        subtitle="Le plan de commande n'est pas saisi : il est déduit des niveaux de stock
                  et des ventes, puis groupé par fournisseur." />

      <div class="grid grid-4">
        <erp-kpi label="Fournisseurs actifs" [value]="'' + d.suppliers.length"
                 [accent]="c('PURCH')">au référentiel</erp-kpi>
        <erp-kpi label="Commandes en cours" [value]="'' + pending()" [accent]="c('STOCK')">
          en attente de réception
        </erp-kpi>
        <erp-kpi label="Réappro. suggéré" [value]="fmt(planAmount())" [accent]="c('SALES')">
          {{ planRefs() }} références sous le seuil
        </erp-kpi>
        <erp-kpi label="Total commandé" [value]="fmt(totalOrdered())" [accent]="c('FIN')">
          sur tout l'historique
        </erp-kpi>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Achats par mois"
                    note="Montant des commandes fournisseurs, hors commandes annulées.">
            <erp-bar-chart [labels]="monthLabels()" [values]="monthValues()"
                           [symbol]="symbol()" [height]="270" [color]="green" />
          </erp-card>
        </div>
        <erp-card title="Dépense par fournisseur" note="Les six premiers.">
          <erp-share-chart [labels]="supplierNames()" [values]="supplierSpend()"
                           [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-2 mt">
        <erp-card title="Plan de réapprovisionnement"
                  note="Une commande par fournisseur, prête à être passée.">
          <erp-table [rows]="d.reorder_plan" [columns]="planCols" [symbol]="symbol()"
                     [limit]="8" empty="Aucun réapprovisionnement nécessaire." />
        </erp-card>
        <erp-card title="Fournisseurs" note="Note sur 5 : qualité, délais, litiges.">
          <erp-table [rows]="d.suppliers" [columns]="supplierCols" [symbol]="symbol()"
                     [limit]="8" />
        </erp-card>
      </div>

      <div class="mt">
        <erp-card title="Commandes fournisseurs"
                  note="Passer une commande au statut « reçue » déclenche l'entrée en stock
                        par trigger SQL, sans intervention du magasinier.">
          <erp-table [rows]="d.orders" [columns]="orderCols" [symbol]="symbol()"
                     [limit]="12" [rowClass]="orderRowClass" />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class PurchasingComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<PurchasingResponse | null>(null);
  protected readonly error = signal('');
  protected readonly green = seriesColor(2);

  protected readonly planCols: Column[] = [
    { key: 'supplier', label: 'Fournisseur' },
    { key: 'refs', label: 'Réf.', type: 'num' },
    { key: 'units', label: 'Unités', type: 'num' },
    { key: 'amount', label: 'Montant', type: 'money', strong: true },
    { key: 'lead_time_days', label: 'Délai (j)', type: 'num' },
  ];

  protected readonly supplierCols: Column[] = [
    { key: 'name', label: 'Fournisseur' },
    { key: 'contact_name', label: 'Contact' },
    { key: 'lead_time_days', label: 'Délai (j)', type: 'num' },
    { key: 'rating', label: 'Note', type: 'num', decimals: 1 },
    { key: 'refs', label: 'Références', type: 'num' },
    { key: 'spend', label: 'Dépense', type: 'money', strong: true },
  ];

  protected readonly orderCols: Column[] = [
    { key: 'ref', label: 'Référence' },
    { key: 'supplier', label: 'Fournisseur' },
    { key: 'ordered_on', label: 'Commandée le' },
    { key: 'received_on', label: 'Reçue le' },
    { key: 'status', label: 'Statut' },
    { key: 'total', label: 'Total', type: 'money', strong: true },
  ];

  protected readonly orderRowClass = (row: TableRow): string =>
    (row as PurchaseOrder).status === 'commandée' ? 'row-serious' : '';

  constructor() {
    effect(() => {
      this.api.purchasing().subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected c(code: string): string { return deptColor(code); }

  protected readonly pending = computed(
    () => (this.data()?.orders ?? []).filter((o) => o.status === 'commandée').length);
  protected readonly planAmount = computed(
    () => (this.data()?.reorder_plan ?? []).reduce((a, r) => a + (r.amount ?? 0), 0));
  protected readonly planRefs = computed(
    () => (this.data()?.reorder_plan ?? []).reduce((a, r) => a + r.refs, 0));
  protected readonly totalOrdered = computed(
    () => (this.data()?.monthly ?? []).reduce((a, r) => a + (r.amount ?? 0), 0));
  protected readonly monthLabels = computed(
    () => (this.data()?.monthly ?? []).map((r) => periodLabel(r.period)));
  protected readonly monthValues = computed(
    () => (this.data()?.monthly ?? []).map((r) => r.amount));
  protected readonly supplierNames = computed(
    () => (this.data()?.suppliers ?? []).slice(0, 6).map((s) => s.name));
  protected readonly supplierSpend = computed(
    () => (this.data()?.suppliers ?? []).slice(0, 6).map((s) => s.spend));
}
