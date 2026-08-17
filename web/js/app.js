/* =====================================================================
   Amorçage, routage et onboarding du front web.
   ===================================================================== */
(function () {
  'use strict';

  var DEPARTMENTS = [
    { code: 'OVERVIEW', route: 'overview', name: "Vue d'ensemble" },
    { code: 'SALES', route: 'sales', name: 'Ventes' },
    { code: 'STOCK', route: 'stock', name: 'Stock' },
    { code: 'PURCH', route: 'purchasing', name: 'Achats' },
    { code: 'CRM', route: 'customers', name: 'Clients' },
    { code: 'HR', route: 'hr', name: 'Ressources humaines' },
    { code: 'FIN', route: 'finance', name: 'Finance' }
  ];

  var state = { company: null, route: 'overview', days: 30, storeType: null, types: [] };

  var $ = function (id) { return document.getElementById(id); };

  /* ---------------------------------------------------------- overlay */
  function busy(on, text, progress) {
    var overlay = $('overlay');
    overlay.hidden = !on;
    if (text) $('overlay-text').textContent = text;
    if (progress !== undefined) $('overlay-bar').style.width = (progress * 100) + '%';
  }

  /* ------------------------------------------------------- onboarding */
  /**
   * L'API est le seul fournisseur de données du front. Si elle ne répond pas,
   * on affiche la marche à suivre plutôt que des champs vides, et on désactive
   * la création tant que la connexion n'est pas rétablie.
   */
  function showApiError(message) {
    $('type-grid').innerHTML =
      '<div class="api-down">' +
        '<div class="api-down-title">Le service de données n\'est pas démarré</div>' +
        '<p>Le front web ne contient aucune donnée : il interroge l\'API. ' +
        'Ouvrez un terminal à la racine du projet et lancez :</p>' +
        '<pre><code>cd python\npip install -r requirements.txt\nuvicorn api.main:app --port 8000</code></pre>' +
        '<p class="api-down-note">Adresse attendue : <code>' + Fmt.esc(Api.base) +
        '</code>. Pour une API ailleurs, ajoutez <code>?api=https://mon-api</code> ' +
        'à l\'adresse de cette page.</p>' +
        '<button type="button" class="btn" id="btn-retry">Réessayer</button>' +
      '</div>';
    $('btn-create').disabled = true;
    $('onboard-echo').textContent = '';
    var notice = $('onboard-notice');
    notice.className = 'notice notice-warn';
    notice.innerHTML = '<div><b>API injoignable.</b> ' +
      Fmt.esc(message) + '</div>';
    var retry = document.getElementById('btn-retry');
    if (retry) retry.addEventListener('click', showOnboarding);
  }

  function showOnboarding() {
    $('app').hidden = true;
    $('onboarding').hidden = false;
    $('btn-create').disabled = false;
    Api.storeTypes().then(function (data) {
      state.types = data.types;
      $('type-grid').innerHTML = data.types.map(function (t) {
        return '<button type="button" class="type-card" role="radio" aria-checked="false" ' +
          'data-key="' + Fmt.esc(t.key) + '">' +
          '<div class="type-icon">' + Fmt.esc(t.icon) + '</div>' +
          '<div class="type-name">' + Fmt.esc(t.label) + '</div>' +
          '<div class="type-tag">' + Fmt.esc(t.tagline) + '</div>' +
          '<div class="type-meta"><span>' + t.n_categories + ' rayons</span>' +
          '<span>' + t.n_products + ' produits</span>' +
          '<span>' + t.n_roles + ' métiers</span></div></button>';
      }).join('');
      $('f-currency').innerHTML = data.currencies.map(function (c) {
        return '<option value="' + c.code + '"' + (c.code === 'XOF' ? ' selected' : '') + '>' +
          Fmt.esc(c.label) + ' (' + Fmt.esc(c.symbol) + ')</option>';
      }).join('');
    }).catch(function (error) { showApiError(error.message); });
  }

  $('type-grid').addEventListener('click', function (event) {
    var card = event.target.closest('.type-card');
    if (!card) return;
    state.storeType = card.getAttribute('data-key');
    Array.prototype.forEach.call(this.querySelectorAll('.type-card'), function (node) {
      node.setAttribute('aria-checked', node === card ? 'true' : 'false');
    });
    updateEcho();
  });

  $('f-name').addEventListener('input', updateEcho);

  function updateEcho() {
    var name = $('f-name').value.trim();
    var echo = $('onboard-echo');
    if (!state.storeType) { echo.textContent = "Choisissez d'abord un type de boutique."; return; }
    if (!name) { echo.textContent = 'Indiquez maintenant le nom de la boutique.'; return; }
    echo.textContent = 'Prêt : « ' + name + ' ».';
  }

  $('btn-create').addEventListener('click', function () {
    var name = $('f-name').value.trim();
    if (!state.storeType) return UI.toast('Sélectionnez le type de boutique (étape 1).', true);
    if (!name) return UI.toast('Le nom de la boutique est obligatoire (étape 2).', true);

    var months = parseInt($('f-months').value, 10);
    busy(true, 'Génération de l\'ERP « ' + name + ' »…', .08);
    // Progression indicative : la génération est une seule requête serveur.
    var fake = .08, timer = setInterval(function () {
      fake = Math.min(.92, fake + .045);
      busy(true, null, fake);
    }, 320);

    Api.createCompany({
      name: name, store_type: state.storeType,
      city: $('f-city').value.trim() || 'Abidjan',
      country: $('f-country').value.trim() || "Côte d'Ivoire",
      currency: $('f-currency').value,
      history_months: months,
      traffic_scale: parseFloat($('f-traffic').value)
    }).then(function (result) {
      clearInterval(timer);
      busy(true, 'Consolidation des tableaux de bord…', 1);
      state.company = result.company;
      setTimeout(function () {
        busy(false);
        $('onboarding').hidden = true;
        $('app').hidden = false;
        UI.toast('« ' + result.summary.company +' » créée : ' +
                 Fmt.number(result.summary.sales) + ' tickets générés.');
        mountShell();
        navigate('overview');
      }, 350);
    }).catch(function (error) {
      clearInterval(timer);
      busy(false);
      UI.toast(error.message, true);
    });
  });

  /* -------------------------------------------------------- coquille */
  function mountShell() {
    var company = state.company;
    $('brand-logo').textContent = company.logo_mark;
    $('brand-name').textContent = company.name;
    $('brand-type').textContent = company.store_label;
    $('brand-meta').textContent = company.currency + ' · TVA ' +
      Math.round(company.tax_rate * 100) + ' %';
    $('nav').innerHTML = DEPARTMENTS.map(function (d) {
      return '<button type="button" class="nav-link" data-route="' + d.route + '">' +
        Fmt.esc(d.name) + '</button>';
    }).join('');
  }

  $('nav').addEventListener('click', function (event) {
    var link = event.target.closest('.nav-link');
    if (link) navigate(link.getAttribute('data-route'));
  });

  $('period').addEventListener('click', function (event) {
    var button = event.target.closest('button[data-days]');
    if (!button) return;
    state.days = parseInt(button.getAttribute('data-days'), 10);
    Array.prototype.forEach.call(this.querySelectorAll('button'), function (b) {
      b.classList.toggle('on', b === button);
    });
    navigate(state.route);
  });

  $('btn-reset').addEventListener('click', function () {
    if (!confirm('Réinitialiser la plateforme ? Toutes les données seront effacées.')) return;
    busy(true, 'Réinitialisation…', .5);
    Api.resetCompany().then(function () {
      busy(false);
      state.company = null;
      state.storeType = null;
      $('f-name').value = '';
      showOnboarding();
    }).catch(function (error) { busy(false); UI.toast(error.message, true); });
  });

  /* --------------------------------------------------------- routage */
  var LOADERS = {
    overview:   function () { return Api.overview(state.days); },
    sales:      function () { return Api.sales(state.days); },
    stock:      function () { return Api.stock(state.days); },
    purchasing: function () { return Api.purchasing(); },
    customers:  function () { return Api.customers(); },
    hr:         function () { return Api.hr(); },
    finance:    function () { return Api.finance(); }
  };

  function navigate(route) {
    state.route = route;
    Charts.reset();
    UI.resetTables();
    Array.prototype.forEach.call(document.querySelectorAll('.nav-link'), function (link) {
      link.classList.toggle('active', link.getAttribute('data-route') === route);
    });
    var view = $('view');
    view.innerHTML = '<div class="empty"><span class="mark">⋯</span>Chargement…</div>';

    LOADERS[route]().then(function (data) {
      var rendered = Views[route](data, state.days, state.company);
      view.innerHTML = rendered.html;
      if (rendered.draw) rendered.draw();
      window.scrollTo({ top: 0, behavior: 'instant' });
    }).catch(function (error) {
      view.innerHTML = '<div class="notice notice-warn"><div>' +
        Fmt.esc(error.message) + '</div></div>';
    });
  }

  /* ----------------------------------------------------------- départ */
  Api.health().then(function (health) {
    if (!health.configured) return showOnboarding();
    return Api.company().then(function (company) {
      state.company = company;
      $('onboarding').hidden = true;
      $('app').hidden = false;
      mountShell();
      navigate('overview');
    });
  }).catch(function (error) {
    $('app').hidden = true;
    $('onboarding').hidden = false;
    showApiError(error.message);
  });
}());
