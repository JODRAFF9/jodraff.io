/* =====================================================================
   Graphiques SVG écrits à la main, aucune bibliothèque, aucun CDN.
   Mêmes règles que les dashboards Python et R :
     * un seul axe de valeurs (jamais deux échelles Y) ;
     * marques fines, extrémités arrondies, 2 px entre segments empilés ;
     * légende dès deux séries, étiquettes directes sélectives ;
     * survol actif partout (curseur unifié sur les courbes).
   ===================================================================== */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var SERIES = ['--s1', '--s2', '--s3', '--s4', '--s5', '--s6', '--s7', '--s8'];

  /** Couleur de série : ordre FIXE, jamais recyclé entre deux rendus. */
  function color(index) {
    return 'var(' + SERIES[index % SERIES.length] + ')';
  }

  function el(tag, attrs, parent) {
    var node = document.createElementNS(NS, tag);
    for (var key in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, key) && attrs[key] !== null) {
        node.setAttribute(key, attrs[key]);
      }
    }
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceMax(value) {
    if (!isFinite(value) || value <= 0) return 1;
    var exp = Math.pow(10, Math.floor(Math.log10(value)));
    var normalized = value / exp;
    var step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5
             : normalized <= 5 ? 5 : 10;
    return step * exp;
  }

  /* ------------------------------------------------------------ tooltip */
  var tip = null;
  function showTip(html, event) {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'tooltip';
      document.body.appendChild(tip);
    }
    tip.innerHTML = html;
    tip.hidden = false;
    var box = tip.getBoundingClientRect();
    var x = Math.min(event.clientX + 14, window.innerWidth - box.width - 10);
    var y = Math.max(event.clientY - box.height - 12, 8);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  function hideTip() { if (tip) tip.hidden = true; }

  function swatch(index) {
    return '<span class="legend-swatch" style="background:' + color(index) + '"></span>';
  }

  /* ------------------------------------------------------------- socle */
  function frame(host, options) {
    host.innerHTML = '';
    var width = Math.max(260, host.clientWidth || 520);
    var height = options.height || 280;
    var names = Object.keys(options.series || {});

    if (names.length > 1) {                     // légende dès deux séries
      var legend = document.createElement('div');
      legend.className = 'legend';
      legend.innerHTML = names.map(function (name, i) {
        return '<span class="legend-item">' + swatch(i) + Fmt.esc(name) + '</span>';
      }).join('');
      host.appendChild(legend);
      height -= 22;
    }
    var svg = el('svg', {
      class: 'chart', width: width, height: height,
      viewBox: '0 0 ' + width + ' ' + height, role: 'img'
    }, host);
    if (options.title) el('title', {}, svg).textContent = options.title;
    return { svg: svg, w: width, h: height, names: names };
  }

  function yAxis(svg, box, max, min) {
    var lo = min || 0, ticks = 5, out = [];
    for (var i = 0; i <= ticks; i++) {
      var value = lo + (max - lo) * i / ticks;
      var y = box.y + box.h - (value - lo) / (max - lo || 1) * box.h;
      el('line', { class: 'grid-line', x1: box.x, x2: box.x + box.w, y1: y, y2: y }, svg);
      var text = el('text', { class: 'tick', x: box.x - 8, y: y + 4, 'text-anchor': 'end' }, svg);
      text.textContent = Fmt.axisTick(value);
      out.push(y);
    }
    return out;
  }

  function emptyState(host, message) {
    host.innerHTML = '<div class="empty"><span class="mark">∅</span>' + Fmt.esc(message) + '</div>';
  }

  /* ======================================================== courbes ==== */
  function line(host, options) {
    var x = options.x || [];
    if (!x.length) return emptyState(host, options.empty || 'Aucune donnée sur la période.');

    var f = frame(host, options);
    var box = { x: 58, y: 12, w: f.w - 74, h: f.h - 42 };
    var all = [];
    f.names.forEach(function (n) { all = all.concat(options.series[n]); });
    var max = niceMax(Math.max.apply(null, all.concat([0])) * 1.08);
    yAxis(f.svg, box, max);

    var stepX = box.w / Math.max(1, x.length - 1);
    var pointX = function (i) { return box.x + i * stepX; };
    var pointY = function (v) { return box.y + box.h - (v || 0) / max * box.h; };

    f.names.forEach(function (name, s) {
      var values = options.series[name];
      var d = values.map(function (v, i) {
        return (i ? 'L' : 'M') + pointX(i).toFixed(1) + ' ' + pointY(v).toFixed(1);
      }).join(' ');
      if (options.fill && f.names.length === 1) {
        el('path', {
          d: d + ' L' + pointX(values.length - 1).toFixed(1) + ' ' + (box.y + box.h) +
             ' L' + box.x + ' ' + (box.y + box.h) + ' Z',
          fill: color(s), 'fill-opacity': .10, stroke: 'none'
        }, f.svg);
      }
      el('path', {
        d: d, fill: 'none', stroke: color(s), 'stroke-width': 2,
        'stroke-linejoin': 'round', 'stroke-linecap': 'round'
      }, f.svg);
    });

    // axe des abscisses : au plus 8 étiquettes pour éviter les collisions
    var every = Math.max(1, Math.ceil(x.length / 8));
    x.forEach(function (label, i) {
      if (i % every && i !== x.length - 1) return;
      var text = el('text', {
        class: 'tick', x: pointX(i), y: box.y + box.h + 18, 'text-anchor': 'middle'
      }, f.svg);
      text.textContent = label;
    });
    el('line', {
      class: 'axis-line', x1: box.x, x2: box.x + box.w,
      y1: box.y + box.h, y2: box.y + box.h
    }, f.svg);

    // curseur unifié
    var cursor = el('line', {
      class: 'cursor', y1: box.y, y2: box.y + box.h, x1: 0, x2: 0, opacity: 0
    }, f.svg);
    var dots = f.names.map(function (name, s) {
      return el('circle', {
        r: 4.5, fill: color(s), stroke: 'var(--chart)', 'stroke-width': 2, opacity: 0
      }, f.svg);
    });
    var hit = el('rect', { class: 'hit', x: box.x, y: box.y, width: box.w, height: box.h }, f.svg);

    hit.addEventListener('mousemove', function (event) {
      var rect = f.svg.getBoundingClientRect();
      var i = Math.round((event.clientX - rect.left - box.x) / stepX);
      i = Math.max(0, Math.min(x.length - 1, i));
      cursor.setAttribute('x1', pointX(i));
      cursor.setAttribute('x2', pointX(i));
      cursor.setAttribute('opacity', 1);
      var rows = f.names.map(function (name, s) {
        dots[s].setAttribute('cx', pointX(i));
        dots[s].setAttribute('cy', pointY(options.series[name][i]));
        dots[s].setAttribute('opacity', 1);
        return '<div class="row">' + swatch(s) + Fmt.esc(name) + ' : <b style="display:inline">' +
               (options.symbol ? Fmt.money(options.series[name][i], options.symbol)
                               : Fmt.number(options.series[name][i])) + '</b></div>';
      }).join('');
      showTip('<b>' + Fmt.esc(options.xLabels ? options.xLabels[i] : x[i]) + '</b>' + rows, event);
    });
    hit.addEventListener('mouseleave', function () {
      cursor.setAttribute('opacity', 0);
      dots.forEach(function (d) { d.setAttribute('opacity', 0); });
      hideTip();
    });
  }

  /* ==================================================== barres verticales */
  function bars(host, options) {
    var labels = options.labels || [];
    if (!labels.length) return emptyState(host, options.empty || 'Aucune donnée.');

    var f = frame(host, options);
    var box = { x: 58, y: 12, w: f.w - 74, h: f.h - 44 };
    var max = niceMax(Math.max.apply(null, options.values.concat([0])) * 1.1);
    yAxis(f.svg, box, max);

    var slot = box.w / labels.length;
    var barW = Math.min(46, slot * .62);
    labels.forEach(function (label, i) {
      var value = options.values[i] || 0;
      var height = value / max * box.h;
      var x = box.x + slot * i + (slot - barW) / 2;
      var y = box.y + box.h - height;
      var rect = el('rect', {
        x: x, y: y, width: barW, height: Math.max(2, height), rx: 4,
        fill: options.color || color(0)
      }, f.svg);
      rect.addEventListener('mousemove', function (event) {
        showTip('<b>' + Fmt.esc(label) + '</b>' +
          (options.symbol ? Fmt.money(value, options.symbol) : Fmt.number(value)), event);
      });
      rect.addEventListener('mouseleave', hideTip);

      var text = el('text', {
        class: 'tick', x: box.x + slot * i + slot / 2,
        y: box.y + box.h + 18, 'text-anchor': 'middle'
      }, f.svg);
      text.textContent = label;
    });
    el('line', {
      class: 'axis-line', x1: box.x, x2: box.x + box.w,
      y1: box.y + box.h, y2: box.y + box.h
    }, f.svg);
  }

  /* ============================================ barres groupées/empilées */
  function groupedBars(host, options) {
    var x = options.x || [];
    if (!x.length) return emptyState(host, options.empty || 'Aucune donnée.');

    var f = frame(host, options);
    var box = { x: 58, y: 12, w: f.w - 74, h: f.h - 44 };
    var stacked = !!options.stacked;
    var totals = x.map(function (_, i) {
      return f.names.reduce(function (sum, n) { return sum + (options.series[n][i] || 0); }, 0);
    });
    var flat = [];
    f.names.forEach(function (n) { flat = flat.concat(options.series[n]); });
    var max = niceMax((stacked ? Math.max.apply(null, totals) : Math.max.apply(null, flat)) * 1.1);
    yAxis(f.svg, box, max);

    var slot = box.w / x.length;
    var groupW = slot * .72;
    var barW = stacked ? Math.min(40, groupW) : groupW / f.names.length;

    x.forEach(function (label, i) {
      var offsetY = box.y + box.h;
      f.names.forEach(function (name, s) {
        var value = options.series[name][i] || 0;
        var height = value / max * box.h;
        var bx = stacked
          ? box.x + slot * i + (slot - barW) / 2
          : box.x + slot * i + (slot - groupW) / 2 + s * barW;
        var by = stacked ? (offsetY - height) : (box.y + box.h - height);
        if (stacked) offsetY -= height + 2;         // 2 px de respiration
        var rect = el('rect', {
          x: bx, y: by, width: stacked ? barW : Math.max(2, barW - 2),
          height: Math.max(2, height), rx: 4, fill: color(s)
        }, f.svg);
        rect.addEventListener('mousemove', function (event) {
          showTip('<b>' + Fmt.esc(label) + '</b><div class="row">' + swatch(s) +
            Fmt.esc(name) + ' : <b style="display:inline">' +
            (options.symbol ? Fmt.money(value, options.symbol) : Fmt.number(value)) +
            '</b></div>', event);
        });
        rect.addEventListener('mouseleave', hideTip);
      });
      var text = el('text', {
        class: 'tick', x: box.x + slot * i + slot / 2,
        y: box.y + box.h + 18, 'text-anchor': 'middle'
      }, f.svg);
      text.textContent = label;
    });
    el('line', {
      class: 'axis-line', x1: box.x, x2: box.x + box.w,
      y1: box.y + box.h, y2: box.y + box.h
    }, f.svg);
  }

  /* ============================================ répartition (horizontal) */
  function shareBars(host, options) {
    var labels = options.labels || [];
    if (!labels.length) return emptyState(host, options.empty || 'Aucune donnée.');

    var rowH = 34;
    var height = labels.length * rowH + 16;
    host.innerHTML = '';
    var width = Math.max(260, host.clientWidth || 460);
    var svg = el('svg', {
      class: 'chart', width: width, height: height, viewBox: '0 0 ' + width + ' ' + height
    }, host);

    var labelW = Math.min(150, Math.max.apply(null, labels.map(function (l) {
      return l.length * 6.6;
    })) + 10);
    var total = options.values.reduce(function (a, b) { return a + b; }, 0) || 1;
    var max = Math.max.apply(null, options.values) || 1;
    var trackW = width - labelW - 108;

    labels.forEach(function (label, i) {
      var value = options.values[i] || 0;
      var y = 8 + i * rowH;
      var text = el('text', {
        class: 'value-label', x: labelW - 10, y: y + 18, 'text-anchor': 'end'
      }, svg);
      text.textContent = label.length > 22 ? label.slice(0, 21) + '…' : label;

      el('rect', {
        x: labelW, y: y + 5, width: trackW, height: 18, rx: 4,
        fill: 'var(--grid)', opacity: .5
      }, svg);
      var w = Math.max(3, value / max * trackW);
      var rect = el('rect', {
        x: labelW, y: y + 5, width: w, height: 18, rx: 4, fill: color(i)
      }, svg);

      var right = el('text', {
        class: 'value-label', x: labelW + trackW + 8, y: y + 18
      }, svg);
      right.textContent = Fmt.compact(value, options.symbol) + '  ·  ' +
                          Math.round(value / total * 100) + ' %';

      rect.addEventListener('mousemove', function (event) {
        showTip('<b>' + Fmt.esc(label) + '</b>' + Fmt.money(value, options.symbol) +
                '<br>' + Math.round(value / total * 100) + ' % du total', event);
      });
      rect.addEventListener('mouseleave', hideTip);
    });
  }

  /* ============================================================ haltères */
  function dumbbell(host, options) {
    var labels = options.labels || [];
    if (!labels.length) return emptyState(host, options.empty || 'Aucune donnée.');

    var rowH = 36;
    var height = labels.length * rowH + 34;
    host.innerHTML = '';
    var legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = '<span class="legend-item">' + swatch(0) + Fmt.esc(options.leftName) +
      '</span><span class="legend-item">' + swatch(2) + Fmt.esc(options.rightName) + '</span>';
    host.appendChild(legend);

    var width = Math.max(280, host.clientWidth || 460);
    var svg = el('svg', { class: 'chart', width: width, height: height,
                          viewBox: '0 0 ' + width + ' ' + height }, host);
    var labelW = Math.min(150, Math.max.apply(null, labels.map(function (l) {
      return l.length * 6.6;
    })) + 10);
    var trackW = width - labelW - 26;
    var max = niceMax(Math.max.apply(null, options.left.concat(options.right)) * 1.05);
    var scale = function (v) { return labelW + (v || 0) / max * trackW; };

    labels.forEach(function (label, i) {
      var y = 12 + i * rowH + 10;
      var text = el('text', { class: 'value-label', x: labelW - 10, y: y + 4, 'text-anchor': 'end' }, svg);
      text.textContent = label.length > 22 ? label.slice(0, 21) + '…' : label;
      el('line', {
        x1: scale(options.left[i]), x2: scale(options.right[i]), y1: y, y2: y,
        stroke: 'var(--axis)', 'stroke-width': 2
      }, svg);
      [[options.left[i], 0, options.leftName], [options.right[i], 2, options.rightName]]
        .forEach(function (pair) {
          var dot = el('circle', {
            cx: scale(pair[0]), cy: y, r: 5.5, fill: color(pair[1]),
            stroke: 'var(--chart)', 'stroke-width': 2
          }, svg);
          dot.addEventListener('mousemove', function (event) {
            showTip('<b>' + Fmt.esc(label) + '</b>' + Fmt.esc(pair[2]) + ' : ' +
                    Fmt.money(pair[0], options.symbol), event);
          });
          dot.addEventListener('mouseleave', hideTip);
        });
    });
  }

  /* ------------------------------------------------- rendu responsive --- */
  var registry = [];
  function render(host, kind, options) {
    if (!host) return;
    registry = registry.filter(function (entry) { return document.body.contains(entry.host); });
    registry.push({ host: host, kind: kind, options: options });
    Charts[kind](host, options);
  }

  var resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      registry.forEach(function (entry) {
        if (document.body.contains(entry.host)) Charts[entry.kind](entry.host, entry.options);
      });
    }, 180);
  });

  var Charts = {
    line: line, bars: bars, groupedBars: groupedBars,
    shareBars: shareBars, dumbbell: dumbbell,
    color: color, render: render, hideTip: hideTip,
    reset: function () { registry = []; hideTip(); }
  };
  global.Charts = Charts;
}(window));
