/* =====================================================================
   Composants d'interface, chaînes HTML assemblées puis injectées.
   Toute donnée externe passe par Fmt.esc().
   ===================================================================== */
(function (global) {
  'use strict';

  var DEPT_COLOR = {
    OVERVIEW: '--s7', SALES: '--s1', STOCK: '--s2',
    PURCH: '--s3', CRM: '--s5', HR: '--s4', FIN: '--s6'
  };

  function deptColor(code) { return 'var(' + (DEPT_COLOR[code] || '--ink-muted') + ')'; }

  /** Évolution : flèche + valeur, la couleur ne porte jamais seule l'information. */
  function delta(pct) {
    if (pct === null || pct === undefined) {
      return '<span class="delta flat">nouvelle période</span>';
    }
    var cls = Math.abs(pct) < 0.05 ? 'flat' : (pct > 0 ? 'up' : 'down');
    var arrow = Math.abs(pct) < 0.05 ? '→' : (pct > 0 ? '↑' : '↓');
    return '<span class="delta ' + cls + '">' + arrow + ' ' +
           Math.abs(pct).toFixed(1).replace('.', ',') + ' %</span>';
  }

  function kpi(label, value, foot, accent) {
    return '<div class="card kpi">' +
      '<span class="kpi-accent" style="background:' + (accent || 'var(--ink-muted)') + '"></span>' +
      '<div class="kpi-label">' + Fmt.esc(label) + '</div>' +
      '<div class="kpi-value">' + value + '</div>' +
      '<div class="kpi-foot">' + (foot || '') + '</div></div>';
  }

  function card(title, body, note, extraClass) {
    return '<section class="card ' + (extraClass || '') + '">' +
      '<h3 class="card-title">' + Fmt.esc(title) + '</h3>' +
      (note ? '<p class="card-note">' + Fmt.esc(note) + '</p>' : '<div style="height:8px"></div>') +
      body + '</section>';
  }

  /** Emplacement pour un graphique, rempli après insertion dans le DOM. */
  function chartSlot(id) { return '<div id="' + id + '"></div>'; }

  var STATUS = {
    rupture:  ['critical', '⛔', 'Rupture'],
    alerte:   ['serious',  '▲', 'À commander'],
    faible:   ['warning',  '•', 'Stock faible'],
    ok:       ['good',     '✓', 'Disponible']
  };

  function badge(status) {
    var spec = STATUS[status] || ['', '•', status];
    return '<span class="badge ' + spec[0] + '"><span class="badge-dot" style="background:var(--' +
      (spec[0] || 'ink-muted') + ')"></span>' + spec[1] + ' ' + Fmt.esc(spec[2]) + '</span>';
  }

  /**
   * Tableau triable, c'est aussi la « vue table » des graphiques.
   * columns : [{ key, label, type: 'text'|'num'|'money'|'badge', decimals, strong }]
   */
  var tableSeq = 0;
  function table(rows, columns, options) {
    var opts = options || {};
    var id = 'tbl-' + (++tableSeq);
    var limit = opts.limit || 12;
    if (!rows || !rows.length) {
      return '<div class="empty"><span class="mark">∅</span>' +
             Fmt.esc(opts.empty || 'Aucune ligne.') + '</div>';
    }
    var state = { rows: rows, columns: columns, opts: opts, sort: null, asc: false, limit: limit };
    TABLES[id] = state;
    return '<div class="table-wrap" id="' + id + '">' + renderTable(id) + '</div>';
  }

  var TABLES = {};

  function renderTable(id) {
    var state = TABLES[id];
    var rows = state.rows.slice();
    if (state.sort) {
      rows.sort(function (a, b) {
        var x = a[state.sort], y = b[state.sort];
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        var cmp = (typeof x === 'number' && typeof y === 'number')
          ? x - y : String(x).localeCompare(String(y), 'fr');
        return state.asc ? cmp : -cmp;
      });
    }
    var shown = rows.slice(0, state.limit);
    var head = state.columns.map(function (col) {
      var arrow = state.sort === col.key ? (state.asc ? '▲' : '▼') : '⇅';
      return '<th class="' + (col.type === 'text' || !col.type ? '' : 'num') +
        '" data-table="' + id + '" data-key="' + Fmt.esc(col.key) + '" tabindex="0">' +
        Fmt.esc(col.label) + '<span class="sort">' + arrow + '</span></th>';
    }).join('');

    var body = shown.map(function (row) {
      var cls = state.opts.rowClass ? state.opts.rowClass(row) : '';
      var cells = state.columns.map(function (col) {
        var value = row[col.key];
        if (col.type === 'badge') return '<td>' + badge(value) + '</td>';
        if (col.type === 'money') {
          return '<td class="num' + (col.strong ? ' strong' : '') + '">' +
                 Fmt.money(value, state.opts.symbol, col.decimals || 0) + '</td>';
        }
        if (col.type === 'num') {
          return '<td class="num">' + Fmt.number(value, col.decimals || 0) + '</td>';
        }
        if (col.type === 'percent') return '<td class="num">' + Fmt.percent(value) + '</td>';
        if (col.type === 'date') return '<td>' + Fmt.esc(Fmt.dateTime(value)) + '</td>';
        return '<td>' + Fmt.esc(value === null || value === undefined ? 'n.d.' : value) + '</td>';
      }).join('');
      return '<tr class="' + cls + '">' + cells + '</tr>';
    }).join('');

    var foot = state.rows.length > shown.length
      ? '<div class="table-foot">' + shown.length + ' lignes affichées sur ' +
        state.rows.length + ', cliquez sur un en-tête pour trier.</div>'
      : '<div class="table-foot">Cliquez sur un en-tête pour trier.</div>';
    return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>' + foot;
  }

  document.addEventListener('click', function (event) {
    var th = event.target.closest ? event.target.closest('th[data-table]') : null;
    if (!th) return;
    var id = th.getAttribute('data-table');
    var state = TABLES[id];
    if (!state) return;
    var key = th.getAttribute('data-key');
    state.asc = state.sort === key ? !state.asc : false;
    state.sort = key;
    var host = document.getElementById(id);
    if (host) host.innerHTML = renderTable(id);
  });

  function feed(rows, symbol) {
    var tags = { SALES: 'VENTE', PURCH: 'ACHAT', STOCK: 'STOCK', FIN: 'CHARGE' };
    return rows.map(function (row) {
      var label = String(row.label || '')
        .replace(/^Vente /, '').replace(/^Commande /, '').replace(/^Charge, /, '');
      var amount = row.dept === 'STOCK'
        ? (row.amount > 0 ? '+' : '') + Fmt.number(row.amount, 0) + ' u.'
        : Fmt.compact(row.amount, symbol);
      return '<div class="feed-row">' +
        '<span class="feed-tag" style="background:' + deptColor(row.dept) + '">' +
        (tags[row.dept] || row.dept) + '</span>' +
        '<span class="feed-label" title="' + Fmt.esc(row.label) + '">' + Fmt.esc(label) + '</span>' +
        '<span class="feed-amount">' + amount + '</span>' +
        '<span class="feed-time">' + Fmt.esc(Fmt.dateTime(row.at)) + '</span></div>';
    }).join('');
  }

  function pageHead(title, subtitle) {
    return '<header class="page-head"><h1 class="page-title">' + title +
      '</h1><p class="page-sub">' + Fmt.esc(subtitle) + '</p></header>';
  }

  function toast(message, isError) {
    var node = document.getElementById('toast');
    node.textContent = message;
    node.className = 'toast' + (isError ? ' error' : '');
    node.hidden = false;
    clearTimeout(node._timer);
    node._timer = setTimeout(function () { node.hidden = true; }, isError ? 7000 : 3500);
  }

  global.UI = {
    kpi: kpi, card: card, chartSlot: chartSlot, badge: badge, table: table,
    feed: feed, delta: delta, pageHead: pageHead, deptColor: deptColor,
    toast: toast, resetTables: function () { TABLES = {}; }
  };
}(window));
