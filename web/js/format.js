/* =====================================================================
   Formatage, français, sans dépendance.
   ===================================================================== */
(function (global) {
  'use strict';

  var MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
                'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

  /** 1234567 -> "1 234 567" */
  function number(value, decimals) {
    if (value === null || value === undefined || isNaN(value)) return 'n.d.';
    var d = decimals === undefined ? 0 : decimals;
    return Number(value).toFixed(d)
      .replace('.', ',')
      .replace(/\B(?=(\d{3})+(?!\d))/g, ' ');   // espace fine insécable
  }

  /** Montant complet : "1 234 567 FCFA" */
  function money(value, symbol, decimals) {
    if (value === null || value === undefined || isNaN(value)) return 'n.d.';
    return number(value, decimals || 0) + ' ' + (symbol || '');
  }

  /** Montant compact : "1,2 M FCFA", pour les tuiles et les axes. */
  function compact(value, symbol) {
    if (value === null || value === undefined || isNaN(value)) return 'n.d.';
    var a = Math.abs(value), sign = value < 0 ? '-' : '', sym = symbol ? ' ' + symbol : '';
    if (a >= 1e9) return sign + (a / 1e9).toFixed(1).replace('.', ',') + ' Md' + sym;
    if (a >= 1e6) return sign + (a / 1e6).toFixed(1).replace('.', ',') + ' M' + sym;
    if (a >= 1e3) return sign + (a / 1e3).toFixed(1).replace('.', ',') + ' k' + sym;
    return sign + number(a, 0) + sym;
  }

  /** Graduation d'axe : "12 k", "1,4 M" (sans devise, elle est dans le titre). */
  function axisTick(value) {
    var a = Math.abs(value), sign = value < 0 ? '-' : '';
    if (a >= 1e9) return sign + trim(a / 1e9) + ' Md';
    if (a >= 1e6) return sign + trim(a / 1e6) + ' M';
    if (a >= 1e3) return sign + trim(a / 1e3) + ' k';
    return sign + trim(a);
  }

  function trim(v) {
    var s = v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(v % 1 === 0 ? 0 : 1);
    return s.replace('.', ',').replace(/,0$/, '');
  }

  function percent(value, decimals) {
    if (value === null || value === undefined || isNaN(value)) return 'n.d.';
    return number(value * 100, decimals === undefined ? 1 : decimals) + ' %';
  }

  /** '2026-08-16' -> '16/08' */
  function day(iso) {
    if (!iso || iso.length < 10) return iso || '';
    return iso.slice(8, 10) + '/' + iso.slice(5, 7);
  }

  /** '2026-08' -> 'août 2026' */
  function period(iso) {
    if (!iso || iso.length < 7) return iso || '';
    var m = parseInt(iso.slice(5, 7), 10);
    return (MONTHS[m - 1] || iso.slice(5, 7)) + ' ' + iso.slice(0, 4);
  }

  /** '2026-08-16 20:48:12' -> '16/08 20:48' */
  function dateTime(iso) {
    if (!iso) return '';
    if (iso.length >= 16) return day(iso) + ' ' + iso.slice(11, 16);
    return day(iso);
  }

  /** Échappe le texte injecté en HTML. */
  function esc(text) {
    return String(text === null || text === undefined ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  global.Fmt = {
    number: number, money: money, compact: compact, axisTick: axisTick,
    percent: percent, day: day, period: period, dateTime: dateTime, esc: esc,
    MONTHS: MONTHS
  };
}(window));
