/* Relecture de vraies exécutions n8n : noms des étapes, ordre et durées viennent des exécutions enregistrées. */
(function () {
  var racine = document.getElementById('sim'), D = window.DK_WORKFLOWS;
  if (!racine || !D) return;
  var calme = matchMedia('(prefers-reduced-motion: reduce)').matches, NS = 'http://www.w3.org/2000/svg', NW = 196, NH = 66;
  var $ = function (s) { return racine.querySelector(s); };
  var svg = $('.sim-canvas svg'), boite = $('.sim-canvas'), journal = $('.sim-journal'), etat = $('.sim-etat'), bouton = $('.sim-lancer');
  var cur = null, nds = {}, ars = {}, pos = {}, jeton = 0, vu = null, ech = 1, largeur = 1, hauteur = 1;
  function el(n, a, p) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; }
  function sec(ms) { return (ms / 1000).toFixed(ms < 1000 ? 2 : 1).replace('.', ',') + ' s'; }
  var TYPES = { scheduleTrigger: 'Déclencheur', formTrigger: 'Formulaire', webhook: 'Adresse d’entrée', errorTrigger: 'Déclencheur d’erreur', dataTable: 'Base de données', httpRequest: 'Appel API', code: 'Code', set: 'Données', if: 'Condition', switch: 'Aiguillage', wait: 'Attente', telegram: 'Telegram', linkedIn: 'LinkedIn', readWriteFile: 'Fichier', chainLlm: 'IA', lmChatAnthropic: 'Claude', textClassifier: 'IA', respondToWebhook: 'Réponse', splitOut: 'Découpage', aggregate: 'Regroupement', merge: 'Fusion', filter: 'Filtre', noOp: 'Étape', executeCommand: 'Commande' };
  function coupe(t, n) { return t.length > n ? t.slice(0, n - 1) + '…' : t; }
  function dessine(w) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    nds = {}; ars = {}; pos = {};
    var xs = w.nodes.map(function (n) { return n[2]; }), ys = w.nodes.map(function (n) { return n[3]; });
    var x0 = Math.min.apply(0, xs) - 30, y0 = Math.min.apply(0, ys) - 30;
    largeur = Math.max.apply(0, xs) - x0 + NW + 30; hauteur = Math.max.apply(0, ys) - y0 + NH + 30;
    svg.setAttribute('viewBox', '0 0 ' + largeur + ' ' + hauteur);
    svg.style.minWidth = Math.min(largeur * .8, 3000) + 'px';
    w.nodes.forEach(function (n) { pos[n[0]] = [n[2] - x0, n[3] - y0, n[1]]; });
    w.links.forEach(function (l) {
      var a = pos[l[0]], b = pos[l[1]]; if (!a || !b) return;
      var ax = a[0] + NW, ay = a[1] + NH / 2, bx = b[0], by = b[1] + NH / 2, d = Math.max(50, Math.abs(bx - ax) / 2);
      ars[l[0] + '>' + l[1]] = el('path', { d: 'M' + ax + ' ' + ay + ' C' + (ax + d) + ' ' + ay + ',' + (bx - d) + ' ' + by + ',' + bx + ' ' + by, class: 'sim-arete' }, svg);
    });
    w.nodes.forEach(function (n) {
      var p = pos[n[0]], g = el('g', { class: 'sim-noeud', transform: 'translate(' + p[0] + ',' + p[1] + ')' }, svg);
      el('rect', { width: NW, height: NH, rx: 8 }, g);
      el('text', { x: 12, y: 24, class: 'sim-type' }, g).textContent = (TYPES[n[1]] || n[1]);
      el('text', { x: 12, y: 49, class: 'sim-nom' }, g).textContent = coupe(n[0], 23);
      nds[n[0]] = g;
    });
  }
  function ligne(t, c) { var p = document.createElement('p'); if (c) p.className = c; p.textContent = t; journal.appendChild(p); journal.scrollTop = journal.scrollHeight; }
  function resultat(w, fini) {
    var r = w.res, b = $('.sim-resultat'); b.className = 'sim-resultat' + (fini ? ' fini' : '');
    var h = ''; if (r.img) h += '<img src="' + r.img + '" alt="" loading="lazy">';
    b.innerHTML = h + '<strong></strong><p></p>' + (r.lien ? '<a target="_blank" rel="noopener" href="' + r.lien + '">Voir le vrai post sur LinkedIn ↗</a>' : '');
    b.querySelector('strong').textContent = r.titre; b.querySelector('p').textContent = r.texte;
  }
  function choisir(id) {
    jeton++; cur = D.filter(function (w) { return w.id === id; })[0]; dessine(cur);
    racine.querySelectorAll('[data-wf]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.wf === id); });
    $('.sim-desc').textContent = cur.desc;
    var e = $('.sim-badge'); e.textContent = cur.etat; e.className = 'sim-badge ' + cur.cl;
    $('.sim-meta').textContent = 'Exécution n° ' + cur.ex + ' · ' + cur.quand + ' · ' + cur.trace.length + ' étapes · durée réelle ' + sec(cur.duree * 1000);
    journal.textContent = ''; etat.textContent = 'Prêt'; boite.scrollLeft = 0; resultat(cur, false);
    ligne('Prêt : lancez la relecture', 'sim-gris');
  }
  function ordre(w) {
    var entrants = {}; w.links.forEach(function (l) { entrants[l[1]] = 1; });
    var t = w.trace.slice(), i = t.findIndex(function (x) { return !entrants[x[0]] && /Trigger|webhook/i.test((w.nodes.filter(function (n) { return n[0] === x[0]; })[0] || [])[1] || ''); });
    if (i > 0) t.unshift(t.splice(i, 1)[0]);
    return t;
  }
  function lancer() {
    if (vu) { vu.disconnect(); vu = null; }
    var w = Object.assign({}, cur), moi = ++jeton, i = 0, t = 0; w.trace = ordre(cur); dessine(w); journal.textContent = ''; resultat(w, false);
    etat.textContent = 'Relecture'; bouton.textContent = 'Rejouer';
    (function suite() {
      if (moi !== jeton) return;
      if (i >= w.trace.length) {
        if (w.trace[i - 1] && nds[w.trace[i - 1][0]]) nds[w.trace[i - 1][0]].setAttribute('class', 'sim-noeud fait');
        etat.textContent = 'Terminé en ' + sec(w.duree * 1000); resultat(w, true); return;
      }
      var s = w.trace[i], n = s[0], p = w.trace[i - 1];
      if (p && nds[p[0]]) nds[p[0]].setAttribute('class', 'sim-noeud fait');
      if (p && ars[p[0] + '>' + n]) ars[p[0] + '>' + n].classList.add('on');
      if (nds[n]) {
        nds[n].setAttribute('class', 'sim-noeud actif');
        boite.scrollLeft = Math.max(0, (pos[n][0] + NW / 2) / largeur * boite.scrollWidth - boite.clientWidth / 2);
        boite.scrollTop = Math.max(0, (pos[n][1] + NH / 2) / hauteur * boite.scrollHeight - boite.clientHeight / 2);
      }
      ligne('+' + sec(t) + '  ' + n + '  (' + (s[1] < 1000 ? s[1] + ' ms' : sec(s[1])) + ')');
      t += s[1]; i++;
      setTimeout(suite, calme ? 40 : Math.min(1500, 320 + s[1] * .06));
    })();
  }
  racine.querySelectorAll('[data-wf]').forEach(function (b) { b.addEventListener('click', function () { choisir(b.dataset.wf); lancer(); }); });
  bouton.addEventListener('click', lancer);
  choisir(D[0].id);
  if ('IntersectionObserver' in window && !calme) {
    vu = new IntersectionObserver(function (e) { if (e[0].isIntersecting) lancer(); }, { threshold: .3 });
    vu.observe(boite);
  }
})();
