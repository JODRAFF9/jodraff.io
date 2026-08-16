/* =====================================================================
   Une vue par département. Chaque vue :
     1. retourne le HTML de la page ;
     2. dessine ensuite ses graphiques dans les emplacements réservés.
   ===================================================================== */
(function (global) {
  'use strict';

  function money(v, sym) { return Fmt.compact(v, sym); }

  /* ===================================================== VUE D'ENSEMBLE */
  function overview(data, days) {
    var sym = data.company.currency_sym, k = data.kpis;
    var html =
      UI.pageHead(Fmt.esc(data.company.logo_emoji) + '&nbsp; ' + Fmt.esc(data.company.name),
        data.company.store_label + ' — ' + data.company.city + ', ' + data.company.country +
        '. Toutes les cartes sont calculées en direct sur la base SQL centrale.') +

      '<div class="grid grid-kpi">' +
        UI.kpi("Chiffre d'affaires", money(k.revenue, sym),
               UI.delta(k.revenue_delta) + ' sur ' + days + ' j', UI.deptColor('SALES')) +
        UI.kpi('Marge brute', money(k.margin, sym),
               UI.delta(k.margin_delta) + ' taux ' + Fmt.percent(k.margin_rate),
               UI.deptColor('FIN')) +
        UI.kpi('Tickets', Fmt.number(k.tickets),
               UI.delta(k.tickets_delta) + ' ' + k.customers + ' clients identifiés',
               UI.deptColor('CRM')) +
        UI.kpi('Panier moyen', money(k.avg_basket, sym),
               UI.delta(k.avg_basket_delta) + ' par ticket', UI.deptColor('SALES')) +
        UI.kpi('Valeur du stock', money(k.stock_value, sym),
               '⛔ ' + k.out_of_stock + ' rupture(s) · ▲ ' + k.stock_alerts + ' à commander',
               UI.deptColor('STOCK')) +
        UI.kpi('Résultat du mois', money(k.net_result, sym),
               'masse salariale ' + money(k.payroll, sym), UI.deptColor('HR')) +
      '</div>' +

      '<div class="mt">' + UI.card('Départements connectés à la base centrale',
        '<div class="dept-strip">' + data.departments.map(function (d) {
          return '<span class="dept-chip"><span class="dept-dot" style="background:' +
            UI.deptColor(d.dept) + '"></span><b>' + Fmt.esc(d.name) + '</b> · ' +
            Fmt.number(d.count) + ' ' + Fmt.esc(d.count_label) + '</span>';
        }).join('') + '</div>' +
        '<div class="summary-grid" style="margin-top:12px">' + data.departments.map(function (d) {
          return '<div class="summary-item" style="border-left-color:' + UI.deptColor(d.dept) + '">' +
            '<div class="k">' + Fmt.esc(d.metric) + '</div><div class="v">' +
            (d.dept === 'CRM' ? Fmt.number(d.value) : money(d.value, sym)) + '</div></div>';
        }).join('') + '</div>',
        "Une écriture faite dans un département met immédiatement à jour les indicateurs " +
        "des autres — c'est le rôle des triggers SQL.") + '</div>' +

      '<div class="grid grid-3 mt">' +
        UI.card("Chiffre d'affaires quotidien", UI.chartSlot('c-daily'),
                'Source : département Ventes. Survolez la courbe pour le détail.', 'span-2') +
        UI.card('Répartition par rayon', UI.chartSlot('c-cat'),
                "Chiffre d'affaires HT des " + days + ' derniers jours.') +
      '</div>' +

      '<div class="grid grid-3 mt">' +
        UI.card("Chiffre d'affaires et marge par mois", UI.chartSlot('c-monthly'),
                "Deux mesures de même unité, donc un seul axe de valeurs.", 'span-2') +
        UI.card('Dernières écritures', UI.feed(data.activity, sym),
                'Ventes, achats, mouvements de stock et charges, tous départements.') +
      '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-daily'), 'line', {
        x: data.sales_daily.map(function (r) { return Fmt.day(r.sale_date); }),
        xLabels: data.sales_daily.map(function (r) { return r.sale_date; }),
        series: { 'CA TTC': data.sales_daily.map(function (r) { return r.revenue; }) },
        symbol: sym, height: 280, fill: true
      });
      Charts.render(document.getElementById('c-cat'), 'shareBars', {
        labels: data.sales_by_category.map(function (r) { return r.category; }),
        values: data.sales_by_category.map(function (r) { return r.revenue; }),
        symbol: sym
      });
      Charts.render(document.getElementById('c-monthly'), 'groupedBars', {
        x: data.sales_monthly.map(function (r) { return Fmt.period(r.period); }),
        series: {
          'CA HT': data.sales_monthly.map(function (r) { return r.revenue_ht; }),
          'Marge brute': data.sales_monthly.map(function (r) { return r.gross_margin; })
        },
        symbol: sym, height: 300
      });
    }};
  }

  /* ============================================================= VENTES */
  function sales(data, days, company) {
    var sym = company.currency_sym, k = data.kpis;
    var html =
      UI.pageHead('🧾&nbsp; Ventes',
        'Chaque ticket enregistré décharge le stock, alimente la fiche client et le ' +
        'compte de résultat — sans aucune ressaisie.') +
      '<div class="grid grid-4">' +
        UI.kpi("Chiffre d'affaires", money(k.revenue, sym),
               UI.delta(k.revenue_delta) + ' sur ' + days + ' j', UI.deptColor('SALES')) +
        UI.kpi('Tickets', Fmt.number(k.tickets), UI.delta(k.tickets_delta), UI.deptColor('SALES')) +
        UI.kpi('Panier moyen', money(k.avg_basket, sym), UI.delta(k.avg_basket_delta),
               UI.deptColor('SALES')) +
        UI.kpi('Marge brute', money(k.margin, sym), 'taux ' + Fmt.percent(k.margin_rate),
               UI.deptColor('FIN')) +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card("Chiffre d'affaires et tickets", UI.chartSlot('c-s-rev') + UI.chartSlot('c-s-tickets'),
                'Deux unités différentes : deux graphiques superposés, jamais un second axe Y.',
                'span-2') +
        UI.card('Modes de paiement', UI.chartSlot('c-s-pay'), '') +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Ventes par heure', UI.chartSlot('c-s-hour'),
                "Nombre de tickets — utile pour caler les plannings.", 'span-2') +
        UI.card('Canaux de vente', UI.chartSlot('c-s-chan'), '') +
      '</div>' +
      '<div class="grid grid-2 mt">' +
        UI.card('Top 10 des produits', UI.table(data.top_products, [
          { key: 'product', label: 'Produit' },
          { key: 'category', label: 'Rayon' },
          { key: 'qty_sold', label: 'Quantité', type: 'num' },
          { key: 'revenue_ht', label: 'CA HT', type: 'money', strong: true },
          { key: 'margin', label: 'Marge', type: 'money' }
        ], { symbol: sym, limit: 10 }), 'Classement par chiffre d\'affaires hors taxes.') +
        UI.card('Journal des ventes', UI.table(data.recent, [
          { key: 'ref', label: 'Référence' },
          { key: 'sold_at', label: 'Date', type: 'date' },
          { key: 'customer', label: 'Client' },
          { key: 'seller', label: 'Vendeur' },
          { key: 'payment_method', label: 'Paiement' },
          { key: 'total', label: 'Total', type: 'money', strong: true }
        ], { symbol: sym, limit: 12,
             rowClass: function (r) { return r.status === 'annulée' ? 'row-critical' : ''; } }),
          'Les tickets annulés apparaissent en rouge.') +
      '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-s-rev'), 'line', {
        x: data.daily.map(function (r) { return Fmt.day(r.sale_date); }),
        xLabels: data.daily.map(function (r) { return r.sale_date; }),
        series: { 'CA TTC': data.daily.map(function (r) { return r.revenue; }) },
        symbol: sym, height: 220, fill: true
      });
      Charts.render(document.getElementById('c-s-tickets'), 'line', {
        x: data.daily.map(function (r) { return Fmt.day(r.sale_date); }),
        series: { 'Tickets': data.daily.map(function (r) { return r.tickets; }) },
        height: 150
      });
      Charts.render(document.getElementById('c-s-pay'), 'shareBars', {
        labels: data.by_payment.map(function (r) { return r.label; }),
        values: data.by_payment.map(function (r) { return r.revenue; }), symbol: sym
      });
      Charts.render(document.getElementById('c-s-hour'), 'bars', {
        labels: data.by_hour.map(function (r) { return r.label + ' h'; }),
        values: data.by_hour.map(function (r) { return r.tickets; }),
        height: 260, color: Charts.color(0)
      });
      Charts.render(document.getElementById('c-s-chan'), 'shareBars', {
        labels: data.by_channel.map(function (r) { return r.label; }),
        values: data.by_channel.map(function (r) { return r.revenue; }), symbol: sym
      });
    }};
  }

  /* ============================================================== STOCK */
  function stock(data, days, company) {
    var sym = company.currency_sym;
    var totalValue = data.valuation.reduce(function (a, r) { return a + (r.value || 0); }, 0);
    var retail = data.valuation.reduce(function (a, r) { return a + (r.retail_value || 0); }, 0);
    var out = data.products.filter(function (p) { return p.stock_status === 'rupture'; }).length;

    var html =
      UI.pageHead('📦&nbsp; Stock',
        "Le stock n'est jamais saisi à la main : il résulte des ventes, des réceptions " +
        "fournisseurs et des écritures d'inventaire.") +
      '<div class="grid grid-kpi">' +
        UI.kpi('Valeur du stock', money(totalValue, sym),
               'au prix de revient · ' + data.products.length + ' références', UI.deptColor('STOCK')) +
        UI.kpi('Valeur au prix de vente', money(retail, sym),
               'marge potentielle ' + money(retail - totalValue, sym), UI.deptColor('FIN')) +
        UI.kpi('Ruptures', String(out), '⛔ vente impossible', 'var(--critical)') +
        UI.kpi('À commander', String(data.alerts.length), '▲ sous le point de commande',
               'var(--serious)') +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Valorisation par rayon', UI.chartSlot('c-k-val'),
                "L'écart entre les deux points est la marge immobilisée dans le rayon.", 'span-2') +
        UI.card('Répartition de la valeur', UI.chartSlot('c-k-share'), '') +
      '</div>' +
      '<div class="grid grid-2 mt">' +
        UI.card('Alertes de réapprovisionnement', UI.table(data.alerts, [
          { key: 'product', label: 'Produit' },
          { key: 'supplier', label: 'Fournisseur' },
          { key: 'severity', label: 'État', type: 'badge' },
          { key: 'stock', label: 'Stock', type: 'num', decimals: 1 },
          { key: 'suggested_qty', label: 'À commander', type: 'num' },
          { key: 'suggested_cost', label: 'Coût', type: 'money' }
        ], { symbol: sym, limit: 10, empty: 'Aucune alerte : tous les stocks sont au-dessus du seuil.',
             rowClass: function (r) { return r.severity === 'rupture' ? 'row-critical' : 'row-serious'; } }),
          'Vue SQL v_stock_alerts, reprise telle quelle par le département Achats.') +
        UI.card('Mouvements de stock', UI.table(data.moves, [
          { key: 'moved_at', label: 'Date', type: 'date' },
          { key: 'product', label: 'Produit' },
          { key: 'move_type', label: 'Type' },
          { key: 'source_dept', label: 'Origine' },
          { key: 'quantity', label: 'Quantité', type: 'num', decimals: 1 }
        ], { symbol: sym, limit: 12 }),
          "Chaque ligne indique le département qui l'a générée.") +
      '</div>' +
      '<div class="mt">' + UI.card('Catalogue complet', UI.table(data.products, [
          { key: 'sku', label: 'SKU' },
          { key: 'name', label: 'Produit' },
          { key: 'category', label: 'Rayon' },
          { key: 'cost_price', label: 'Achat', type: 'money' },
          { key: 'sale_price', label: 'Vente', type: 'money' },
          { key: 'margin_rate', label: 'Marge', type: 'percent' },
          { key: 'stock', label: 'Stock', type: 'num', decimals: 1 },
          { key: 'stock_status', label: 'État', type: 'badge' },
          { key: 'stock_value', label: 'Valeur', type: 'money', strong: true }
        ], { symbol: sym, limit: 15 }),
        'Vue SQL v_products : prix, marge unitaire, niveau et état de stock.') + '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-k-val'), 'dumbbell', {
        labels: data.valuation.map(function (r) { return r.category; }),
        left: data.valuation.map(function (r) { return r.value; }),
        right: data.valuation.map(function (r) { return r.retail_value; }),
        leftName: 'Prix de revient', rightName: 'Prix de vente', symbol: sym
      });
      Charts.render(document.getElementById('c-k-share'), 'shareBars', {
        labels: data.valuation.map(function (r) { return r.category; }),
        values: data.valuation.map(function (r) { return r.value; }), symbol: sym
      });
    }};
  }

  /* ============================================================= ACHATS */
  function purchasing(data, days, company) {
    var sym = company.currency_sym;
    var pending = data.orders.filter(function (o) { return o.status === 'commandée'; });
    var planAmount = data.reorder_plan.reduce(function (a, r) { return a + (r.amount || 0); }, 0);

    var html =
      UI.pageHead('🚚&nbsp; Achats',
        "Le plan de commande n'est pas saisi : il est déduit des niveaux de stock et " +
        'des ventes, puis groupé par fournisseur.') +
      '<div class="grid grid-4">' +
        UI.kpi('Fournisseurs actifs', String(data.suppliers.length), 'au référentiel',
               UI.deptColor('PURCH')) +
        UI.kpi('Commandes en cours', String(pending.length), 'en attente de réception',
               UI.deptColor('STOCK')) +
        UI.kpi('Réappro. suggéré', money(planAmount, sym),
               data.reorder_plan.reduce(function (a, r) { return a + r.refs; }, 0) +
               ' références sous le seuil', UI.deptColor('SALES')) +
        UI.kpi('Total commandé', money(data.monthly.reduce(function (a, r) {
                 return a + (r.amount || 0); }, 0), sym), 'sur tout l\'historique',
               UI.deptColor('FIN')) +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Achats par mois', UI.chartSlot('c-p-monthly'),
                'Montant des commandes fournisseurs, hors annulations.', 'span-2') +
        UI.card('Dépense par fournisseur', UI.chartSlot('c-p-sup'), '') +
      '</div>' +
      '<div class="grid grid-2 mt">' +
        UI.card('Plan de réapprovisionnement', UI.table(data.reorder_plan, [
          { key: 'supplier', label: 'Fournisseur' },
          { key: 'refs', label: 'Réf.', type: 'num' },
          { key: 'units', label: 'Unités', type: 'num' },
          { key: 'amount', label: 'Montant', type: 'money', strong: true },
          { key: 'lead_time_days', label: 'Délai (j)', type: 'num' }
        ], { symbol: sym, limit: 8, empty: 'Aucun réapprovisionnement nécessaire.' }),
          'Une commande par fournisseur, prête à être passée.') +
        UI.card('Fournisseurs', UI.table(data.suppliers, [
          { key: 'name', label: 'Fournisseur' },
          { key: 'contact_name', label: 'Contact' },
          { key: 'lead_time_days', label: 'Délai (j)', type: 'num' },
          { key: 'rating', label: 'Note', type: 'num', decimals: 1 },
          { key: 'spend', label: 'Dépense', type: 'money', strong: true }
        ], { symbol: sym, limit: 8 }), 'Note sur 5 : qualité, délais, litiges.') +
      '</div>' +
      '<div class="mt">' + UI.card('Commandes fournisseurs', UI.table(data.orders, [
          { key: 'ref', label: 'Référence' },
          { key: 'supplier', label: 'Fournisseur' },
          { key: 'ordered_on', label: 'Commandée le' },
          { key: 'received_on', label: 'Reçue le' },
          { key: 'status', label: 'Statut' },
          { key: 'total', label: 'Total', type: 'money', strong: true }
        ], { symbol: sym, limit: 12,
             rowClass: function (r) { return r.status === 'commandée' ? 'row-serious' : ''; } }),
        "Passer une commande au statut « reçue » déclenche l'entrée en stock par trigger SQL.") +
      '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-p-monthly'), 'bars', {
        labels: data.monthly.map(function (r) { return Fmt.period(r.period); }),
        values: data.monthly.map(function (r) { return r.amount; }),
        symbol: sym, height: 280, color: Charts.color(2)
      });
      Charts.render(document.getElementById('c-p-sup'), 'shareBars', {
        labels: data.suppliers.slice(0, 6).map(function (r) { return r.name; }),
        values: data.suppliers.slice(0, 6).map(function (r) { return r.spend; }), symbol: sym
      });
    }};
  }

  /* ============================================================ CLIENTS */
  function customers(data, days, company) {
    var sym = company.currency_sym;
    var ltv = data.customers.reduce(function (a, c) { return a + (c.lifetime_value || 0); }, 0);
    var points = data.customers.reduce(function (a, c) { return a + (c.loyalty_points || 0); }, 0);

    var html =
      UI.pageHead('👥&nbsp; Clients',
        'La fiche client se remplit toute seule : chaque encaissement met à jour son ' +
        'historique, sa valeur et ses points de fidélité.') +
      '<div class="grid grid-4">' +
        UI.kpi('Clients au fichier', Fmt.number(data.customers.length), 'tous segments',
               UI.deptColor('CRM')) +
        UI.kpi('Valeur vie cumulée', money(ltv, sym), 'tous clients confondus',
               UI.deptColor('FIN')) +
        UI.kpi('Points de fidélité', Fmt.number(points), '1 point par tranche encaissée',
               UI.deptColor('HR')) +
        UI.kpi('À relancer', String(data.dormant.length), 'sans achat depuis 45 jours',
               'var(--serious)') +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card("Chiffre d'affaires par segment", UI.chartSlot('c-c-seg'),
                'Un professionnel pèse plusieurs fois un particulier.') +
        UI.card('Poids des segments', UI.table(data.segments, [
          { key: 'segment', label: 'Segment' },
          { key: 'customers', label: 'Clients', type: 'num' },
          { key: 'revenue', label: 'CA', type: 'money', strong: true },
          { key: 'avg_basket', label: 'Panier', type: 'money' }
        ], { symbol: sym, limit: 6 }), 'La vue table du graphique ci-contre.') +
        UI.card('Nouveaux clients par mois', UI.chartSlot('c-c-acq'),
                "Date de première inscription au fichier.") +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Meilleurs clients', UI.table(data.customers, [
          { key: 'customer', label: 'Client' },
          { key: 'segment', label: 'Segment' },
          { key: 'city', label: 'Ville' },
          { key: 'orders', label: 'Commandes', type: 'num' },
          { key: 'lifetime_value', label: 'Valeur vie', type: 'money', strong: true },
          { key: 'loyalty_points', label: 'Points', type: 'num' },
          { key: 'last_purchase', label: 'Dernier achat' }
        ], { symbol: sym, limit: 12 }), 'Vue SQL v_customer_value.', 'span-2') +
        UI.card('Clients à relancer', UI.table(data.dormant, [
          { key: 'customer', label: 'Client' },
          { key: 'days_since_last', label: 'Jours', type: 'num' },
          { key: 'lifetime_value', label: 'Valeur', type: 'money' }
        ], { symbol: sym, limit: 12, empty: 'Aucun client dormant.' }),
          'Bons clients sans achat depuis plus de 45 jours.') +
      '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-c-seg'), 'shareBars', {
        labels: data.segments.map(function (r) { return r.segment; }),
        values: data.segments.map(function (r) { return r.revenue; }), symbol: sym
      });
      Charts.render(document.getElementById('c-c-acq'), 'bars', {
        labels: data.acquisition.slice(-10).map(function (r) { return Fmt.period(r.period); }),
        values: data.acquisition.slice(-10).map(function (r) { return r.customers; }),
        height: 240, color: Charts.color(4)
      });
    }};
  }

  /* ================================================================= RH */
  function hr(data, days, company) {
    var sym = company.currency_sym;
    var payroll = data.by_department.reduce(function (a, d) { return a + (d.payroll || 0); }, 0);
    var sellers = data.employees.filter(function (e) { return e.tickets > 0; });

    var html =
      UI.pageHead('🧑‍💼&nbsp; Ressources humaines',
        "L'équipe est reliée aux ventes : le même identifiant salarié sert à la paie " +
        'et au calcul de la performance commerciale.') +
      '<div class="grid grid-4">' +
        UI.kpi('Effectif', String(data.employees.length),
               data.by_department.length + ' services', UI.deptColor('HR')) +
        UI.kpi('Masse salariale', money(payroll, sym), 'par mois, salaires bruts',
               UI.deptColor('FIN')) +
        UI.kpi('Salariés encaissant', String(sellers.length), 'reliés à un ticket',
               UI.deptColor('SALES')) +
        UI.kpi('CA moyen par vendeur', money(sellers.reduce(function (a, e) {
                 return a + (e.revenue || 0); }, 0) / Math.max(1, sellers.length), sym),
               'sur tout l\'historique', UI.deptColor('CRM')) +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Masse salariale versée par mois', UI.chartSlot('c-h-pay'),
                'Segments empilés séparés par 2 px : les parts restent lisibles.', 'span-2') +
        UI.card('Effectif par service', UI.chartSlot('c-h-dept'), '') +
      '</div>' +
      '<div class="mt">' + UI.card('Performance commerciale de l\'équipe',
        UI.table(data.employees, [
          { key: 'employee', label: 'Salarié' },
          { key: 'role', label: 'Poste' },
          { key: 'department', label: 'Service' },
          { key: 'salary', label: 'Salaire', type: 'money' },
          { key: 'tickets', label: 'Tickets', type: 'num' },
          { key: 'revenue', label: 'CA généré', type: 'money', strong: true },
          { key: 'avg_basket', label: 'Panier moyen', type: 'money' }
        ], { symbol: sym, limit: 12 }),
        'Vue SQL v_employee_performance : jointure RH × Ventes. Un poste sans ' +
        'encaissement affiche logiquement zéro ticket.') + '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-h-pay'), 'groupedBars', {
        x: data.payroll.map(function (r) { return Fmt.period(r.period); }),
        series: {
          'Salaires nets': data.payroll.map(function (r) { return r.net; }),
          'Primes': data.payroll.map(function (r) { return r.bonus; })
        }, symbol: sym, height: 290, stacked: true
      });
      Charts.render(document.getElementById('c-h-dept'), 'shareBars', {
        labels: data.by_department.map(function (r) { return r.department; }),
        values: data.by_department.map(function (r) { return r.headcount; }), symbol: ''
      });
    }};
  }

  /* ============================================================ FINANCE */
  function finance(data, days, company) {
    var sym = company.currency_sym;
    var monthly = data.monthly;
    var closed = monthly.length > 1 ? monthly.slice(0, -1) : monthly;
    var last = closed[closed.length - 1] || {};
    var margin = (last.revenue || 0) - (last.cogs || 0);

    var html =
      UI.pageHead('💰&nbsp; Finance',
        "Le compte de résultat n'est pas ressaisi : ventes, coût des marchandises, " +
        'charges et paie remontent automatiquement des autres départements.') +
      '<div class="grid grid-4">' +
        UI.kpi("CA — " + Fmt.period(last.period || ''), money(last.revenue, sym),
               'dernier mois clos', UI.deptColor('SALES')) +
        UI.kpi('Marge brute', money(margin, sym),
               last.revenue ? 'taux ' + Fmt.percent(margin / last.revenue) : '—',
               UI.deptColor('FIN')) +
        UI.kpi('Charges + paie', money((last.expenses || 0) + (last.payroll || 0), sym),
               'structure et salaires', UI.deptColor('HR')) +
        UI.kpi('Résultat net', money(last.net_result, sym),
               (last.net_result >= 0 ? '✓ bénéfice' : '⛔ perte'),
               last.net_result >= 0 ? 'var(--good)' : 'var(--critical)') +
      '</div>' +
      '<div class="grid grid-3 mt">' +
        UI.card('Chiffre d\'affaires, coût des marchandises et charges',
                UI.chartSlot('c-f-monthly'),
                'Trois mesures dans la même unité, donc un seul axe de valeurs.', 'span-2') +
        UI.card('Charges par nature', UI.chartSlot('c-f-cat'), 'Sur douze mois glissants.') +
      '</div>' +
      '<div class="grid grid-2 mt">' +
        UI.card('Compte de résultat mensuel', UI.table(monthly, [
          { key: 'period', label: 'Période' },
          { key: 'revenue', label: 'CA', type: 'money' },
          { key: 'cogs', label: 'Coût march.', type: 'money' },
          { key: 'expenses', label: 'Charges', type: 'money' },
          { key: 'payroll', label: 'Paie', type: 'money' },
          { key: 'net_result', label: 'Résultat', type: 'money', strong: true }
        ], { symbol: sym, limit: 13,
             rowClass: function (r) { return r.net_result < 0 ? 'row-critical' : ''; } }),
          'Vue SQL v_financial_monthly. Le dernier mois est partiel.') +
        UI.card('Journal des charges', UI.table(data.entries, [
          { key: 'spent_on', label: 'Date' },
          { key: 'label', label: 'Libellé' },
          { key: 'category', label: 'Nature' },
          { key: 'department', label: 'Département' },
          { key: 'amount', label: 'Montant', type: 'money', strong: true }
        ], { symbol: sym, limit: 13 }), '150 dernières écritures.') +
      '</div>';

    return { html: html, draw: function () {
      Charts.render(document.getElementById('c-f-monthly'), 'groupedBars', {
        x: monthly.map(function (r) { return Fmt.period(r.period); }),
        series: {
          "Chiffre d'affaires": monthly.map(function (r) { return r.revenue; }),
          'Coût des marchandises': monthly.map(function (r) { return r.cogs; }),
          'Charges + paie': monthly.map(function (r) {
            return (r.expenses || 0) + (r.payroll || 0); })
        }, symbol: sym, height: 310
      });
      Charts.render(document.getElementById('c-f-cat'), 'shareBars', {
        labels: data.by_category.map(function (r) { return r.category; }),
        values: data.by_category.map(function (r) { return r.amount; }), symbol: sym
      });
    }};
  }

  global.Views = {
    overview: overview, sales: sales, stock: stock,
    purchasing: purchasing, customers: customers, hr: hr, finance: finance
  };
}(window));
