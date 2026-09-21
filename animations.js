/* ==========================================================================
   ANIMATIONS — apparitions au défilement, titres ligne par ligne, parallaxe.

   Principes relevés sur thierrychopain.com, réécrits en JS natif :
     · transformations en cubic-bezier(.77, 0, .18, 1), 1,2 s à 1,4 s
     · opacités en cubic-bezier(.32, .94, .6, 1), 0,8 s
     · titres révélés ligne par ligne, masquées puis remontées
     · visuels en parallaxe douce

   Deux garde-fous :
     · rien ne se déclenche si l'utilisateur a demandé moins d'animations ;
     · l'état masqué n'est appliqué que par la classe « js-anim » posée par
       ce script, donc sans JavaScript tout reste visible.
   ========================================================================== */

(function () {
  'use strict';

  var doux = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (doux.matches) return;

  var racine = document.documentElement;
  window.__animPretes = true;   /* désarme le filet de sécurité du <head> */

  /* ---------------------------------------------------------- Apparitions */

  /* Cette liste doit rester identique à celle du sélecteur :is() de
     styles-portfolio.css, qui applique l'état masqué avant le rendu. */
  var CIBLES = [
    '.hero-texte .label', '.hero-role', '.hero-logos', '.hero-desc', '.hero-actions', '.hero-credit', '.hero-portrait',
    '.bloc > .wrap > .label', '.bloc-desc', '.systeme-texte .bloc-desc',
    '.pills', '.cas-texte', '.cas-montage', '.methode-montage',
    '.colonnes-4 > *', '.cartes-4 > *', '.expertise-carte', '.expertise-texte', '.dsx-fiche', '.etape',
    '.systeme-faits > div', '.final-faits > div', '.final-actions',
    '.about-texte', '.about-cote', '.outils', '.billet', '.coord li',
    '.contact-lignes', '.contact-form'
  ];

  var aReveler = [];
  CIBLES.forEach(function (sel) {
    [].forEach.call(document.querySelectorAll(sel), function (el) {
      if (aReveler.indexOf(el) === -1) aReveler.push(el);
    });
  });

  var hauteur = window.innerHeight;

  /* Le premier écran s'anime lui aussi, en cascade : c'est le moment le plus
     regardé de la page. Le reste attend le défilement. */
  var premierEcran = [];

  aReveler.forEach(function (el) {
    if (el.getBoundingClientRect().top < hauteur * 0.92) premierEcran.push(el);
  });

  /* La cascade se fait en décalant le moment où la classe est posée, et non
     par transition-delay : le délai inline n'était pas honoré quand la classe
     arrivait dans la même image que lui. */
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      premierEcran.forEach(function (el, i) {
        setTimeout(function () { el.classList.add('vu'); }, Math.min(i * 110, 700));
      });
    });
  });

  if ('IntersectionObserver' in window) {
    var oeil = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('vu');
        oeil.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0 });

    /* Les éléments du premier écran sont déjà pris en charge par la cascade
       d'entrée. Les confier aussi à l'observateur les révélerait tous dans la
       même image, puisqu'ils sont visibles dès le départ. */
    aReveler.forEach(function (el) {
      if (premierEcran.indexOf(el) === -1) oeil.observe(el);
    });
  } else {
    aReveler.forEach(function (el) { el.classList.add('vu'); });
  }

  /* Décalage en cascade entre voisins d'une même grille : chaque enfant
     part 70 ms après le précédent, plafonné pour ne pas traîner. */
  ['.colonnes-4', '.cartes-4', '.dsx', '.process', '.billets', '.coord', '.pills']
    .forEach(function (sel) {
      [].forEach.call(document.querySelectorAll(sel), function (grille) {
        [].forEach.call(grille.children, function (enfant, i) {
          enfant.style.transitionDelay = Math.min(i * 70, 420) + 'ms';
        });
      });
    });

  /* ------------------------------------------------- Titres ligne par ligne */

  function decouper(titre) {
    if (titre.dataset.decoupe === 'fait') return;

    var origine = titre.dataset.origine || titre.innerHTML;
    titre.dataset.origine = origine;

    /* Un titre qui contient autre chose que du texte et des <br> n'est pas
       découpé : on ne prend pas le risque de démonter son balisage. */
    var nu = origine.replace(/<br\s*\/?>/gi, ' ');
    if (nu.indexOf('<') !== -1) return;

    /* Chaque mot devient une balise mesurable. Le jeton @@BR@@ marque les
       retours forcés : sans espace ni chevron, il traverse le découpage
       sans être confondu avec un mot. */
    titre.innerHTML = origine
      .replace(/<br\s*\/?>/gi, ' @@BR@@ ')
      .split(/\s+/)
      .filter(function (bout) { return bout.length; })
      .map(function (bout) {
        return bout === '@@BR@@'
          ? '<i data-coupure></i>'
          : '<i class="mot">' + bout + '</i>';
      })
      .join(' ');

    var mots = [].slice.call(titre.querySelectorAll('.mot, [data-coupure]'));
    if (!mots.length) { titre.innerHTML = origine; return; }

    var lignes = [];
    var courante = [];
    var haut = null;

    mots.forEach(function (m) {
      if (m.hasAttribute('data-coupure')) {
        if (courante.length) lignes.push(courante);
        courante = []; haut = null; return;
      }
      var y = m.offsetTop;
      if (haut === null) haut = y;
      if (Math.abs(y - haut) > 4) {
        lignes.push(courante); courante = []; haut = y;
      }
      courante.push(m.textContent);
    });
    if (courante.length) lignes.push(courante);

    if (lignes.length === 0) { titre.innerHTML = origine; return; }

    /* L'espace final garde le mot de fin de ligne séparé du suivant quand
       le titre est copié ou lu par une synthèse vocale. */
    titre.innerHTML = lignes.map(function (mots, i) {
      var fin = (i < lignes.length - 1) ? ' ' : '';
      return '<span class="ln"><span class="ln-in" style="transition-delay:' +
             (i * 90) + 'ms">' + mots.join(' ') + fin + '</span></span>';
    }).join('');

    titre.dataset.decoupe = 'fait';
    titre.classList.add('titre-anime');
  }

  var titres = [].slice.call(document.querySelectorAll(
    '.hero-texte h1, .bloc-titre, .systeme-texte h2, .final-titre, .cas-titre'
  ));

  titres.forEach(decouper);

  function montrerTitre(t) { t.classList.add('vu'); }

  titres.forEach(function (t) {
    if (t.getBoundingClientRect().top < hauteur * 0.9) {
      /* Le titre du hero part tout de suite, les autres à l'approche. */
      requestAnimationFrame(function () { montrerTitre(t); });
    }
  });

  if ('IntersectionObserver' in window) {
    var oeilTitres = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        montrerTitre(e.target);
        oeilTitres.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0 });

    titres.forEach(function (t) {
      if (!t.classList.contains('vu')) oeilTitres.observe(t);
    });
  } else {
    titres.forEach(montrerTitre);
  }

  /* Au redimensionnement le nombre de lignes change : on redécoupe. */
  var minuteur;
  var largeur = window.innerWidth;
  window.addEventListener('resize', function () {
    if (window.innerWidth === largeur) return;
    largeur = window.innerWidth;
    clearTimeout(minuteur);
    minuteur = setTimeout(function () {
      titres.forEach(function (t) {
        t.dataset.decoupe = '';
        t.classList.remove('titre-anime');
        decouper(t);
        t.classList.add('vu');
      });
      hauteur = window.innerHeight;
    }, 220);
  }, { passive: true });

  /* ----------------------------------------------------------- Parallaxe */

  var visuels = [].slice.call(document.querySelectorAll('.cas-montage, .methode-montage'));
  if (visuels.length && window.innerWidth > 760) {
    var actifs = [];

    if ('IntersectionObserver' in window) {
      var oeilPara = new IntersectionObserver(function (entrees) {
        entrees.forEach(function (e) {
          var i = actifs.indexOf(e.target);
          if (e.isIntersecting && i === -1) actifs.push(e.target);
          if (!e.isIntersecting && i !== -1) actifs.splice(i, 1);
        });
      }, { rootMargin: '120px 0px' });
      visuels.forEach(function (v) { oeilPara.observe(v); });
    } else {
      actifs = visuels;
    }

    var enCours = false;
    function peindre() {
      var mi = window.innerHeight / 2;
      actifs.forEach(function (v) {
        var r = v.getBoundingClientRect();
        var centre = r.top + r.height / 2;
        var ecart = (centre - mi) / window.innerHeight;   /* -1 … 1 */
        var y = Math.max(-18, Math.min(18, ecart * 26));
        var cible = v.querySelector('iframe, img') || v;
        cible.style.transform = 'translate3d(0,' + y.toFixed(1) + 'px,0)';
      });
      enCours = false;
    }

    window.addEventListener('scroll', function () {
      if (enCours) return;
      enCours = true;
      requestAnimationFrame(peindre);
    }, { passive: true });

    peindre();
  }

  /* L'utilisateur peut activer « moins d'animations » en cours de route. */
  doux.addEventListener('change', function (e) {
    if (!e.matches) return;
    racine.classList.remove('js-anim');
    document.querySelectorAll('.vu, .titre-anime').forEach(function (el) {
      el.classList.add('vu');
      el.style.transitionDelay = '';
    });
  });
})();
