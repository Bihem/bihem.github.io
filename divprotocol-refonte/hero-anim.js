/* ==========================================================================
   DIV Protocol — animation du hero
   L'illustration d'origine est intacte : elle est simplement découpée en
   calques, remontés à leurs coordonnées exactes. Au repos, le rendu est
   pixel pour pixel celui du fichier source.
   ========================================================================== */
(function () {
  "use strict";

  var scene = document.getElementById("scene");
  var stage = document.getElementById("stage");
  if (!scene || !stage) return;

  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var layers = [].slice.call(scene.querySelectorAll(".ly"));
  var bloom  = scene.querySelector(".bloom");
  if (!layers.length) return;

  /* fente lumineuse du boîtier, en % de l'illustration */
  var SLOT_X = 50.2, SLOT_Y = 77.2;

  /* profondeur (parallaxe), amplitude et période de la dérive au repos */
  var CFG = {
    box:    { d: 0.09, amp: 0,  per: 0,   mode: "box"  },
    deck:   { d: 0.20, amp: 7,  per: 5.4, mode: "deck" },
    misc:   { d: 0.12, amp: 0,  per: 0,   mode: "pin", side: 0 },
    doc:    { d: 0.34, amp: 11, per: 5.2, rot:  1.3, mode: "file" },
    video:  { d: 0.41, amp: 13, per: 4.4, rot: -1.5, mode: "file" },
    image:  { d: 0.38, amp: 12, per: 6.0, rot:  1.7, mode: "file" },
    folder: { d: 0.30, amp: 9,  per: 5.8, rot: -1.2, mode: "file" },
    pill1:  { d: 0.20, amp: 5,  per: 6.2, mode: "pin", side: -1 },
    pill2:  { d: 0.20, amp: 5,  per: 5.4, mode: "pin", side:  1 },
    pill3:  { d: 0.22, amp: 6,  per: 6.6, mode: "pin", side:  1 },
    pill4:  { d: 0.22, amp: 6,  per: 5.0, mode: "pin", side: -1 },
    pill5:  { d: 0.24, amp: 5,  per: 5.9, mode: "pin", side:  1 },
    pill6:  { d: 0.24, amp: 6,  per: 6.4, mode: "pin", side: -1 }
  };
  /* ordre d'apparition : du fond vers l'avant */
  var ORDER = ["deck","box","misc","folder","doc","video","image",
               "pill1","pill2","pill3","pill4","pill5","pill6"];

  var items = layers.map(function (el) {
    var k = el.dataset.k, c = CFG[k] || CFG.box;
    var cs = el.style;
    return {
      el: el, k: k, c: c,
      cx: parseFloat(cs.left) + parseFloat(cs.width) / 2,
      cy: 0,                                   /* mesuré après chargement */
      ph: (ORDER.indexOf(k) % 7) * 0.9 + (c.per || 5) * 0.13,
      i:  Math.max(0, ORDER.indexOf(k))
    };
  });

  function measure() {
    var H = scene.clientHeight || 1;
    items.forEach(function (it) {
      it.cy = (it.el.offsetTop + it.el.offsetHeight / 2) / H * 100;
      it.dx = SLOT_X - it.cx;
      it.dy = SLOT_Y - it.cy;
    });
  }

  /* ------------------------------------------------------- pilotage ---- */
  var S0 = 0, S1 = 1, p = 0, mx = 0, my = 0, tmx = 0, tmy = 0;
  function anchors() {
    var h = stage.offsetHeight, vh = innerHeight;
    var slot = stage.getBoundingClientRect().top + scrollY + h * (SLOT_Y / 100);
    S0 = Math.max(0, slot - vh * 0.95);
    S1 = slot - vh * 0.42;
    if (S1 - S0 < 200) S1 = S0 + 200;
  }
  function onScroll() {
    var v = (scrollY - S0) / (S1 - S0);
    p = v < 0 ? 0 : v > 1 ? 1 : v;
  }

  if (!reduce) {
    stage.addEventListener("pointermove", function (e) {
      var r = stage.getBoundingClientRect();
      tmx = (e.clientX - r.left) / r.width - 0.5;
      tmy = (e.clientY - r.top) / r.height - 0.5;
    });
    stage.addEventListener("pointerleave", function () { tmx = 0; tmy = 0; });
  }

  /* ------------------------------------------------------- rendu ------- */
  var W = 1, H = 1, t0 = null, running = false, entered = 0;

  function sizes() { W = scene.clientWidth || 1; H = scene.clientHeight || 1; }
  function ease(x) { return x * x * (3 - 2 * x); }
  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }

  function frame(now) {
    if (!running) return;
    requestAnimationFrame(frame);
    if (t0 === null) t0 = now;
    var t = (now - t0) / 1000;
    var e = ease(p);
    var q = clamp01(p * 1.55);
    var pulse = Math.pow(e, 2.1);

    mx += (tmx - mx) * 0.05;
    my += (tmy - my) * 0.05;

    items.forEach(function (it) {
      var c = it.c;
      /* apparition : décalée du fond vers l'avant */
      var en = reduce ? 1 : ease(clamp01((t - it.i * 0.065) / 0.85));
      entered = Math.max(entered, en);

      var drift = reduce ? 0 : Math.sin(t * (6.283 / (c.per || 6)) + it.ph) * (c.amp || 0);
      var tx = mx * c.d * 44, ty = drift + my * c.d * 30;
      var sc = 0.965 + 0.035 * en, rot = 0, op = en;

      if (c.mode === "file") {
        var k = ease(clamp01((e - it.i * 0.02) / (1 - it.i * 0.02)));
        tx += it.dx / 100 * W * k;
        ty += it.dy / 100 * H * k;
        sc *= 1 - 0.94 * k;
        rot = (reduce ? 0 : Math.sin(t * 0.55 + it.ph) * (c.rot || 0) * (1 - k)) + k * 26;
        op *= 1 - Math.pow(k, 1.6);
      } else if (c.mode === "deck") {
        /* la plateforme et le nuage descendent dans le boîtier, qui les masque */
        ty += it.dy / 100 * H * 1.02 * e;
        sc *= 1 - 0.42 * e;
        op *= 1 - Math.pow(e, 2.4);
      } else if (c.mode === "pin") {
        tx += (c.side || 0) * 40 * q;
        ty += 10 * q;
        op *= 1 - q;
      } else {            /* le socle encaisse l'absorption */
        sc *= 1 + 0.018 * pulse;
        ty += 7 * pulse;
      }

      it.el.style.transform = "translate3d(" + tx.toFixed(2) + "px," + ty.toFixed(2) + "px,0) rotate(" + rot.toFixed(2) + "deg) scale(" + sc.toFixed(4) + ")";
      it.el.style.opacity = op.toFixed(3);
    });

    var shade = scene.querySelector(".shade");
    if (shade) {
      shade.style.opacity = (entered * (1 - 0.18 * pulse)).toFixed(3);
      shade.style.transform = "translate(-50%,-50%) scale(" + (1 + 0.05 * pulse).toFixed(3) + "," + (1 - 0.12 * pulse).toFixed(3) + ")";
    }
    if (bloom) {
      var breathe = reduce ? 0 : Math.sin(t * 1.25) * 0.05;
      bloom.style.opacity = (entered * (0.16 + 0.84 * pulse + breathe)).toFixed(3);
      bloom.style.transform = "translate(-50%,-50%) scale(" + (0.55 + 0.75 * e).toFixed(3) + ")";
    }

    if (reduce && p === 0 && t > 1.2) { running = false; }   /* rendu figé */
  }

  function boot() {
    sizes(); measure(); anchors(); onScroll();
    if (!running) { running = true; requestAnimationFrame(frame); }
  }

  new IntersectionObserver(function (en) {
    if (en[0].isIntersecting) { if (!running) { running = true; requestAnimationFrame(frame); } }
    else running = false;
  }, { rootMargin: "160px" }).observe(stage);

  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", function () { sizes(); measure(); anchors(); onScroll(); });

  var pending = layers.filter(function (l) { return !l.complete; }).length;
  if (pending) {
    layers.forEach(function (l) {
      l.addEventListener("load", function () { if (--pending <= 0) boot(); }, { once: true });
      l.addEventListener("error", function () { if (--pending <= 0) boot(); }, { once: true });
    });
    setTimeout(boot, 1800);          /* filet de sécurité */
  }
  boot();
})();
