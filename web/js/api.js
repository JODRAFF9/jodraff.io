/* =====================================================================
   Client de l'API REST (python/api/main.py).
   Le front n'accède jamais à la base directement : il passe par l'API,
   qui est la même source pour l'application Angular.
   ===================================================================== */
(function (global) {
  'use strict';

  // Même origine si le front est servi par un proxy ; sinon l'API locale.
  var BASE = (function () {
    var override = new URLSearchParams(location.search).get('api');
    if (override) return override.replace(/\/$/, '');
    if (location.protocol === 'file:') return 'http://127.0.0.1:8000';
    if (location.port === '8000') return location.origin;
    return 'http://127.0.0.1:8000';
  }());

  function request(path, options) {
    var opts = options || {};
    return fetch(BASE + '/api' + path, {
      method: opts.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (response) {
      return response.text().then(function (text) {
        var payload = text ? JSON.parse(text) : null;
        if (!response.ok) {
          var detail = payload && payload.detail ? payload.detail : response.statusText;
          if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join(', ');
          var err = new Error(detail);
          err.status = response.status;
          throw err;
        }
        return payload;
      });
    }, function () {
      var err = new Error(
        'API injoignable sur ' + BASE + '. Lancez : cd python && uvicorn api.main:app --port 8000'
      );
      err.status = 0;
      throw err;
    });
  }

  global.Api = {
    base: BASE,
    health:      function () { return request('/health'); },
    storeTypes:  function () { return request('/store-types'); },
    theme:       function () { return request('/theme'); },
    company:     function () { return request('/company'); },
    createCompany: function (payload) { return request('/company', { method: 'POST', body: payload }); },
    resetCompany:  function () { return request('/company', { method: 'DELETE' }); },

    overview:    function (days) { return request('/overview?days=' + days); },
    sales:       function (days) { return request('/sales?days=' + days); },
    stock:       function (days) { return request('/stock?days=' + days); },
    purchasing:  function () { return request('/purchasing'); },
    customers:   function () { return request('/customers'); },
    hr:          function () { return request('/hr'); },
    finance:     function () { return request('/finance'); },

    createSale:  function (payload) { return request('/sales', { method: 'POST', body: payload }); },
    stockMove:   function (payload) { return request('/stock/moves', { method: 'POST', body: payload }); },
    receivePurchase: function (id) { return request('/purchases/' + id + '/receive', { method: 'POST' }); }
  };
}(window));
