/* Menu burger — mobile uniquement.
   Le bouton n'existe que sous 700px (voir styles.css) ; le panneau se ferme
   au clic sur un lien, à l'Échap, et quand on repasse en grand écran.       */
(function () {
  var bouton = document.getElementById('burger');
  var panneau = document.getElementById('menu-principal');
  if (!bouton || !panneau) return;

  var voile = document.createElement('div');
  voile.className = 'menu-voile';
  document.body.appendChild(voile);

  function ouvrir() {
    panneau.classList.add('ouvert');
    voile.classList.add('visible');
    bouton.classList.add('actif');
    bouton.setAttribute('aria-expanded', 'true');
    bouton.setAttribute('aria-label', 'Fermer le menu');
    document.body.style.overflow = 'hidden';
    var premier = panneau.querySelector('button, a');
    if (premier) premier.focus({ preventScroll: true });
  }

  function fermer(rendreLeFocus) {
    panneau.classList.remove('ouvert');
    voile.classList.remove('visible');
    bouton.classList.remove('actif');
    bouton.setAttribute('aria-expanded', 'false');
    bouton.setAttribute('aria-label', 'Ouvrir le menu');
    document.body.style.overflow = '';
    if (rendreLeFocus) bouton.focus({ preventScroll: true });
  }

  bouton.addEventListener('click', function () {
    if (panneau.classList.contains('ouvert')) fermer(true); else ouvrir();
  });

  voile.addEventListener('click', function () { fermer(false); });

  panneau.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') fermer(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panneau.classList.contains('ouvert')) fermer(true);
  });

  // Le panneau ne doit pas rester ouvert si l'écran redevient large
  var large = window.matchMedia('(min-width: 700px)');
  var surChangement = function (e) { if (e.matches) fermer(false); };
  if (large.addEventListener) large.addEventListener('change', surChangement);
  else large.addListener(surChangement);
})();

/* Bascule de langue — le chevron ouvre le choix sous le déclencheur.
   Le bouton est un <button> : le clic ne ferme donc pas le panneau mobile,
   qui ne se referme que sur un <a>.                                        */
(function () {
  var bloc = document.querySelector('.pf-langue');
  if (!bloc) return;
  var bouton = bloc.querySelector('.pf-langue-bouton');
  var menu = bloc.querySelector('.pf-langue-menu');
  if (!bouton || !menu) return;

  function ouvert() { return bouton.getAttribute('aria-expanded') === 'true'; }

  function basculer(etat) {
    bouton.setAttribute('aria-expanded', etat ? 'true' : 'false');
    menu.hidden = !etat;
    if (etat) {
      var premier = menu.querySelector('a[aria-current]') || menu.querySelector('a');
      if (premier) premier.focus({ preventScroll: true });
    }
  }

  bouton.addEventListener('click', function (e) {
    e.stopPropagation();
    basculer(!ouvert());
  });

  document.addEventListener('click', function (e) {
    if (ouvert() && !bloc.contains(e.target)) basculer(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && ouvert()) {
      basculer(false);
      bouton.focus({ preventScroll: true });
    }
  });

  /* Sortir du menu au clavier le referme. */
  bloc.addEventListener('focusout', function (e) {
    if (ouvert() && !bloc.contains(e.relatedTarget)) basculer(false);
  });
})();
