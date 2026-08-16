import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ActivityRow } from '../core/models';
import { compact, dateTime, deltaParts, deptColor, STOCK_STATUS } from '../core/format';

/** Tuile d'indicateur : un chiffre qui se lit sans graphique. */
@Component({
  selector: 'erp-kpi',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card kpi">
      <span class="kpi-accent" [style.background]="accent()"></span>
      <div class="kpi-label">{{ label() }}</div>
      <div class="kpi-value">{{ value() }}</div>
      <div class="kpi-foot"><ng-content /></div>
    </div>
  `,
})
export class KpiComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly accent = input<string>('var(--ink-muted)');
}

/** Carte de contenu : titre, note explicative, corps projeté. */
@Component({
  selector: 'erp-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card">
      <h3 class="card-title">{{ title() }}</h3>
      @if (note()) {
        <p class="card-note">{{ note() }}</p>
      } @else {
        <div style="height:8px"></div>
      }
      <ng-content />
    </section>
  `,
})
export class CardComponent {
  readonly title = input.required<string>();
  readonly note = input<string>('');
}

/** Évolution période sur période, flèche + valeur, jamais la couleur seule. */
@Component({
  selector: 'erp-delta',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="delta {{ parts().cls }}">{{ parts().arrow }} {{ parts().text }}</span>
  `,
})
export class DeltaComponent {
  readonly pct = input<number | null>(null);
  protected readonly parts = computed(() => deltaParts(this.pct()));
}

/** Pastille d'état de stock : couleur + icône + libellé. */
@Component({
  selector: 'erp-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="badge {{ spec().cls }}">
      <span class="badge-dot" [style.background]="'var(--' + spec().cls + ')'"></span>
      {{ spec().icon }} {{ spec().label }}
    </span>
  `,
})
export class BadgeComponent {
  readonly status = input.required<string>();
  protected readonly spec = computed(
    () => STOCK_STATUS[this.status()] ?? { cls: '', icon: '•', label: this.status() });
}

/** En-tête de page : titre du département et phrase d'explication. */
@Component({
  selector: 'erp-page-head',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="page-head">
      <h1 class="page-title">{{ title() }}</h1>
      <p class="page-sub">{{ subtitle() }}</p>
    </header>
  `,
})
export class PageHeadComponent {
  readonly title = input.required<string>();
  readonly subtitle = input<string>('');
}

/** État vide, utilisé partout où une requête ne ramène aucune ligne. */
@Component({
  selector: 'erp-empty',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="empty"><span class="mark">∅</span>{{ message() }}</div>`,
})
export class EmptyComponent {
  readonly message = input<string>('Aucune donnée.');
}

/** Flux d'activité inter-départements. */
@Component({
  selector: 'erp-feed',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @for (row of decorated(); track $index) {
      <div class="feed-row">
        <span class="feed-tag" [style.background]="row.color">{{ row.tag }}</span>
        <span class="feed-label" [title]="row.full">{{ row.label }}</span>
        <span class="feed-amount">{{ row.amount }}</span>
        <span class="feed-time">{{ row.when }}</span>
      </div>
    } @empty {
      <erp-empty message="Aucune écriture." />
    }
  `,
  imports: [EmptyComponent],
})
export class FeedComponent {
  readonly rows = input.required<ActivityRow[]>();
  readonly symbol = input<string>('');

  private static readonly TAGS: Record<string, string> = {
    SALES: 'VENTE', PURCH: 'ACHAT', STOCK: 'STOCK', FIN: 'CHARGE',
  };

  protected readonly decorated = computed(() => this.rows().map((row) => ({
    tag: FeedComponent.TAGS[row.dept] ?? row.dept,
    color: deptColor(row.dept),
    full: row.label,
    label: row.label.replace(/^Vente /, '').replace(/^Commande /, '').replace(/^Charge, /, ''),
    amount: row.dept === 'STOCK'
      ? `${row.amount > 0 ? '+' : ''}${row.amount} u.`
      : compact(row.amount, this.symbol()),
    when: dateTime(row.at),
  })));
}

export const UI_COMPONENTS = [
  KpiComponent, CardComponent, DeltaComponent, BadgeComponent,
  PageHeadComponent, EmptyComponent, FeedComponent,
] as const;
