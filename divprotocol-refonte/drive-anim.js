/* DIV Drive — animation de l'illustration en calques.
   GSAP + ScrollTrigger. Narration : dossier → ouverture → fichiers → chiffrement
   → partage → collaboration → appareils → lien → liaisons → textes → lévitation. */
(function () {
  "use strict";

  var root = document.getElementById("dviz");
  if (!root || !window.gsap) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var q = function (k) { return root.querySelector('[data-k="' + k + '"]'); };
  var pick = function (list) { return list.map(q).filter(Boolean); };

  /* chaque liaison se déploie depuis le bord de sa carte */
  var LINKS = [
    ["data",   "0% 0%"],   ["share",  "50% 0%"],   ["collab", "100% 100%"],
    ["links",  "100% 50%"], ["access", "0% 100%"], ["files",  "100% 100%"]
  ];
  var FILES   = ["f-white", "f-image", "f-doc", "f-video"];
  var copyBtn = root.querySelector(".dviz__copy");
  var toast   = root.querySelector(".dviz__toast");

  /* ---- mouvement réduit : de simples fondus, aucun déplacement ---- */
  if (reduce) {
    var order = ["ground", "folder-bk", "folder", "f-white", "f-image", "f-doc", "f-video",
      "lock", "plane", "collab", "devices", "pdf", "green", "vidblue", "link",
      "c-data", "t-data", "c-share", "t-share", "c-collab", "t-collab",
      "c-links", "t-links", "c-access", "t-access", "c-files", "t-files"];
    gsap.set(root.querySelectorAll(".dl"), { opacity: 0 });
    gsap.to(pick(order), {
      opacity: 1, duration: .5, stagger: .055, ease: "none",
      scrollTrigger: { trigger: root, start: "top 80%" }
    });
    bindCopy();
    return;
  }

  /* ---- état de départ ---- */
  gsap.set(root.querySelectorAll(".dl"), { opacity: 0 });
  LINKS.forEach(function (c) {
    gsap.set(q("c-" + c[0]), { transformOrigin: c[1], scale: .15 });
  });

  var E = "power3.out";
  /* la séquence se rejoue à chaque fois que la section revient dans le champ */
  var tl = gsap.timeline({
    paused: true,
    defaults: { ease: E },
    scrollTrigger: {
      trigger: root, start: "top 78%", end: "bottom 12%",
      onEnter:      function () { tl.play(0); },
      onEnterBack:  function () { tl.play(0); },
      onLeave:      function () { tl.pause(0); },
      onLeaveBack:  function () { tl.pause(0); }
    }
  });

  /* 1 · le dossier arrive */
  tl.to(pick(["ground"]), { opacity: 1, duration: .9, ease: "power2.out" }, 0)
    .fromTo(pick(["folder-bk", "folder"]),
      { opacity: 0, scale: .94, y: 30 },
      { opacity: 1, scale: 1, y: 0, duration: .8, stagger: .06 }, .05);

  /* 2 · légère ouverture du rabat avant */
  tl.fromTo(pick(["folder"]),
    { rotate: 0 },
    { rotate: -1.1, duration: .5, ease: "power2.inOut", yoyo: true, repeat: 1 }, .6);

  /* 3 · les fichiers sortent du dossier, l'un après l'autre */
  tl.fromTo(pick(FILES),
    { opacity: 0, y: 25, scale: .95 },
    { opacity: 1, y: 0, scale: 1, duration: .62, stagger: .1 }, .72);

  /* 4 · le cadenas — chiffrement */
  tl.fromTo(pick(["lock"]),
    { opacity: 0, x: 20, y: 15, scale: .95 },
    { opacity: 1, x: 0, y: 0, scale: 1, duration: .75 }, 1.02);

  /* 5 · partage sécurisé */
  tl.fromTo(pick(["plane"]),
    { opacity: 0, y: 34, scale: .95 },
    { opacity: 1, y: 0, scale: 1, duration: .72 }, 1.2);

  /* 6 · collaboration */
  tl.fromTo(pick(["collab"]),
    { opacity: 0, scale: .92 },
    { opacity: 1, scale: 1, duration: .66 }, 1.34);

  /* 7 · appareils, depuis le bas gauche */
  tl.fromTo(pick(["devices"]),
    { opacity: 0, x: -18, y: 24, scale: .95 },
    { opacity: 1, x: 0, y: 0, scale: 1, duration: .78 }, 1.46);

  /* 8 · les fichiers du bas */
  tl.fromTo(pick(["pdf", "green", "vidblue"]),
    { opacity: 0, y: 22, scale: .96 },
    { opacity: 1, y: 0, scale: 1, duration: .6, stagger: .09 }, 1.56);

  /* 9 · le lien de partage sort horizontalement */
  tl.fromTo(pick(["link"]),
    { opacity: 0, x: -30 },
    { opacity: 1, x: 0, duration: .7 }, 1.72);

  /* 10 · liaisons : le trait se déploie, puis la carte suit ~100 ms après */
  LINKS.forEach(function (c, i) {
    var at = 1.92 + i * 0.12;
    tl.to(q("c-" + c[0]),
      { opacity: 1, scale: 1, duration: .42, ease: "power2.out" }, at)
      .fromTo(q("t-" + c[0]),
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: .45 }, at + .14);
  });

  /* 11 · micro-lévitation, une durée différente par objet */
  var FLOAT = [
    ["plane",   3.5, 5.0], ["collab",  2.4, 6.0], ["devices", 3.2, 5.5],
    ["lock",    2.2, 6.4], ["link",    1.8, 4.6], ["f-video", 1.6, 5.8],
    ["f-doc",   1.4, 6.6], ["f-image", 1.5, 5.2], ["pdf",     1.6, 6.2],
    ["green",   1.4, 5.6], ["vidblue", 1.7, 6.8]
  ];
  var floating = false;
  tl.call(function () {
    if (floating) return;          /* une seule fois, même si la séquence rejoue */
    floating = true;
    FLOAT.forEach(function (f) {
      var el = q(f[0]);
      if (!el) return;
      gsap.to(el, {
        y: "+=" + f[1] * 2, duration: f[2], ease: "sine.inOut",
        yoyo: true, repeat: -1, startAt: { y: -f[1] }
      });
    });
  }, null, 2.7);

  /* ---- parallaxe souris, desktop uniquement ---- */
  gsap.matchMedia().add("(min-width: 1024px) and (pointer: fine)", function () {
    var DEPTH = {
      "ground": .15, "folder-bk": .35, "f-white": .5, "f-image": .6, "f-doc": .65,
      "f-video": .7, "folder": .8, "link": 1, "lock": .9, "plane": 1,
      "collab": .9, "devices": 1, "pdf": 1, "green": 1, "vidblue": 1
    };
    var setters = {}, damp = 1;
    Object.keys(DEPTH).forEach(function (k) {
      var el = q(k); if (el) setters[k] = gsap.quickTo(el, "x", { duration: .9, ease: "power3.out" });
    });
    var ys = {};
    Object.keys(DEPTH).forEach(function (k) {
      var el = q(k); if (el) ys[k] = gsap.quickTo(el, "rotate", { duration: 1.1, ease: "power3.out" });
    });

    function onMove(e) {
      var r = root.getBoundingClientRect();
      var nx = (e.clientX - r.left) / r.width - .5;
      Object.keys(setters).forEach(function (k) {
        setters[k](nx * 8 * DEPTH[k] * damp);
        ys[k](nx * .35 * DEPTH[k] * damp);
      });
    }
    window.addEventListener("mousemove", onMove, { passive: true });

    /* 13 · en sortie de vue, la profondeur s'estompe au lieu de couper net */
    var st = ScrollTrigger.create({
      trigger: root, start: "top 20%", end: "bottom top",
      onUpdate: function (self) { damp = 1 - self.progress * .8; }
    });

    return function () {
      window.removeEventListener("mousemove", onMove);
      st.kill();
      Object.keys(setters).forEach(function (k) { setters[k](0); ys[k](0); });
    };
  });

  /* ---- hover sur les objets au premier plan ---- */
  ["lock", "plane", "collab", "devices", "pdf", "green", "vidblue"].forEach(function (k) {
    var el = q(k); if (!el) return;
    el.classList.add("hit");
    var base = null;
    el.addEventListener("mouseenter", function () {
      base = gsap.getProperty(el, "y");
      gsap.to(el, { scale: 1.025, duration: .3, ease: "power2.out", overwrite: "auto" });
    });
    el.addEventListener("mouseleave", function () {
      gsap.to(el, { scale: 1, duration: .35, ease: "power2.out", overwrite: "auto" });
    });
  });

  bindCopy();

  /* ---- bouton Copier ---- */
  function bindCopy() {
    if (!copyBtn || !toast) return;
    var busy = false;
    copyBtn.addEventListener("click", function () {
      if (busy) return;
      busy = true;
      var url = copyBtn.getAttribute("data-url");
      var done = function () {
        toast.textContent = "✓ Copié";
        if (reduce) {
          toast.style.opacity = 1;
          setTimeout(function () { toast.style.opacity = 0; busy = false; }, 1500);
          return;
        }
        gsap.timeline()
          .to(toast, { opacity: 1, y: 0, duration: .28, ease: "back.out(2)" })
          .to(toast, { opacity: 0, y: 6, duration: .3, ease: "power2.in",
            delay: 1.5, onComplete: function () { busy = false; } });
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, done);
      } else { done(); }
    });
  }
})();
