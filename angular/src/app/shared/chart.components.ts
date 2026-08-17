import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

import { axisTick, compact, money, seriesColor, seriesTint } from '../core/format';
import { EmptyComponent } from './ui.components';

/*
 * Graphiques SVG en Angular : la géométrie est calculée dans des `computed()`
 * et liée dans le gabarit, pas de manipulation impérative du DOM.
 * Mêmes règles que les autres interfaces : un seul axe de valeurs, marques
 * fines, extrémités arrondies, légende dès deux séries, survol par défaut.
 */

const WIDTH = 640;               // repère interne ; le viewBox rend le tout fluide

function niceMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  const n = value / exp;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * exp;
}

interface GridLine { y: number; label: string; }

/** Courbe d'évolution, avec curseur au survol. */
@Component({
  selector: 'erp-line-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyComponent],
  template: `
    @if (!x().length) {
      <erp-empty [message]="empty()" />
    } @else {
      @if (names().length > 1) {
        <div class="legend">
          @for (name of names(); track name; let i = $index) {
            <span class="legend-item">
              <span class="legend-swatch" [style.background]="color(i)"></span>{{ name }}
            </span>
          }
        </div>
      }
      <div class="plot" [style.height.px]="height() + 20">
      <svg class="chart" [attr.viewBox]="'0 0 ' + W + ' ' + height()"
           [style.height.px]="height()" preserveAspectRatio="none" role="img">
        @for (line of grid(); track line.y) {
          <line class="grid-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
                [attr.y1]="line.y" [attr.y2]="line.y" />
        }
        @for (path of paths(); track path.name) {
          @if (fill() && names().length === 1) {
            <path [attr.d]="path.area" [attr.fill]="path.tint" />
          }
          <path [attr.d]="path.line" fill="none" [attr.stroke]="path.color"
                stroke-width="2" stroke-linejoin="round" stroke-linecap="round"
                vector-effect="non-scaling-stroke" />
        }
        <line class="axis-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
              [attr.y1]="box().y + box().h" [attr.y2]="box().y + box().h" />
        @if (hover() !== null) {
          <line class="cursor" [attr.x1]="pointX(hover()!)" [attr.x2]="pointX(hover()!)"
                [attr.y1]="box().y" [attr.y2]="box().y + box().h" />
          @for (path of paths(); track path.name) {
            <circle [attr.cx]="pointX(hover()!)" [attr.cy]="pointY(path.values[hover()!])"
                    r="4.5" [attr.fill]="path.color" stroke="var(--chart)" stroke-width="2" />
          }
        }
        <rect class="hit" [attr.x]="box().x" [attr.y]="box().y"
              [attr.width]="box().w" [attr.height]="box().h"
              (mousemove)="onMove($event)" (mouseleave)="hover.set(null)" />
      </svg>
        @for (line of grid(); track line.y) {
          <span class="chart-ytick" [style.top.px]="line.y">{{ line.label }}</span>
        }
        @for (tick of xTicks(); track tick.i) {
          <span class="chart-xtick" [style.left.%]="tick.pct"
                [style.top.px]="axisY()">{{ tick.label }}</span>
        }
      </div>
      @if (hover() !== null) {
        <div class="chart-readout">
          <b>{{ x()[hover()!] }}</b>
          @for (path of paths(); track path.name; let i = $index) {
            <span class="legend-item">
              <span class="legend-swatch" [style.background]="path.color"></span>
              {{ path.name }} : <b>{{ display(path.values[hover()!]) }}</b>
            </span>
          }
        </div>
      }
    }
  `,
  styles: [`
    :host { display: block; }
    .plot { position: relative; }
    .chart-ytick {
      position: absolute; left: 0; width: 40px; text-align: right;
      transform: translateY(-50%);
      font-size: 11px; color: var(--ink-muted); font-variant-numeric: tabular-nums;
    }
    .chart-xtick {
      position: absolute; transform: translateX(-50%);
      font-size: 11px; color: var(--ink-muted); white-space: nowrap;
    }
    .chart-readout {
      display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
      margin-top: 4px; font-size: 12px; color: var(--ink-2);
    }
    .chart-readout b { color: var(--ink); }
  `],
})
export class LineChartComponent {
  readonly x = input.required<string[]>();
  readonly series = input.required<Record<string, number[]>>();
  readonly symbol = input<string>('');
  readonly height = input<number>(260);
  readonly fill = input<boolean>(false);
  readonly empty = input<string>('Aucune donnée sur la période.');

  protected readonly W = WIDTH;
  protected readonly hover = signal<number | null>(null);
  protected readonly names = computed(() => Object.keys(this.series()));

  protected readonly box = computed(() => ({
    x: 46, y: 10, w: WIDTH - 56, h: this.height() - 24,
  }));

  protected readonly max = computed(() => {
    const all = this.names().flatMap((n) => this.series()[n] ?? []);
    return niceMax(Math.max(0, ...all) * 1.08);
  });

  protected readonly grid = computed<GridLine[]>(() => {
    const b = this.box(); const max = this.max();
    return Array.from({ length: 6 }, (_, i) => ({
      y: b.y + b.h - (b.h * i) / 5,
      label: axisTick((max * i) / 5),
    }));
  });

  protected readonly paths = computed(() => {
    const b = this.box();
    return this.names().map((name, i) => {
      const values = this.series()[name] ?? [];
      const line = values
        .map((v, k) => `${k ? 'L' : 'M'}${this.pointX(k).toFixed(1)} ${this.pointY(v).toFixed(1)}`)
        .join(' ');
      const last = this.pointX(values.length - 1).toFixed(1);
      return {
        name, values, color: seriesColor(i), tint: seriesTint(i), line,
        area: `${line} L${last} ${b.y + b.h} L${b.x} ${b.y + b.h} Z`,
      };
    });
  });

  protected readonly xTicks = computed(() => {
    const labels = this.x();
    const every = Math.max(1, Math.ceil(labels.length / 8));
    return labels
      .map((label, i) => ({ i, label, pct: (i / Math.max(1, labels.length - 1)) * 100 }))
      .filter((t) => t.i % every === 0 || t.i === labels.length - 1);
  });

  /** Ordonnée de l'axe des abscisses, pour poser les étiquettes juste dessous. */
  protected axisY(): number { return this.box().y + this.box().h + 6; }

  protected color(index: number): string { return seriesColor(index); }

  protected pointX(index: number): number {
    const b = this.box();
    return b.x + (index * b.w) / Math.max(1, this.x().length - 1);
  }

  protected pointY(value: number): number {
    const b = this.box();
    return b.y + b.h - ((value || 0) / this.max()) * b.h;
  }

  protected display(value: number): string {
    return this.symbol() ? money(value, this.symbol()) : value.toLocaleString('fr-FR');
  }

  protected onMove(event: MouseEvent): void {
    const target = event.currentTarget as SVGRectElement;
    const rect = target.ownerSVGElement!.getBoundingClientRect();
    const b = this.box();
    const ratio = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const index = Math.round(((ratio - b.x) / b.w) * Math.max(1, this.x().length - 1));
    this.hover.set(Math.max(0, Math.min(this.x().length - 1, index)));
  }
}

/** Barres verticales, une série, une couleur, pas de légende. */
@Component({
  selector: 'erp-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyComponent],
  template: `
    @if (!labels().length) {
      <erp-empty [message]="empty()" />
    } @else {
      <div class="plot" [style.height.px]="height() + 20">
      <svg class="chart" [attr.viewBox]="'0 0 ' + W + ' ' + height()"
           [style.height.px]="height()" preserveAspectRatio="none" role="img">
        @for (line of grid(); track line.y) {
          <line class="grid-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
                [attr.y1]="line.y" [attr.y2]="line.y" />
        }
        @for (bar of bars(); track bar.label) {
          <rect [attr.x]="bar.x" [attr.y]="bar.y" [attr.width]="bar.w" [attr.height]="bar.h"
                rx="4" [attr.fill]="color()">
            <title>{{ bar.label }} : {{ bar.text }}</title>
          </rect>
        }
        <line class="axis-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
              [attr.y1]="box().y + box().h" [attr.y2]="box().y + box().h" />
      </svg>
        @for (line of grid(); track line.y) {
          <span class="chart-ytick" [style.top.px]="line.y">{{ line.label }}</span>
        }
        @for (bar of bars(); track bar.label) {
          <span class="chart-xtick" [style.left.%]="bar.centerPct"
                [style.top.px]="axisY()">{{ bar.label }}</span>
        }
      </div>
    }
  `,
  styles: [`
    :host { display: block; }
    .plot { position: relative; }
    .chart-ytick {
      position: absolute; left: 0; width: 40px; text-align: right;
      transform: translateY(-50%);
      font-size: 11px; color: var(--ink-muted); font-variant-numeric: tabular-nums;
    }
    .chart-xtick {
      position: absolute; transform: translateX(-50%);
      font-size: 11px; color: var(--ink-muted); white-space: nowrap;
    }
  `],
})
export class BarChartComponent {
  readonly labels = input.required<string[]>();
  readonly values = input.required<number[]>();
  readonly symbol = input<string>('');
  readonly height = input<number>(260);
  readonly color = input<string>(seriesColor(0));
  readonly empty = input<string>('Aucune donnée.');

  protected readonly W = WIDTH;
  protected readonly box = computed(() => ({ x: 46, y: 10, w: WIDTH - 56, h: this.height() - 30 }));
  protected readonly max = computed(() => niceMax(Math.max(0, ...this.values()) * 1.1));

  protected readonly grid = computed<GridLine[]>(() => {
    const b = this.box(); const max = this.max();
    return Array.from({ length: 5 }, (_, i) => ({
      y: b.y + b.h - (b.h * i) / 4, label: axisTick((max * i) / 4),
    }));
  });

  protected axisY(): number { return this.box().y + this.box().h + 6; }

  protected readonly bars = computed(() => {
    const b = this.box(); const labels = this.labels(); const max = this.max();
    const slot = b.w / Math.max(1, labels.length);
    const width = Math.min(46, slot * 0.62);
    return labels.map((label, i) => {
      const value = this.values()[i] ?? 0;
      const h = Math.max(2, (value / max) * b.h);
      return {
        label, x: b.x + slot * i + (slot - width) / 2, y: b.y + b.h - h, w: width, h,
        centerPct: ((b.x + slot * i + slot / 2) / WIDTH) * 100,
        text: this.symbol() ? money(value, this.symbol()) : `${value}`,
      };
    });
  });
}

/** Barres groupées ou empilées, plusieurs séries de MÊME unité. */
@Component({
  selector: 'erp-grouped-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyComponent],
  template: `
    @if (!x().length) {
      <erp-empty [message]="empty()" />
    } @else {
      <div class="legend">
        @for (name of names(); track name; let i = $index) {
          <span class="legend-item">
            <span class="legend-swatch" [style.background]="col(i)"></span>{{ name }}
          </span>
        }
      </div>
      <div class="plot" [style.height.px]="height() + 20">
      <svg class="chart" [attr.viewBox]="'0 0 ' + W + ' ' + height()"
           [style.height.px]="height()" preserveAspectRatio="none" role="img">
        @for (line of grid(); track line.y) {
          <line class="grid-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
                [attr.y1]="line.y" [attr.y2]="line.y" />
        }
        @for (bar of bars(); track bar.key) {
          <rect [attr.x]="bar.x" [attr.y]="bar.y" [attr.width]="bar.w" [attr.height]="bar.h"
                rx="4" [attr.fill]="bar.color">
            <title>{{ bar.group }}, {{ bar.name }} : {{ bar.text }}</title>
          </rect>
        }
        <line class="axis-line" [attr.x1]="box().x" [attr.x2]="box().x + box().w"
              [attr.y1]="box().y + box().h" [attr.y2]="box().y + box().h" />
      </svg>
        @for (line of grid(); track line.y) {
          <span class="chart-ytick" [style.top.px]="line.y">{{ line.label }}</span>
        }
        @for (tick of xTicks(); track tick.label) {
          <span class="chart-xtick" [style.left.%]="tick.pct"
                [style.top.px]="axisY()">{{ tick.label }}</span>
        }
      </div>
    }
  `,
  styles: [`
    :host { display: block; }
    .plot { position: relative; }
    .chart-ytick {
      position: absolute; left: 0; width: 40px; text-align: right;
      transform: translateY(-50%);
      font-size: 11px; color: var(--ink-muted); font-variant-numeric: tabular-nums;
    }
    .chart-xtick {
      position: absolute; transform: translateX(-50%);
      font-size: 11px; color: var(--ink-muted); white-space: nowrap;
    }
  `],
})
export class GroupedBarChartComponent {
  readonly x = input.required<string[]>();
  readonly series = input.required<Record<string, number[]>>();
  readonly symbol = input<string>('');
  readonly height = input<number>(290);
  readonly stacked = input<boolean>(false);
  readonly empty = input<string>('Aucune donnée.');

  protected readonly W = WIDTH;
  protected readonly names = computed(() => Object.keys(this.series()));
  protected readonly box = computed(() => ({ x: 46, y: 10, w: WIDTH - 56, h: this.height() - 30 }));

  protected readonly max = computed(() => {
    const names = this.names();
    if (this.stacked()) {
      const totals = this.x().map((_, i) =>
        names.reduce((sum, n) => sum + (this.series()[n]?.[i] ?? 0), 0));
      return niceMax(Math.max(0, ...totals) * 1.1);
    }
    return niceMax(Math.max(0, ...names.flatMap((n) => this.series()[n] ?? [])) * 1.1);
  });

  protected readonly grid = computed<GridLine[]>(() => {
    const b = this.box(); const max = this.max();
    return Array.from({ length: 5 }, (_, i) => ({
      y: b.y + b.h - (b.h * i) / 4, label: axisTick((max * i) / 4),
    }));
  });

  protected readonly bars = computed(() => {
    const b = this.box(); const names = this.names(); const max = this.max();
    const slot = b.w / Math.max(1, this.x().length);
    const groupW = slot * 0.72;
    const barW = this.stacked() ? Math.min(40, groupW) : groupW / Math.max(1, names.length);
    const out: {
      key: string; group: string; name: string; color: string; text: string;
      x: number; y: number; w: number; h: number;
    }[] = [];

    this.x().forEach((group, i) => {
      let offset = b.y + b.h;
      names.forEach((name, s) => {
        const value = this.series()[name]?.[i] ?? 0;
        const h = Math.max(2, (value / max) * b.h);
        const bx = this.stacked()
          ? b.x + slot * i + (slot - barW) / 2
          : b.x + slot * i + (slot - groupW) / 2 + s * barW;
        const by = this.stacked() ? offset - h : b.y + b.h - h;
        if (this.stacked()) offset -= h + 2;           // 2 px de respiration
        out.push({
          key: `${group}-${name}`, group, name, color: seriesColor(s),
          x: bx, y: by, w: this.stacked() ? barW : Math.max(2, barW - 2), h,
          text: this.symbol() ? money(value, this.symbol()) : `${value}`,
        });
      });
    });
    return out;
  });

  protected readonly xTicks = computed(() => {
    const b = this.box();
    const slot = b.w / Math.max(1, this.x().length);
    const every = Math.max(1, Math.ceil(this.x().length / 12));
    return this.x()
      .map((label, i) => ({ label, i, pct: ((b.x + slot * i + slot / 2) / WIDTH) * 100 }))
      .filter((t) => t.i % every === 0);
  });

  protected axisY(): number { return this.box().y + this.box().h + 6; }

  protected col(index: number): string { return seriesColor(index); }
}

/** Répartition : barres horizontales triées + part en pourcentage. */
@Component({
  selector: 'erp-share-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyComponent],
  template: `
    @if (!labels().length) {
      <erp-empty [message]="empty()" />
    } @else {
      <div class="share">
        @for (row of rows(); track row.label) {
          <div class="share-row" [title]="row.label + ' : ' + row.value">
            <span class="share-label">{{ row.label }}</span>
            <span class="share-track">
              <span class="share-fill" [style.width.%]="row.pct"
                    [style.background]="row.color"></span>
            </span>
            <span class="share-value">{{ row.value }} · {{ row.share }} %</span>
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .share { display: flex; flex-direction: column; gap: 10px; }
    .share-row { display: grid; grid-template-columns: minmax(70px, 1fr) 2fr auto; gap: 10px; align-items: center; }
    .share-label {
      font-size: 12.5px; color: var(--ink-2); text-align: right;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .share-track { height: 18px; background: var(--grid); border-radius: 4px; overflow: hidden; }
    .share-fill { display: block; height: 100%; border-radius: 4px; min-width: 3px; }
    .share-value {
      font-size: 12px; color: var(--ink-2); white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
  `],
})
export class ShareChartComponent {
  readonly labels = input.required<string[]>();
  readonly values = input.required<number[]>();
  readonly symbol = input<string>('');
  readonly empty = input<string>('Aucune donnée.');

  protected readonly rows = computed(() => {
    const values = this.values();
    const total = values.reduce((a, b) => a + b, 0) || 1;
    const max = Math.max(1, ...values);
    return this.labels().map((label, i) => ({
      label, color: seriesColor(i),
      pct: ((values[i] ?? 0) / max) * 100,
      share: Math.round(((values[i] ?? 0) / total) * 100),
      value: compact(values[i] ?? 0, this.symbol()),
    }));
  });
}

export const CHART_COMPONENTS = [
  LineChartComponent, BarChartComponent, GroupedBarChartComponent, ShareChartComponent,
] as const;
