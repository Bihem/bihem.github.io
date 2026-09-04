/* ==========================================================================
   DIV Protocol — hero 3D (Three.js r128)
   Reconstruction volumétrique de l'illustration de référence (1226 × 1283).
   Toutes les positions sont exprimées dans le repère de l'illustration puis
   converties en unités monde : 1 unité = largeur du boîtier / 3,5.
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

  /* --- repère de l'illustration -> repère monde ------------------------ */
  var PX = 3.5 / 570;              /* le boîtier fait 570 px pour 3,5 unités */
  var BOX_CX = 615, BOX_CY = 1040; /* centre du boîtier dans l'illustration  */
  function wx(px) { return (px - BOX_CX) * PX; }
  function wy(py) { return (BOX_CY - py) * PX - 0.10; }

  /* --- outils ---------------------------------------------------------- */
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
    bev = bev || 0.03;
    var g = new T.ExtrudeGeometry(roundedShape(w, h, r), {
      depth: Math.max(0.01, d - bev * 2), bevelEnabled: true,
      bevelThickness: bev, bevelSize: bev, bevelSegments: 3, curveSegments: 14
    });
    g.center(); return g;
  }
  function tex(draw, w, h) {
    var c = document.createElement("canvas");
    c.width = w; c.height = h || w;
    draw(c.getContext("2d"), c.width, c.height);
    var t = new T.CanvasTexture(c);
    t.encoding = T.sRGBEncoding; t.anisotropy = 4; return t;
  }
  function decal(texture, w, h) {
    return new T.Mesh(new T.PlaneGeometry(w, h),
      new T.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false }));
  }
  function rrect(c, x, y, w, h, r) {
    c.beginPath(); c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }

  /* --- rendu ----------------------------------------------------------- */
  var LIGHT = innerWidth < 760;
  var renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, LIGHT ? 1.6 : 2));
  renderer.outputEncoding = T.sRGBEncoding;
  renderer.toneMapping = T.LinearToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = !LIGHT;
  renderer.shadowMap.type = T.PCFSoftShadowMap;

  var scene = new T.Scene();
  /* longue focale : la lecture reste quasi isométrique, comme l'illustration */
  var camera = new T.PerspectiveCamera(24, 1, 0.5, 200);
  var LOOK = new T.Vector3(0, wy(642), 0);
  var DIST = 19.8, ELEV = 0.335;   /* ~19° au-dessus de l'horizon */

  scene.add(new T.HemisphereLight(0xffffff, 0xd6e0f2, 0.40));
  var key = new T.DirectionalLight(0xffffff, 0.92);
  key.position.set(5, 11, 7);
  key.castShadow = !LIGHT;
  key.shadow.mapSize.set(LIGHT ? 512 : 1024, LIGHT ? 512 : 1024);
  key.shadow.camera.near = 2; key.shadow.camera.far = 34;
  key.shadow.camera.left = -7; key.shadow.camera.right = 7;
  key.shadow.camera.top = 9; key.shadow.camera.bottom = -5;
  key.shadow.bias = -0.0013; key.shadow.radius = 4;
  scene.add(key);
  var rim = new T.DirectionalLight(0x9dbcff, 0.3);
  rim.position.set(-7, 4, -6);
  scene.add(rim);
  var slotLight = new T.PointLight(0x8b5cff, 0.6, 7, 2);
  slotLight.position.set(0, 0.9, 0);
  scene.add(slotLight);

  var world = new T.Group();
  scene.add(world);

  var ground = new T.Mesh(new T.PlaneGeometry(30, 30), new T.ShadowMaterial({ opacity: 0.15 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.64; ground.receiveShadow = true;
  world.add(ground);

  /* ------------------------------------------------------- le boîtier -- */
  var boxG = new T.Group(); world.add(boxG);

  var shell = new T.Mesh(roundedBox(3.5, 3.5, 1.02, 0.34),
    new T.MeshPhysicalMaterial({ color: 0x14161b, roughness: 0.3, metalness: 0.4, clearcoat: 0.9, clearcoatRoughness: 0.18 }));
  shell.rotation.x = -Math.PI / 2; shell.position.y = -0.1;
  shell.castShadow = true; shell.receiveShadow = true;
  boxG.add(shell);

  var well = new T.Mesh(roundedBox(2.05, 2.05, 0.34, 0.2),
    new T.MeshPhysicalMaterial({ color: 0x0c0e13, roughness: 0.52, metalness: 0.2 }));
  well.rotation.x = -Math.PI / 2; well.position.y = 0.24;
  boxG.add(well);

  var glow = new T.Mesh(new T.PlaneGeometry(2, 2), new T.MeshBasicMaterial({
    color: 0x7c3aff, transparent: true, opacity: 0.6, blending: T.AdditiveBlending, depthWrite: false,
    map: tex(function (c, w, h) {
      var g = c.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.42, "rgba(178,148,255,.6)");
      g.addColorStop(1, "rgba(80,0,255,0)");
      c.fillStyle = g; c.fillRect(0, 0, w, h);
    }, 256)
  }));
  glow.rotation.x = -Math.PI / 2; glow.position.y = 0.418;
  boxG.add(glow);

  var crest = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.strokeStyle = "#CDB4FF"; c.lineWidth = w * 0.052; c.lineJoin = "round"; c.lineCap = "round";
    c.beginPath();
    c.moveTo(w * 0.5, h * 0.13); c.lineTo(w * 0.84, h * 0.28); c.lineTo(w * 0.84, h * 0.55);
    c.quadraticCurveTo(w * 0.84, h * 0.82, w * 0.5, h * 0.92);
    c.quadraticCurveTo(w * 0.16, h * 0.82, w * 0.16, h * 0.55);
    c.lineTo(w * 0.16, h * 0.28); c.closePath(); c.stroke();
    c.lineWidth = w * 0.062;
    c.beginPath(); c.moveTo(w * 0.38, h * 0.35); c.lineTo(w * 0.38, h * 0.66); c.stroke();
    c.beginPath(); c.moveTo(w * 0.56, h * 0.34); c.lineTo(w * 0.56, h * 0.55);
    c.quadraticCurveTo(w * 0.56, h * 0.72, w * 0.70, h * 0.72); c.stroke();
  }, 384), 1.06, 1.06);
  crest.rotation.x = -Math.PI / 2; crest.position.y = 0.432;
  boxG.add(crest);

  var label = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.fillStyle = "rgba(228,232,240,.74)";
    c.font = "600 " + Math.round(h * 0.5) + "px Inter, Helvetica, Arial, sans-serif";
    c.textBaseline = "middle"; c.fillText("DIV Protocol", w * 0.04, h * 0.56);
  }, 512, 128), 1.5, 0.375);
  label.position.set(-0.86, -0.2, 1.79);
  boxG.add(label);
  var led = new T.Mesh(new T.PlaneGeometry(0.16, 0.05), new T.MeshBasicMaterial({ color: 0x63b3ff }));
  led.position.set(1.16, -0.16, 1.79);
  boxG.add(led);

  /* ---------------------------------------------------- la plateforme -- */
  var platG = new T.Group();
  var PLAT_Y = wy(790);
  platG.position.y = PLAT_Y;
  world.add(platG);

  var slab = new T.Mesh(roundedBox(2.66, 2.66, 0.24, 0.3),
    new T.MeshPhysicalMaterial({
      color: 0x2f7bff, roughness: 0.1, metalness: 0.04, transparent: true, opacity: 0.74,
      emissive: 0x1a4ee0, emissiveIntensity: 0.6, clearcoat: 1, clearcoatRoughness: 0.06
    }));
  slab.rotation.x = -Math.PI / 2; slab.castShadow = true;
  platG.add(slab);

  var dots = decal(tex(function (c, w, h) {
    c.clearRect(0, 0, w, h);
    c.fillStyle = "rgba(205,232,255,.98)";
    var seed = 11;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var i = 0; i < 1900; i++) {
      var x = rnd(), y = rnd();
      var band = Math.sin(x * 11 + Math.cos(y * 7) * 2) * 0.5 + 0.5;
      if (band < 0.42 || Math.abs(y - 0.5) > 0.34 || Math.abs(x - 0.5) > 0.44) continue;
      c.beginPath(); c.arc(x * w, y * h, 1.4 + rnd() * 1.1, 0, 6.283); c.fill();
    }
  }, 512), 2.38, 2.38);
  dots.rotation.x = -Math.PI / 2; dots.position.y = 0.125;
  platG.add(dots);

  /* faisceau entre la plateforme et le boîtier */
  var beamH = PLAT_Y - 0.42;
  var beam = new T.Mesh(
    new T.CylinderGeometry(1.02, 1.42, beamH, 32, 1, true),
    new T.MeshBasicMaterial({
      color: 0x5b8dff, transparent: true, opacity: 0.2, side: T.DoubleSide,
      blending: T.AdditiveBlending, depthWrite: false,
      map: tex(function (c, w, h) {
        var g = c.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, "rgba(255,255,255,.9)");
        g.addColorStop(1, "rgba(255,255,255,0)");
        c.fillStyle = g; c.fillRect(0, 0, w, h);
      }, 8, 128)
    })
  );
  beam.position.y = 0.42 + beamH / 2;
  world.add(beam);

  /* --------------------------------------------------------- le nuage -- */
  var cloudG = new T.Group();
  cloudG.position.set(wx(635), wy(640), 0.1);
  world.add(cloudG);
  var puffMat = new T.MeshPhysicalMaterial({ color: 0xeff4fd, roughness: 0.4, metalness: 0, clearcoat: 0.55, clearcoatRoughness: 0.28 });
  [[-0.5, -0.05, 0, 0.44], [0.02, 0.17, 0.02, 0.56], [0.54, -0.03, -0.02, 0.42],
   [0.15, -0.19, 0.15, 0.4], [-0.19, -0.17, -0.13, 0.38]].forEach(function (q) {
    var m = new T.Mesh(new T.SphereGeometry(q[3], 28, 22), puffMat.clone());
    m.position.set(q[0], q[1], q[2]); m.castShadow = true; cloudG.add(m);
  });
  var aS = new T.Shape();
  aS.moveTo(0, 0.5); aS.lineTo(0.33, 0.09); aS.lineTo(0.145, 0.09);
  aS.lineTo(0.145, -0.48); aS.lineTo(-0.145, -0.48); aS.lineTo(-0.145, 0.09);
  aS.lineTo(-0.33, 0.09); aS.closePath();
  var arrow = new T.Mesh(
    new T.ExtrudeGeometry(aS, { depth: 0.15, bevelEnabled: true, bevelThickness: 0.028, bevelSize: 0.028, bevelSegments: 2 }),
    new T.MeshPhysicalMaterial({ color: 0x3183ff, roughness: 0.22, metalness: 0.1, clearcoat: 0.85 }));
  arrow.position.set(0, -0.06, 0.42); arrow.scale.setScalar(1.02); arrow.castShadow = true;
  cloudG.add(arrow);

  /* ------------------------------------------------------ les fichiers - */
  var glyphs = {
    doc: function (c, w, h) {
      c.clearRect(0, 0, w, h); c.fillStyle = "#2F7BFF";
      [[0.30, 0.60], [0.42, 0.60], [0.54, 0.38]].forEach(function (r) {
        rrect(c, w * 0.2, h * r[0], w * r[1], h * 0.052, h * 0.028); c.fill();
      });
    },
    video: function (c, w, h) {
      c.clearRect(0, 0, w, h); c.fillStyle = "#fff";
      c.beginPath(); c.moveTo(w * 0.4, h * 0.33); c.lineTo(w * 0.7, h * 0.5);
      c.lineTo(w * 0.4, h * 0.67); c.closePath(); c.fill();
    },
    image: function (c, w, h) {
      c.clearRect(0, 0, w, h); c.fillStyle = "#fff";
      c.beginPath(); c.arc(w * 0.67, h * 0.35, w * 0.08, 0, 6.283); c.fill();
      c.beginPath(); c.moveTo(w * 0.17, h * 0.71); c.lineTo(w * 0.4, h * 0.42);
      c.lineTo(w * 0.55, h * 0.6); c.lineTo(w * 0.64, h * 0.49); c.lineTo(w * 0.83, h * 0.71);
      c.closePath(); c.fill();
    }
  };

  function card(w, h, color, kind, roll) {
    var g = new T.Group();
    var m = new T.Mesh(roundedBox(w, h, 0.17, 0.13),
      new T.MeshPhysicalMaterial({ color: color, roughness: 0.24, metalness: 0.05, clearcoat: 0.92, clearcoatRoughness: 0.1, transparent: true }));
    m.castShadow = true; g.add(m);
    var d = decal(tex(glyphs[kind], 256), w, h); d.position.z = 0.088; g.add(d);
    g.userData = { parts: [m, d], roll: roll };
    return g;
  }

  /* dossier : deux volets, comme dans l'illustration */
  function folder(w, roll) {
    var g = new T.Group();
    var back = new T.Mesh(roundedBox(w, w * 0.78, 0.15, 0.1),
      new T.MeshPhysicalMaterial({ color: 0xD98008, roughness: 0.3, metalness: 0.05, clearcoat: 0.8, transparent: true }));
    back.position.set(0, w * 0.09, -0.07);
    var front = new T.Mesh(roundedBox(w, w * 0.62, 0.17, 0.1),
      new T.MeshPhysicalMaterial({ color: 0xF5A623, roughness: 0.26, metalness: 0.05, clearcoat: 0.9, transparent: true }));
    front.position.set(0, -w * 0.06, 0.06);
    var tab = new T.Mesh(roundedBox(w * 0.42, w * 0.14, 0.14, 0.05),
      new T.MeshPhysicalMaterial({ color: 0xD98B0B, roughness: 0.3, metalness: 0.05, clearcoat: 0.8, transparent: true }));
    tab.position.set(-w * 0.28, w * 0.44, -0.07);
    back.castShadow = front.castShadow = true;
    g.add(back, tab, front);
    g.userData = { parts: [back, tab, front], roll: roll };
    return g;
  }

  var files = [
    { o: folder(1.52, -0.18), px: 630, py: 200, z: 0.30 },
    { o: card(0.86, 1.12, 0xF2F5FB, "doc", 0.16), px: 510, py: 345, z: 0.55 },
    { o: card(0.92, 1.10, 0xE23B2E, "video", -0.12), px: 462, py: 505, z: 0.85 },
    { o: card(1.00, 1.16, 0x7C3AED, "image", 0.20), px: 770, py: 430, z: 0.60 }
  ].map(function (f, i) {
    var g = f.o;
    g.position.set(wx(f.px), wy(f.py), f.z);
    g.userData.home = g.position.clone();
    g.userData.ph = i * 1.6;
    world.add(g);
    return g;
  });

  /* ---------------------------------------------------------- moteur --- */
  var TARGET = new T.Vector3(0, 0.42, 0);
  var p = 0, mx = 0, my = 0, tmx = 0, tmy = 0, running = true, S0 = 0, S1 = 1;
  var camPos = new T.Vector3();

  function resize() {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    /* le cadrage suit le rapport de l'illustration (1226/1283) */
    var d = DIST * Math.max(1, 0.9556 / camera.aspect);
    camera.position.set(0, LOOK.y + d * Math.sin(ELEV), d * Math.cos(ELEV));
    camera.lookAt(LOOK);
    camera.updateProjectionMatrix();
    camera.getWorldPosition(camPos);

    var vh = innerHeight;
    var slot = stage.getBoundingClientRect().top + scrollY + h * 0.78;
    S0 = Math.max(0, slot - vh * 0.95);
    S1 = slot - vh * 0.42;
    if (S1 - S0 < 200) S1 = S0 + 200;
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

  new IntersectionObserver(function (en) {
    running = en[0].isIntersecting;
    if (running) loop();
  }, { rootMargin: "140px" }).observe(stage);

  var t0 = performance.now();
  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    var t = (performance.now() - t0) / 1000;
    var e = p * p * (3 - 2 * p);

    mx += (tmx - mx) * 0.055; my += (tmy - my) * 0.055;
    world.rotation.y = Math.sin(t * 0.11) * 0.045 + mx * 0.16;
    world.rotation.x = my * 0.055;

    cloudG.position.y = wy(640) + Math.sin(t * 0.7) * 0.08 + e * 1.2;
    cloudG.scale.setScalar(Math.max(0.001, 1 - e * 0.9));
    cloudG.children.forEach(function (m) { m.material.transparent = true; m.material.opacity = 1 - e; });
    arrow.position.y = -0.08 + Math.sin(t * 1.5) * 0.07;

    platG.position.y = PLAT_Y + Math.sin(t * 0.55 + 1) * 0.05 * (1 - e) - e * (PLAT_Y - 0.62);
    platG.rotation.y = t * 0.085;
    slab.material.opacity = 0.74 * (1 - e * 0.85);
    slab.material.emissiveIntensity = 0.6 + e * 1.7;
    dots.material.opacity = 1 - e;
    beam.material.opacity = 0.2 * (1 - e) + Math.sin(t * 0.9) * 0.015;
    beam.scale.y = Math.max(0.02, 1 - e);
    beam.position.y = 0.42 + (beamH * beam.scale.y) / 2;

    files.forEach(function (g, i) {
      var d = g.userData;
      var k = Math.min(1, Math.max(0, (e - i * 0.05) / (1 - i * 0.05)));
      var ke = k * k * (3 - 2 * k);
      g.position.lerpVectors(d.home, TARGET, ke);
      g.position.y += Math.sin(t * 0.75 + d.ph) * 0.1 * (1 - ke);
      g.scale.setScalar(Math.max(0.001, 1 - 0.93 * ke));
      /* les fichiers restent face à l'objectif, comme dans l'illustration */
      g.lookAt(camPos);
      g.rotateZ(d.roll * (1 - ke) + ke * 0.6);
      g.rotateY(ke * 0.9);
      var o = 1 - Math.pow(ke, 1.8);
      d.parts.forEach(function (m) { m.material.opacity = o; });
    });

    var pulse = Math.pow(e, 2.2);
    glow.material.opacity = 0.6 + pulse * 0.4 + Math.sin(t * 1.3) * 0.03;
    crest.material.opacity = 0.88 + pulse * 0.12;
    slotLight.intensity = 0.6 + pulse * 3.6;
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
