import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { FinanceResponse, FinancialMonth } from '../core/models';
import { compact, deptColor, percent, periodLabel } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { Column, DataTableComponent, TableRow } from '../shared/data-table.component';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Département Finance. */
@Component({
  selector: 'erp-finance',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS, DataTableComponent],
  template: `
    @if (data(); as d) {
      <erp-page-head title="Finance"
        subtitle="Le compte de résultat n'est pas ressaisi : ventes, coût des marchandises,
                  charges et paie remontent automatiquement des autres départements." />

      <div class="grid grid-4">
        <erp-kpi [label]="'CA, ' + periodOf(last())" [value]="fmt(last().revenue)"
                 [accent]="c('SALES')">dernier mois clos</erp-kpi>
        <erp-kpi label="Marge brute" [value]="fmt(margin())" [accent]="c('FIN')">
          {{ last().revenue ? 'taux ' + pct(margin() / last().revenue) : 'n.d.' }}
        </erp-kpi>
        <erp-kpi label="Charges + paie" [value]="fmt(last().expenses + last().payroll)"
                 [accent]="c('HR')">structure et salaires</erp-kpi>
        <erp-kpi label="Résultat net" [value]="fmt(last().net_result)"
                 [accent]="last().net_result >= 0 ? 'var(--good)' : 'var(--critical)'">
          {{ last().net_result >= 0 ? 'bénéfice' : 'perte' }}
        </erp-kpi>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Chiffre d'affaires, coût des marchandises et charges"
                    note="Trois mesures dans la même unité, donc un seul axe de valeurs.">
            <erp-grouped-bar-chart [x]="monthLabels()" [series]="monthSeries()"
                                   [symbol]="symbol()" [height]="300" />
          </erp-card>
        </div>
        <erp-card title="Charges par nature" note="Sur douze mois glissants.">
          <erp-share-chart [labels]="categoryLabels()" [values]="categoryValues()"
                           [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-2 mt">
        <erp-card title="Compte de résultat mensuel"
                  note="Vue SQL v_financial_monthly. Le dernier mois est partiel.">
          <erp-table [rows]="d.monthly" [columns]="monthlyCols" [symbol]="symbol()"
                     [limit]="13" [rowClass]="lossClass" />
        </erp-card>
        <erp-card title="Journal des charges" note="150 dernières écritures.">
          <erp-table [rows]="d.entries" [columns]="expenseCols" [symbol]="symbol()"
                     [limit]="13" />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class FinanceComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<FinanceResponse | null>(null);
  protected readonly error = signal('');

  private static readonly EMPTY_MONTH: FinancialMonth = {
    period: '', revenue: 0, cogs: 0, expenses: 0, payroll: 0, net_result: 0,
  };

  protected readonly monthlyCols: Column[] = [
    { key: 'period', label: 'Période' },
    { key: 'revenue', label: 'CA', type: 'money' },
    { key: 'cogs', label: 'Coût march.', type: 'money' },
    { key: 'expenses', label: 'Charges', type: 'money' },
    { key: 'payroll', label: 'Paie', type: 'money' },
    { key: 'net_result', label: 'Résultat', type: 'money', strong: true },
  ];

  protected readonly expenseCols: Column[] = [
    { key: 'spent_on', label: 'Date' },
    { key: 'label', label: 'Libellé' },
    { key: 'category', label: 'Nature' },
    { key: 'department', label: 'Département' },
    { key: 'amount', label: 'Montant', type: 'money', strong: true },
  ];

  protected readonly lossClass = (row: TableRow): string =>
    (row as FinancialMonth).net_result < 0 ? 'row-critical' : '';

  constructor() {
    effect(() => {
      this.api.finance().subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(v: number): string { return compact(v, this.symbol()); }
  protected pct(v: number): string { return percent(v); }
  protected c(code: string): string { return deptColor(code); }
  protected periodOf(month: FinancialMonth): string { return periodLabel(month.period); }

  /** Dernier mois CLOS : le mois en cours est partiel et fausserait la lecture. */
  protected readonly last = computed<FinancialMonth>(() => {
    const months = this.data()?.monthly ?? [];
    const closed = months.length > 1 ? months.slice(0, -1) : months;
    return closed[closed.length - 1] ?? FinanceComponent.EMPTY_MONTH;
  });

  protected readonly margin = computed(() => this.last().revenue - this.last().cogs);
  protected readonly monthLabels = computed(
    () => (this.data()?.monthly ?? []).map((r) => periodLabel(r.period)));
  protected readonly monthSeries = computed(() => ({
    "Chiffre d'affaires": (this.data()?.monthly ?? []).map((r) => r.revenue),
    'Coût des marchandises': (this.data()?.monthly ?? []).map((r) => r.cogs),
    'Charges + paie': (this.data()?.monthly ?? []).map((r) => r.expenses + r.payroll),
  }));
  protected readonly categoryLabels = computed(
    () => (this.data()?.by_category ?? []).map((r) => r.category));
  protected readonly categoryValues = computed(
    () => (this.data()?.by_category ?? []).map((r) => r.amount));
}
