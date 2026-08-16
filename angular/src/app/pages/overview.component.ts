import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from '../core/api.service';
import { OverviewResponse } from '../core/models';
import { compact, deptColor, percent, periodLabel, num, shortDay } from '../core/format';
import { CHART_COMPONENTS } from '../shared/chart.components';
import { UI_COMPONENTS } from '../shared/ui.components';

/** Vue d'ensemble : la consolidation de tous les départements. */
@Component({
  selector: 'erp-overview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...UI_COMPONENTS, ...CHART_COMPONENTS],
  template: `
    @if (data(); as d) {
      <erp-page-head
        [title]="d.company.logo_emoji + '  ' + d.company.name"
        [subtitle]="d.company.store_label + ' — ' + d.company.city + ', ' + d.company.country +
                    '. Toutes les cartes sont calculées en direct sur la base SQL centrale.'" />

      <div class="grid grid-kpi">
        <erp-kpi label="Chiffre d'affaires" [value]="fmt(d.kpis.revenue)"
                 [accent]="color('SALES')">
          <erp-delta [pct]="d.kpis.revenue_delta" /> sur {{ days() }} j
        </erp-kpi>
        <erp-kpi label="Marge brute" [value]="fmt(d.kpis.margin)" [accent]="color('FIN')">
          <erp-delta [pct]="d.kpis.margin_delta" /> taux {{ pct(d.kpis.margin_rate) }}
        </erp-kpi>
        <erp-kpi label="Tickets" [value]="count(d.kpis.tickets)" [accent]="color('CRM')">
          <erp-delta [pct]="d.kpis.tickets_delta" /> {{ d.kpis.customers }} clients identifiés
        </erp-kpi>
        <erp-kpi label="Panier moyen" [value]="fmt(d.kpis.avg_basket)" [accent]="color('SALES')">
          <erp-delta [pct]="d.kpis.avg_basket_delta" /> par ticket
        </erp-kpi>
        <erp-kpi label="Valeur du stock" [value]="fmt(d.kpis.stock_value)"
                 [accent]="color('STOCK')">
          ⛔ {{ d.kpis.out_of_stock }} rupture(s) · ▲ {{ d.kpis.stock_alerts }} à commander
        </erp-kpi>
        <erp-kpi label="Résultat du mois" [value]="fmt(d.kpis.net_result)" [accent]="color('HR')">
          masse salariale {{ fmt(d.kpis.payroll) }}
        </erp-kpi>
      </div>

      <div class="mt">
        <erp-card title="Départements connectés à la base centrale"
                  note="Une écriture faite dans un département met immédiatement à jour les
                        indicateurs des autres — c'est le rôle des triggers SQL.">
          <div class="dept-strip">
            @for (dept of d.departments; track dept.dept) {
              <span class="dept-chip">
                <span class="dept-dot" [style.background]="color(dept.dept)"></span>
                <b>{{ dept.name }}</b> · {{ count(dept.count) }} {{ dept.count_label }}
              </span>
            }
          </div>
          <div class="summary-grid" style="margin-top:12px">
            @for (dept of d.departments; track dept.dept) {
              <div class="summary-item" [style.border-left-color]="color(dept.dept)">
                <div class="k">{{ dept.metric }}</div>
                <div class="v">
                  {{ dept.dept === 'CRM' ? count(dept.value) : fmt(dept.value) }}
                </div>
              </div>
            }
          </div>
        </erp-card>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Chiffre d'affaires quotidien"
                    note="Source : département Ventes. Survolez la courbe pour le détail.">
            <erp-line-chart [x]="dailyLabels()" [series]="dailySeries()"
                            [symbol]="symbol()" [height]="270" [fill]="true" />
          </erp-card>
        </div>
        <erp-card title="Répartition par rayon"
                  [note]="'Chiffre d\\'affaires HT des ' + days() + ' derniers jours.'">
          <erp-share-chart [labels]="categoryLabels()" [values]="categoryValues()"
                           [symbol]="symbol()" />
        </erp-card>
      </div>

      <div class="grid grid-3 mt">
        <div class="span-2">
          <erp-card title="Chiffre d'affaires et marge par mois"
                    note="Deux mesures de même unité, donc un seul axe de valeurs.">
            <erp-grouped-bar-chart [x]="monthLabels()" [series]="monthSeries()"
                                   [symbol]="symbol()" [height]="290" />
          </erp-card>
        </div>
        <erp-card title="Dernières écritures"
                  note="Ventes, achats, mouvements de stock et charges, tous départements.">
          <erp-feed [rows]="d.activity" [symbol]="symbol()" />
        </erp-card>
      </div>
    } @else {
      <erp-empty [message]="error() || 'Chargement…'" />
    }
  `,
})
export class OverviewComponent {
  private readonly api = inject(ApiService);

  protected readonly data = signal<OverviewResponse | null>(null);
  protected readonly error = signal('');
  protected readonly days = this.api.days;

  constructor() {
    effect(() => {
      const days = this.api.days();
      this.api.overview(days).subscribe({
        next: (response) => this.data.set(response),
        error: (err: { message?: string }) => this.error.set(err.message ?? 'Erreur'),
      });
    });
  }

  protected symbol(): string { return this.api.symbol(); }
  protected fmt(value: number): string { return compact(value, this.symbol()); }
  protected count(value: number): string { return num(value); }
  protected pct(value: number): string { return percent(value); }
  protected color(code: string): string { return deptColor(code); }

  protected readonly dailyLabels = computed(
    () => (this.data()?.sales_daily ?? []).map((r) => shortDay(r.sale_date)));
  protected readonly dailySeries = computed(() => ({
    'CA TTC': (this.data()?.sales_daily ?? []).map((r) => r.revenue),
  }));
  protected readonly categoryLabels = computed(
    () => (this.data()?.sales_by_category ?? []).map((r) => r.category));
  protected readonly categoryValues = computed(
    () => (this.data()?.sales_by_category ?? []).map((r) => r.revenue));
  protected readonly monthLabels = computed(
    () => (this.data()?.sales_monthly ?? []).map((r) => periodLabel(r.period)));
  protected readonly monthSeries = computed(() => ({
    'CA HT': (this.data()?.sales_monthly ?? []).map((r) => r.revenue_ht),
    'Marge brute': (this.data()?.sales_monthly ?? []).map((r) => r.gross_margin),
  }));
}
