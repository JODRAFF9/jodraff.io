/**
 * Formatage français et jetons de couleur.
 * Repris à l'identique du front HTML/CSS/JS afin que les deux applications
 * affichent rigoureusement les mêmes libellés pour les mêmes données.
 */

const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
                'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

export function num(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(decimals).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

export function money(value: number | null | undefined, symbol: string, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${num(value, decimals)} ${symbol}`;
}

/** Format compact des tuiles et des axes : « 1,2 M FCFA ». */
export function compact(value: number | null | undefined, symbol = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  const suffix = symbol ? ` ${symbol}` : '';
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1).replace('.', ',')} Md${suffix}`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(1).replace('.', ',')} M${suffix}`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(1).replace('.', ',')} k${suffix}`;
  return `${sign}${num(abs)}${suffix}`;
}

/** Graduation d'axe, sans devise (elle figure dans le titre de la carte). */
export function axisTick(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  const trim = (v: number): string =>
    (v >= 100 ? v.toFixed(0) : v.toFixed(v % 1 === 0 ? 0 : 1)).replace('.', ',');
  if (abs >= 1e9) return `${sign}${trim(abs / 1e9)} Md`;
  if (abs >= 1e6) return `${sign}${trim(abs / 1e6)} M`;
  if (abs >= 1e3) return `${sign}${trim(abs / 1e3)} k`;
  return `${sign}${trim(abs)}`;
}

export function percent(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${num(value * 100, decimals)} %`;
}

/** '2026-08-16' -> '16/08' */
export function shortDay(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return iso ?? '';
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/** '2026-08' -> 'août 2026' */
export function periodLabel(iso: string | null | undefined): string {
  if (!iso || iso.length < 7) return iso ?? '';
  const month = Number.parseInt(iso.slice(5, 7), 10);
  return `${MONTHS[month - 1] ?? iso.slice(5, 7)} ${iso.slice(0, 4)}`;
}

/** '2026-08-16 20:48:12' -> '16/08 20:48' */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return iso.length >= 16 ? `${shortDay(iso)} ${iso.slice(11, 16)}` : shortDay(iso);
}

/** Couleur de série : ordre FIXE, jamais recyclé quand un filtre change. */
export function seriesColor(index: number): string {
  return `var(--s${(index % 8) + 1})`;
}

export const DEPT_COLOR: Record<string, string> = {
  OVERVIEW: 'var(--s7)', SALES: 'var(--s1)', STOCK: 'var(--s2)',
  PURCH: 'var(--s3)', CRM: 'var(--s5)', HR: 'var(--s4)', FIN: 'var(--s6)',
};

export function deptColor(code: string): string {
  return DEPT_COLOR[code] ?? 'var(--ink-muted)';
}

/** Statut de stock -> classe CSS, icône et libellé (jamais la couleur seule). */
export const STOCK_STATUS: Record<string, { cls: string; icon: string; label: string }> = {
  rupture: { cls: 'critical', icon: '⛔', label: 'Rupture' },
  alerte: { cls: 'serious', icon: '▲', label: 'À commander' },
  faible: { cls: 'warning', icon: '•', label: 'Stock faible' },
  ok: { cls: 'good', icon: '✓', label: 'Disponible' },
};

/** Évolution période sur période : flèche + valeur absolue + sens. */
export function deltaParts(pct: number | null | undefined):
    { cls: string; arrow: string; text: string } {
  if (pct === null || pct === undefined) {
    return { cls: 'flat', arrow: '—', text: 'nouvelle période' };
  }
  const flat = Math.abs(pct) < 0.05;
  return {
    cls: flat ? 'flat' : pct > 0 ? 'up' : 'down',
    arrow: flat ? '→' : pct > 0 ? '↑' : '↓',
    text: `${Math.abs(pct).toFixed(1).replace('.', ',')} %`,
  };
}
