import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { CustomersResponse } from '../core/models';
import { compact, deptColor, num, periodLabel, seriesColor } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Clients (CRM). */
@Component({
  selector: 'erp-customers',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="Clients"
        subtitle="La fiche client se remplit toute seule : chaque encaissement met à jour
                  son historique, sa valeur et ses points de fidélité." />

      <div class="grid grid-4">
        <erp-kpi label="Clients au fichier" [value]="count(d.customers.length)"
                 [accent]="c('CRM')">tous segments</erp-kpi>
        <erp-kpi label="Valeur vie cumulée" [value]="fmt(lifetimeValue())" [accent]="c('FIN')">
          tous clients confondus
        </erp-kpi>
        <erp-kpi label="Points de fidélité" [value]="count(points())" [accent]="c('HR')">
          1 point par tranche encaissée
        </erp-kpi>
        <erp-kpi label="À relancer" [value]="'' + d.dormant.length" accent="var(--serious)">
          sans achat depuis 45 jours
        </erp-kpi>
      </div>

      <div class="grid grid-3 mt">
        <erp-card title="Chiffre d'affaires par segment"
                  note="Un professionnel pèse plusieurs fois un particulier : le nombre de
                        clients ne dit pas la valeur.">
          <erp-share-chart [labels]="segmentLabels()" [values]="segmentValues()"
                           [symbol]="symbol()" />
        </erp-card>
        <erp-card title="Poids des segments" note="La vue table du graphique ci-contre.">
          <erp-table [rows]="d.segments" [columns]="segmentCols" [symbol]="symbol()"
                     [limit]="6" />
        </erp-card>
        <erp-card title="Nouveaux clients par mois"
                  note="Date de première inscription au fichier.">
          <erp-bar-chart [labels]="acquisitionLabels()" [values]="acquisitionValues()"
                         [height]="230" [color]="pink" />
        </erp-card>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Meilleurs clients"
                    note="Vue SQL v_customer_value, classée par valeur vie.">
            <erp-table [rows]="d.customers" [columns]="customerCols" [symbol]="symbol()"
                       [limit]="12" />
          </erp-card>
        </div>
        <erp-card title="Clients à relancer"
                  note="Bons clients sans achat depuis plus de 45 jours.">
          <erp-table [rows]="d.dormant" [columns]="dormantCols" [symbol]="symbol()"
                     [limit]="12" empty="Aucun client dormant : tout le fichier est actif." />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class CustomersComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<CustomersResponse | null>(null);
  protected readonly error = signal('');
  protected readonly pink = seriesColor(4);

  protected readonly segmentCols: Column[] = [
    { key: 'segment', label: 'Segment' },
    { key: 'customers', label: 'Clients', type: 'num' },
    { key: 'revenue', label: 'CA', type: 'money', strong: true },
    { key: 'avg_basket', label: 'Panier', type: 'money' },
  ];

  protected readonly customerCols: Column[] = [
    { key: 'customer', label: 'Client' },
    { key: 'segment', label: 'Segment' },
    { key: 'city', label: 'Ville' },
    { key: 'orders', label: 'Commandes', type: 'num' },
    { key: 'lifetime_value', label: 'Valeur vie', type: 'money', strong: true },
    { key: 'loyalty_points', label: 'Points', type: 'num' },
    { key: 'last_purchase', label: 'Dernier achat' },
  ];

  protected readonly dormantCols: Column[] = [
    { key: 'customer', label: 'Client' },
    { key: 'days_since_last', label: 'Jours', type: 'num' },
    { key: 'lifetime_value', label: 'Valeur', type: 'money' },
  ];

  constructor() {
    effect(() => {
      this.api.customers().subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected count(v: number): string { return num(v); }
  protected c(code: string): string { return deptColor(code); }

  protected readonly lifetimeValue = computed(
    () => (this.data()?.customers ?? []).reduce((a, r) => a + (r.lifetime_value ?? 0), 0));
  protected readonly points = computed(
    () => (this.data()?.customers ?? []).reduce((a, r) => a + (r.loyalty_points ?? 0), 0));
  protected readonly segmentLabels = computed(
    () => (this.data()?.segments ?? []).map((r) => r.segment));
  protected readonly segmentValues = computed(
    () => (this.data()?.segments ?? []).map((r) => r.revenue));
  protected readonly acquisitionLabels = computed(
    () => (this.data()?.acquisition ?? []).slice(-10).map((r) => periodLabel(r.period)));
  protected readonly acquisitionValues = computed(
    () => (this.data()?.acquisition ?? []).slice(-10).map((r) => r.customers));
}
