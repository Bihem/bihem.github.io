/* ==========================================================================
   DIV Protocol — scène 3D du hero (Three.js r128)
   Le boîtier, la plateforme, le nuage et les fichiers sont des volumes réels.
   Au scroll, les fichiers sont absorbés par le boîtier.
   Repli : si WebGL manque ou si l'utilisateur réduit les animations,
   la composition 2D reste affichée et ce module ne démarre pas.
   ========================================================================== */
(function () {
  "use strict";

  var stage = document.getElementById("stage");
  var canvas = document.getElementById("hero3d");
  if (!stage || !canvas || !window.THREE) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  try {
    var probe = document.createElement("canvas");
    if (!(probe.getContext("webgl") || probe.getContext("experimental-webgl"))) return;
  } catch (e) { return; }

  var T = THREE;

  /* ---------------------------------------------------------------- outils */
  function roundedShape(w, h, r) {
    var s = new T.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y);
    s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }
  function roundedBox(w, h, d, r, bev) {
    bev = bev || 0.035;
    var g = new T.ExtrudeGeometry(roundedShape(w, h, r), {
      depth: Math.max(0.01, d - bev * 2), bevelEnabled: true,
      bevelThickness: bev, bevelSize: bev, bevelSegments: 3, curveSegments: 14
    });
    g.center();
    return g;
  }
  function tex(draw, w, h) {
    var c = document.createElement("canvas");
    c.width = w; c.height = h || w;
    draw(c.getContext("2d"), c.width, c.height);
    var t = new T.CanvasTexture(c);
    t.encoding = T.sRGBEncoding;
    t.anisotropy = 4;
    return t;
  }
  function decal(texture, w, h) {
    return new T.Mesh(
      new T.PlaneGeometry(w, h),
      new T.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false })
    );
  }
  function rrect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  /* ---------------------------------------------------------------- scène */
  var renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  var LIGHT = innerWidth < 760;
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, LIGHT ? 1.6 : 2));
  renderer.outputEncoding = T.sRGBEncoding;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  renderer.shadowMap.enabled = !LIGHT;
  renderer.shadowMap.type = T.PCFSoftShadowMap;

  var scene = new T.Scene();
  var camera = new T.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0.25, 2.45, 10.6);
  camera.lookAt(0, 1.05, 0);

  scene.add(new T.HemisphereLight(0xffffff, 0xd6e0f2, 0.42));
  var key = new T.DirectionalLight(0xffffff, 1.15);
  key.position.set(4.5, 8.5, 5.5);
  key.castShadow = true;
  key.shadow.mapSize.set(LIGHT ? 512 : 1024, LIGHT ? 512 : 1024);
  key.shadow.camera.near = 1; key.shadow.camera.far = 26;
  key.shadow.camera.left = -6; key.shadow.camera.right = 6;
  key.shadow.camera.top = 6; key.shadow.camera.bottom = -6;
  key.shadow.bias = -0.0012;
  key.shadow.radius = 4;
  scene.add(key);
  var rim = new T.DirectionalLight(0x93b8ff, 0.38);
  rim.position.set(-6, 3.5, -5);
  scene.add(rim);
  var slotLight = new T.PointLight(0x8b5cff, 0, 6, 2);
  slotLight.position.set(0, 0.9, 0);
  scene.add(slotLight);

  var world = new T.Group();
  scene.add(world);

  /* ------------------------------------------------------ ombre au sol */
  var ground = new T.Mesh(
    new T.PlaneGeometry(24, 24),
    new T.ShadowMaterial({ opacity: 0.17 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.62;
  ground.receiveShadow = true;
  world.add(ground);

  /* ------------------------------------------------------ le boîtier */
  var boxG = new T.Group();
  world.add(boxG);

  var shell = new T.Mesh(
    roundedBox(3.5, 3.5, 1.02, 0.34),
    new T.MeshPhysicalMaterial({ color: 0x14161b, roughness: 0.3, metalness: 0.4, clearcoat: 0.9, clearcoatRoughness: 0.18 })
  );
  shell.rotation.x = -Math.PI / 2;
  shell.position.y = -0.1;
  shell.castShadow = true; shell.receiveShadow = true;
  boxG.add(shell);

  /* creux supérieur */
  var well = new T.Mesh(
    roundedBox(2.05, 2.05, 0.34, 0.2),
    new T.MeshPhysicalMaterial({ color: 0x0d0f14, roughness: 0.5, metalness: 0.2 })
  );
  well.rotation.x = -Math.PI / 2;
  well.position.y = 0.24;
  boxG.add(well);

  /* halo violet dans le creux */
  var glow = new T.Mesh(
    new T.PlaneGeometry(1.95, 1.95),
    new T.MeshBasicMaterial({
      color: 0x7c3aff, transparent: true, opacity: 0.55,
      blending: T.AdditiveBlending, depthWrite: false,
      map: tex(function (c, w, h) {
        var g = c.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
        g.addColorStop(0, "rgba(255,255,255,1)");
        g.addColorStop(0.45, "rgba(180,150,255,.55)");
        g.addColorStop(1, "rgba(80,0,255,0)");
        c.fillStyle = g; c.fillRect(0, 0, w, h);
      }, 256)
    })
  );
  glow.rotation.x = -Math.PI / 2;
  glow.position.y = 0.418;
  boxG.add(glow);

  /* écusson DV, émissif */
  var crest = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.strokeStyle = "#CDB4FF"; c.lineWidth = w * 0.052;
    c.lineJoin = "round"; c.lineCap = "round";
    c.beginPath();
    c.moveTo(w * 0.5, h * 0.13);
    c.lineTo(w * 0.84, h * 0.28);
    c.lineTo(w * 0.84, h * 0.55);
    c.quadraticCurveTo(w * 0.84, h * 0.82, w * 0.5, h * 0.92);
    c.quadraticCurveTo(w * 0.16, h * 0.82, w * 0.16, h * 0.55);
    c.lineTo(w * 0.16, h * 0.28);
    c.closePath(); c.stroke();
    c.lineWidth = w * 0.062;
    c.beginPath(); c.moveTo(w * 0.38, h * 0.35); c.lineTo(w * 0.38, h * 0.66); c.stroke();
    c.beginPath();
    c.moveTo(w * 0.56, h * 0.34); c.lineTo(w * 0.56, h * 0.55);
    c.quadraticCurveTo(w * 0.56, h * 0.72, w * 0.70, h * 0.72);
    c.stroke();
  }, 384), 1.42, 1.42);
  crest.rotation.x = -Math.PI / 2;
  crest.position.y = 0.432;
  boxG.add(crest);

  /* gravure « DIV Protocol » sur la joue avant-gauche */
  var label = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.fillStyle = "rgba(226,230,238,.72)";
    c.font = "600 " + Math.round(h * 0.5) + "px Inter, Helvetica, Arial, sans-serif";
    c.textBaseline = "middle";
    c.fillText("DIV Protocol", w * 0.04, h * 0.56);
  }, 512, 128), 1.5, 0.375);
  label.position.set(-0.86, -0.2, 1.79);
  label.rotation.y = 0;
  boxG.add(label);

  /* témoin lumineux */
  var led = new T.Mesh(
    new T.PlaneGeometry(0.16, 0.05),
    new T.MeshBasicMaterial({ color: 0x63b3ff })
  );
  led.position.set(1.16, -0.16, 1.79);
  boxG.add(led);

  /* ------------------------------------------------------ la plateforme */
  var platG = new T.Group();
  platG.position.y = 1.28;
  world.add(platG);

  var slab = new T.Mesh(
    roundedBox(2.62, 2.62, 0.22, 0.3),
    new T.MeshPhysicalMaterial({
      color: 0x2f7bff, roughness: 0.12, metalness: 0.05,
      transparent: true, opacity: 0.72,
      emissive: 0x1a4ee0, emissiveIntensity: 0.55,
      clearcoat: 1, clearcoatRoughness: 0.08
    })
  );
  slab.rotation.x = -Math.PI / 2;
  slab.castShadow = true;
  platG.add(slab);

  /* semis de points évoquant une carte */
  var dots = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.fillStyle = "rgba(190,225,255,.95)";
    var seed = 7;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var i = 0; i < 1500; i++) {
      var x = rnd(), y = rnd();
      var cx = Math.abs(x - 0.5), cy = Math.abs(y - 0.5);
      /* bandes horizontales irrégulières : lecture « continents » sans dessiner de carte */
      var band = Math.sin(x * 11 + Math.cos(y * 7) * 2) * 0.5 + 0.5;
      if (band < 0.42 || cy > 0.36 || cx > 0.46) continue;
      var r = 1.3 + rnd() * 1.1;
      c.beginPath(); c.arc(x * w, y * h, r, 0, 6.283); c.fill();
    }
  }, 512), 2.34, 2.34);
  dots.rotation.x = -Math.PI / 2;
  dots.position.y = 0.115;
  dots.material.opacity = 1;
  platG.add(dots);

  /* ------------------------------------------------------ le nuage */
  var cloudG = new T.Group();
  cloudG.position.set(0.08, 2.5, 0.05);
  world.add(cloudG);
  var puffMat = new T.MeshPhysicalMaterial({ color: 0xeef4fd, roughness: 0.42, metalness: 0, clearcoat: 0.5, clearcoatRoughness: 0.3 });
  [[-0.52, -0.06, 0, 0.46], [0.03, 0.16, 0.02, 0.58], [0.56, -0.04, -0.02, 0.44], [0.16, -0.2, 0.16, 0.42], [-0.2, -0.18, -0.14, 0.4]]
    .forEach(function (p) {
      var s = new T.Mesh(new T.SphereGeometry(p[3], 28, 22), puffMat);
      s.position.set(p[0], p[1], p[2]);
      s.castShadow = true;
      cloudG.add(s);
    });
  var arrowShape = new T.Shape();
  arrowShape.moveTo(0, 0.52); arrowShape.lineTo(0.34, 0.1); arrowShape.lineTo(0.15, 0.1);
  arrowShape.lineTo(0.15, -0.5); arrowShape.lineTo(-0.15, -0.5); arrowShape.lineTo(-0.15, 0.1);
  arrowShape.lineTo(-0.34, 0.1); arrowShape.closePath();
  var arrow = new T.Mesh(
    new T.ExtrudeGeometry(arrowShape, { depth: 0.16, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 2 }),
    new T.MeshPhysicalMaterial({ color: 0x2f7bff, roughness: 0.25, metalness: 0.1, clearcoat: 0.8 })
  );
  arrow.position.set(0, -0.1, 0.66);
  arrow.scale.setScalar(1.15);
  arrow.castShadow = true;
  cloudG.add(arrow);

  /* ------------------------------------------------------ les fichiers */
  var FILES = [
    { c: 0xF0A020, x:  1.62, y: 3.30, z: 0.25, rz: -0.20, kind: "folder" },
    { c: 0xEDF2FA, x: -1.95, y: 2.92, z: 0.60, rz:  0.17, kind: "doc" },
    { c: 0xDE3B2F, x: -2.42, y: 1.45, z: 1.05, rz: -0.13, kind: "video" },
    { c: 0x6D28D9, x:  2.42, y: 1.72, z: 0.85, rz:  0.21, kind: "image" }
  ];
  var glyphs = {
    folder: function (c, w, h) {
      c.clearRect(0, 0, w, h);
      c.fillStyle = "rgba(255,255,255,.92)";
      rrect(c, w * 0.16, h * 0.3, w * 0.68, h * 0.42, w * 0.06); c.fill();
      c.fillStyle = "rgba(255,255,255,.6)";
      rrect(c, w * 0.16, h * 0.24, w * 0.32, h * 0.1, w * 0.04); c.fill();
    },
    doc: function (c, w, h) {
      c.clearRect(0, 0, w, h);
      c.fillStyle = "#2F7BFF";
      [0.34, 0.46, 0.58].forEach(function (y, i) {
        rrect(c, w * 0.2, h * y, w * (i === 2 ? 0.36 : 0.58), h * 0.055, h * 0.03); c.fill();
      });
    },
    video: function (c, w, h) {
      c.clearRect(0, 0, w, h);
      c.fillStyle = "#fff";
      c.beginPath();
      c.moveTo(w * 0.4, h * 0.34); c.lineTo(w * 0.68, h * 0.5); c.lineTo(w * 0.4, h * 0.66);
      c.closePath(); c.fill();
    },
    image: function (c, w, h) {
      c.clearRect(0, 0, w, h);
      c.fillStyle = "#fff";
      c.beginPath(); c.arc(w * 0.66, h * 0.36, w * 0.075, 0, 6.283); c.fill();
      c.beginPath();
      c.moveTo(w * 0.2, h * 0.68); c.lineTo(w * 0.4, h * 0.44); c.lineTo(w * 0.54, h * 0.6);
      c.lineTo(w * 0.63, h * 0.5); c.lineTo(w * 0.8, h * 0.68);
      c.closePath(); c.fill();
    }
  };

  var files = FILES.map(function (f) {
    var g = new T.Group();
    var card = new T.Mesh(
      roundedBox(1.12, 1.34, 0.16, 0.16),
      new T.MeshPhysicalMaterial({
        color: f.c, roughness: 0.24, metalness: 0.06,
        clearcoat: 0.9, clearcoatRoughness: 0.12, transparent: true
      })
    );
    card.castShadow = true;
    g.add(card);
    var gl = decal(tex(glyphs[f.kind], 256), 1.12, 1.34);
    gl.position.z = 0.083;
    g.add(gl);
    g.position.set(f.x, f.y, f.z);
    g.rotation.set(0.06, -0.18, f.rz);
    g.userData = { home: g.position.clone(), rot: g.rotation.clone(), ph: Math.random() * 6.283, card: card, glyph: gl };
    world.add(g);
    return g;
  });

  /* ---------------------------------------------------------------- moteur */
  var TARGET = new T.Vector3(0, 0.42, 0);
  var p = 0, mx = 0, my = 0, tmx = 0, tmy = 0, running = true, S0 = 0, S1 = 1;

  function resize() {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    /* la scène garde la même présence quel que soit le format */
    camera.position.z = 10.6 * Math.max(1, 1.55 / camera.aspect);
    camera.lookAt(0, 1.05, 0);
    camera.updateProjectionMatrix();

    var vh = innerHeight;
    var slot = stage.getBoundingClientRect().top + scrollY + h * 0.46;
    S0 = Math.max(0, slot - vh * 0.92);
    S1 = slot - vh * 0.42;
    if (S1 - S0 < 180) S1 = S0 + 180;
  }

  function onScroll() {
    var v = (scrollY - S0) / (S1 - S0);
    p = v < 0 ? 0 : v > 1 ? 1 : v;
  }

  stage.addEventListener("pointermove", function (e) {
    var r = stage.getBoundingClientRect();
    tmx = (e.clientX - r.left) / r.width - 0.5;
    tmy = (e.clientY - r.top) / r.height - 0.5;
  });
  stage.addEventListener("pointerleave", function () { tmx = 0; tmy = 0; });

  var io = new IntersectionObserver(function (en) {
    running = en[0].isIntersecting;
    if (running) loop();
  }, { rootMargin: "120px" });
  io.observe(stage);

  var t0 = performance.now();
  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    var t = (performance.now() - t0) / 1000;
    var e = p * p * (3 - 2 * p);          /* lissage de l'absorption */

    mx += (tmx - mx) * 0.06;
    my += (tmy - my) * 0.06;
    world.rotation.y = Math.sin(t * 0.12) * 0.06 + mx * 0.22;
    world.rotation.x = my * 0.08;

    /* le nuage s'élève et s'efface, la plateforme redescend dans le boîtier */
    cloudG.position.y = 2.5 + Math.sin(t * 0.75) * 0.09 + e * 1.1;
    cloudG.scale.setScalar(Math.max(0.001, 1 - e * 0.85));
    cloudG.children.forEach(function (m) {
      if (!m.material.transparent) { m.material.transparent = true; }
      m.material.opacity = 1 - e;
    });
    arrow.position.y = -0.1 + Math.sin(t * 1.6) * 0.07;

    platG.position.y = 1.28 + Math.sin(t * 0.6 + 1) * 0.055 * (1 - e) - e * 0.66;
    platG.rotation.y = t * 0.09;
    slab.material.opacity = 0.72 * (1 - e * 0.82);
    slab.material.emissiveIntensity = 0.55 + e * 1.6;

    /* les fichiers convergent vers la fente et sont absorbés */
    files.forEach(function (g, i) {
      var d = g.userData;
      var k = Math.min(1, Math.max(0, (e - i * 0.045) / (1 - i * 0.045)));
      var ke = k * k * (3 - 2 * k);
      var float = Math.sin(t * 0.8 + d.ph) * 0.11 * (1 - ke);
      g.position.lerpVectors(d.home, TARGET, ke);
      g.position.y += float;
      g.scale.setScalar(Math.max(0.001, 1 - 0.92 * ke));
      g.rotation.set(
        d.rot.x + Math.sin(t * 0.5 + d.ph) * 0.05 * (1 - ke),
        d.rot.y + ke * 1.1,
        d.rot.z * (1 - ke) + ke * 0.5
      );
      var o = 1 - Math.pow(ke, 1.8);
      d.card.material.opacity = o;
      d.glyph.material.opacity = o;
    });

    /* le boîtier encaisse : le halo monte quand tout est avalé */
    var pulse = Math.pow(e, 2.2);
    glow.material.opacity = 0.5 + pulse * 0.5 + Math.sin(t * 1.4) * 0.03;
    crest.material.opacity = 0.85 + pulse * 0.15;
    slotLight.intensity = 0.6 + pulse * 3.4;
    boxG.position.y = pulse * -0.05;
    boxG.scale.setScalar(1 + pulse * 0.02);

    renderer.render(scene, camera);
  }

  addEventListener("resize", function () { resize(); onScroll(); });
  addEventListener("scroll", onScroll, { passive: true });

  resize(); onScroll();
  stage.classList.add("is-3d");
  loop();
})();
