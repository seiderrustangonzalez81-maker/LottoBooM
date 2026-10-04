/* rt_polling.js — Polling LottoBooM
 * - Heartbeat cada 90s
 * - Poll estado cada N ms con jitter ±20%
 * - ETag: 304 sin cambios
 * - Pausa al ocultar pestaña
 */
(function(global){
  'use strict';
  var HEARTBEAT_MS = 90000;

  function jitter(ms){ var d = ms * 0.20; return ms + (Math.random() * 2 * d - d); }

  function getCsrf(){
    var c = document.querySelector('[name=csrfmiddlewaretoken]');
    if (c) return c.value;
    var m = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
    return m ? m[2] : '';
  }

  function heartbeat(url){
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' },
    }).catch(function(){});
  }

  function Poller(opts){
    this.stateUrl = opts.stateUrl;
    this.heartUrl = opts.heartUrl;
    this.scope = opts.scope || 'global';
    this.params = opts.params || {};
    this.interval = opts.interval || 20000;
    this.onData = opts.onData || function(){};
    this._etag = null;
    this._timer = null;
    this._heartTimer = null;
    this._stopped = false;
  }

  Poller.prototype._buildUrl = function(){
    var qs = ['scope=' + encodeURIComponent(this.scope)];
    var self = this;
    Object.keys(this.params).forEach(function(k){
      var v = self.params[k];
      if (v !== null && v !== undefined && v !== '') {
        qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
      }
    });
    return this.stateUrl + '?' + qs.join('&');
  };

  Poller.prototype._tick = function(){
    if (this._stopped) return;
    var self = this;
    var headers = {
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json',
    };
    if (this._etag) headers['If-None-Match'] = this._etag;

    fetch(this._buildUrl(), { headers: headers, credentials: 'same-origin' })
      .then(function(r){
        if (r.status === 304) return null;
        if (r.status === 429) return null;
        if (!r.ok) throw new Error('HTTP ' + r.status);
        var et = r.headers.get('ETag');
        if (et) self._etag = et;
        return r.json();
      })
      .then(function(data){
        if (data) {
          try { self.onData(data); } catch(e){ console.error('[rt_poll onData]', e); }
        }
      })
      .catch(function(e){ console.warn('[rt_poll]', e); })
      .finally(function(){
        if (self._stopped) return;
        self._timer = setTimeout(function(){ self._tick(); }, jitter(self.interval));
      });
  };

  Poller.prototype.start = function(){
    var self = this;
    if (this.heartUrl) {
      heartbeat(this.heartUrl);
      this._heartTimer = setInterval(function(){ heartbeat(self.heartUrl); }, HEARTBEAT_MS);
    }
    this._tick();
    document.addEventListener('visibilitychange', function(){
      if (document.hidden) {
        if (self._timer) { clearTimeout(self._timer); self._timer = null; }
      } else {
        self._etag = null;
        self._tick();
        if (self.heartUrl) heartbeat(self.heartUrl);
      }
    });
  };

  Poller.prototype.stop = function(){
    this._stopped = true;
    if (this._timer) clearTimeout(this._timer);
    if (this._heartTimer) clearInterval(this._heartTimer);
  };

  Poller.prototype.updateParams = function(newParams){
    this.params = Object.assign({}, this.params, newParams);
    this._etag = null;
  };

  global.LottoRT = {
    create: function(opts){ return new Poller(opts); },
    start: function(opts){
      var p = new Poller(opts);
      p.start();
      return p;
    },
  };
})(window);
