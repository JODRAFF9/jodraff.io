import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { HrResponse } from '../core/models';
import { compact, deptColor, periodLabel } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Ressources humaines. */
@Component({
  selector: 'erp-hr',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="Ressources humaines"
        subtitle="L'équipe est reliée aux ventes : le même identifiant salarié sert à la paie
                  et au calcul de la performance commerciale." />

      <div class="grid grid-4">
        <erp-kpi label="Effectif" [value]="'' + d.employees.length" [accent]="c('HR')">
          {{ d.by_department.length }} services
        </erp-kpi>
        <erp-kpi label="Masse salariale" [value]="fmt(payrollTotal())" [accent]="c('FIN')">
          par mois, salaires bruts
        </erp-kpi>
        <erp-kpi label="Salariés encaissant" [value]="'' + sellers().length"
                 [accent]="c('SALES')">reliés à un ticket</erp-kpi>
        <erp-kpi label="CA moyen par vendeur" [value]="fmt(avgRevenue())" [accent]="c('CRM')">
          sur tout l'historique
        </erp-kpi>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Masse salariale versée par mois"
                    note="Segments empilés séparés par 2 px : les parts restent lisibles.">
            <erp-grouped-bar-chart [x]="payrollLabels()" [series]="payrollSeries()"
                                   [symbol]="symbol()" [height]="280" [stacked]="true" />
          </erp-card>
        </div>
        <erp-card title="Effectif par service" note="Répartition des postes.">
          <erp-share-chart [labels]="deptLabels()" [values]="deptHeadcount()" />
        </erp-card>
      </div>

      <div class="grid grid-3 mt">
        <erp-card title="Coût par service" note="La vue table du graphique ci-dessus.">
          <erp-table [rows]="d.by_department" [columns]="deptCols" [symbol]="symbol()"
                     [limit]="8" />
        </erp-card>
        <div class="span-2">
          <erp-card title="Performance commerciale de l'équipe"
                    note="Vue SQL v_employee_performance : jointure RH × Ventes. Un poste sans
                          encaissement affiche logiquement zéro ticket.">
            <erp-table [rows]="d.employees" [columns]="staffCols" [symbol]="symbol()"
                       [limit]="10" />
          </erp-card>
        </div>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class HrComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<HrResponse | null>(null);
  protected readonly error = signal('');

  protected readonly deptCols: Column[] = [
    { key: 'department', label: 'Service' },
    { key: 'headcount', label: 'Effectif', type: 'num' },
    { key: 'payroll', label: 'Masse salariale', type: 'money', strong: true },
    { key: 'avg_salary', label: 'Salaire moyen', type: 'money' },
  ];

  protected readonly staffCols: Column[] = [
    { key: 'employee', label: 'Salarié' },
    { key: 'role', label: 'Poste' },
    { key: 'department', label: 'Service' },
    { key: 'salary', label: 'Salaire', type: 'money' },
    { key: 'tickets', label: 'Tickets', type: 'num' },
    { key: 'revenue', label: 'CA généré', type: 'money', strong: true },
    { key: 'avg_basket', label: 'Panier moyen', type: 'money' },
  ];

  constructor() {
    effect(() => {
      this.api.hr().subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected c(code: string): string { return deptColor(code); }

  protected readonly payrollTotal = computed(
    () => (this.data()?.by_department ?? []).reduce((a, r) => a + (r.payroll ?? 0), 0));
  protected readonly sellers = computed(
    () => (this.data()?.employees ?? []).filter((e) => e.tickets > 0));
  protected readonly avgRevenue = computed(() => {
    const list = this.sellers();
    return list.reduce((a, e) => a + (e.revenue ?? 0), 0) / Math.max(1, list.length);
  });
  protected readonly payrollLabels = computed(
    () => (this.data()?.payroll ?? []).map((r) => periodLabel(r.period)));
  protected readonly payrollSeries = computed(() => ({
    'Salaires nets': (this.data()?.payroll ?? []).map((r) => r.net),
    Primes: (this.data()?.payroll ?? []).map((r) => r.bonus),
  }));
  protected readonly deptLabels = computed(
    () => (this.data()?.by_department ?? []).map((r) => r.department));
  protected readonly deptHeadcount = computed(
    () => (this.data()?.by_department ?? []).map((r) => r.headcount));
}
