import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

import { dateTime, money, num, percent } from '../core/format';
import { BadgeComponent, EmptyComponent } from './ui.components';

export interface Column {
  key: string;
  label: string;
  type?: 'text' | 'num' | 'money' | 'percent' | 'date' | 'badge';
  decimals?: number;
  strong?: boolean;
}

/** Une ligne de tableau : n'importe quel objet de données renvoyé par l'API. */
export type TableRow = object;

/** Accès indexé sûr aux champs d'une ligne. */
function cells(row: TableRow): Record<string, unknown> {
  return row as Record<string, unknown>;
}

/**
 * Tableau triable, il tient aussi le rôle de « vue table » des graphiques :
 * l'information reste accessible même quand la couleur ne l'est pas.
 */
@Component({
  selector: 'erp-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [BadgeComponent, EmptyComponent],
  template: `
    @if (!rows().length) {
      <erp-empty [message]="empty()" />
    } @else {
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              @for (col of columns(); track col.key) {
                <th [class.num]="col.type && col.type !== 'text' && col.type !== 'badge'"
                    (click)="sortBy(col.key)" tabindex="0"
                    (keydown.enter)="sortBy(col.key)">
                  {{ col.label }}
                  <span class="sort">{{ arrow(col.key) }}</span>
                </th>
              }
            </tr>
          </thead>
          <tbody>
            @for (row of visible(); track $index) {
              <tr [class]="rowClass()(row)">
                @for (col of columns(); track col.key) {
                  @switch (col.type) {
                    @case ('badge') {
                      <td><erp-badge [status]="text(field(row, col.key))" /></td>
                    }
                    @default {
                      <td [class.num]="col.type && col.type !== 'text'"
                          [class.strong]="col.strong">{{ cell(row, col) }}</td>
                    }
                  }
                }
              </tr>
            }
          </tbody>
        </table>
        <div class="table-foot">
          @if (rows().length > visible().length) {
            {{ visible().length }} lignes affichées sur {{ rows().length }}, }
          cliquez sur un en-tête pour trier.
        </div>
      </div>
    }
  `,
})
export class DataTableComponent {
  readonly rows = input.required<readonly TableRow[]>();
  readonly columns = input.required<Column[]>();
  readonly symbol = input<string>('');
  readonly limit = input<number>(12);
  readonly empty = input<string>('Aucune ligne.');
  readonly rowClass = input<(row: TableRow) => string>(() => '');

  private readonly sortKey = signal<string | null>(null);
  private readonly ascending = signal(false);

  protected readonly visible = computed(() => {
    const rows = [...this.rows()];
    const key = this.sortKey();
    if (key) {
      const asc = this.ascending();
      rows.sort((a, b) => {
        const x = cells(a)[key], y = cells(b)[key];
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        const cmp = typeof x === 'number' && typeof y === 'number'
          ? x - y
          : String(x).localeCompare(String(y), 'fr');
        return asc ? cmp : -cmp;
      });
    }
    return rows.slice(0, this.limit());
  });

  protected sortBy(key: string): void {
    if (this.sortKey() === key) {
      this.ascending.update((v) => !v);
    } else {
      this.sortKey.set(key);
      this.ascending.set(false);
    }
  }

  protected arrow(key: string): string {
    if (this.sortKey() !== key) return '⇅';
    return this.ascending() ? '▲' : '▼';
  }

  protected field(row: TableRow, key: string): unknown {
    return cells(row)[key];
  }

  protected text(value: unknown): string {
    return value === null || value === undefined ? '' : String(value);
  }

  protected cell(row: TableRow, col: Column): string {
    const value = cells(row)[col.key];
    if (value === null || value === undefined) return 'n.d.';
    switch (col.type) {
      case 'money': return money(Number(value), this.symbol(), col.decimals ?? 0);
      case 'num': return num(Number(value), col.decimals ?? 0);
      case 'percent': return percent(Number(value));
      case 'date': return dateTime(String(value));
      default: return String(value);
    }
  }
}
