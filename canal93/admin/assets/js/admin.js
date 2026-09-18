/* ==========================================================================
   CANAL 93 — ADMIN · interactions
   ========================================================================== */
(() => {
  'use strict';

  // ---- SIDEBAR (mobile drawer + desktop collapse) ----
  const app = document.querySelector('.app');
  const sidebar = document.querySelector('.sidebar');
  const burger = document.querySelector('.topbar-burger');
  const sidebarToggle = document.querySelector('.sidebar-toggle');

  const ensureBackdrop = () => {
    let b = document.querySelector('.drawer-backdrop');
    if (!b) {
      b = document.createElement('div');
      b.className = 'drawer-backdrop';
      document.body.appendChild(b);
      b.addEventListener('click', closeDrawer);
    }
    return b;
  };
  const openDrawer = () => {
    sidebar?.classList.add('open');
    ensureBackdrop().classList.add('open');
    document.body.style.overflow = 'hidden';
  };
  const closeDrawer = () => {
    sidebar?.classList.remove('open');
    document.querySelector('.drawer-backdrop')?.classList.remove('open');
    document.body.style.overflow = '';
  };
  burger?.addEventListener('click', openDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

  sidebarToggle?.addEventListener('click', () => {
    app?.classList.toggle('sidebar-collapsed');
    try { localStorage.setItem('c93admin.sidebar-collapsed', app.classList.contains('sidebar-collapsed') ? '1' : '0'); } catch {}
  });
  try {
    if (localStorage.getItem('c93admin.sidebar-collapsed') === '1') app?.classList.add('sidebar-collapsed');
  } catch {}

  // ---- THEME TOGGLE (persist) ----
  const themeBtn = document.querySelector('[data-action="toggle-theme"]');
  const applyTheme = (t) => {
    document.body.classList.toggle('light-theme', t === 'light');
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t === 'light' ? '#F6F7F9' : '#0A0B0E');
  };
  try {
    const saved = localStorage.getItem('c93admin.theme');
    if (saved) applyTheme(saved);
  } catch {}
  themeBtn?.addEventListener('click', () => {
    const next = document.body.classList.contains('light-theme') ? 'dark' : 'light';
    applyTheme(next);
    try { localStorage.setItem('c93admin.theme', next); } catch {}
  });

  // ---- KEYBOARD SHORTCUT — Cmd/Ctrl + K → focus search ----
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      document.querySelector('.topbar-search input')?.focus();
    }
  });

  // ---- TABS (data-tab-group) ----
  document.querySelectorAll('[data-tab-group]').forEach(group => {
    group.querySelectorAll('.tab').forEach(t => {
      t.addEventListener('click', () => {
        group.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        const target = t.dataset.target;
        if (target) {
          document.querySelectorAll(`[data-tab-panel="${group.dataset.tabGroup}"]`).forEach(p => p.hidden = (p.dataset.id !== target));
        }
      });
    });
  });

  // ---- CHIPS (single-select) ----
  document.querySelectorAll('.chips').forEach(group => {
    group.querySelectorAll('.chip').forEach(c => {
      c.addEventListener('click', () => {
        group.querySelectorAll('.chip').forEach(x => x.classList.remove('active'));
        c.classList.add('active');
      });
    });
  });

  // ---- SWITCHES ----
  document.querySelectorAll('.switch').forEach(sw => {
    sw.addEventListener('click', () => sw.classList.toggle('on'));
  });

  // ---- ANIMATE BAR FILLS once visible ----
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        const bar = e.target;
        const val = bar.dataset.fill || bar.style.getPropertyValue('--fill') || '0';
        bar.style.width = '0%';
        requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = val + '%'; }));
        io.unobserve(bar);
      });
    }, { threshold: 0.2 });
    document.querySelectorAll('.bar-fill[data-fill]').forEach(b => io.observe(b));
  }

  // ---- COUNT-UP ANIMATION on KPIs ----
  const fmtNum = (n) => {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
    return Math.round(n).toString();
  };
  const fmtMoney = (n) => fmtNum(n);
  document.querySelectorAll('[data-countup]').forEach(el => {
    const target = parseFloat(el.dataset.countup);
    const dur = parseInt(el.dataset.dur || '1200', 10);
    const money = el.dataset.money === '1';
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const v = target * eased;
      el.textContent = money ? fmtMoney(v) : fmtNum(v);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = el.dataset.format === 'money' ? fmtMoney(target) : (el.dataset.format === 'int' ? Math.round(target).toLocaleString('fr-FR') : fmtNum(target));
    };
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(entries => {
        entries.forEach(e => { if (e.isIntersecting) { requestAnimationFrame(step); io.unobserve(el); } });
      }, { threshold: 0.4 });
      io.observe(el);
    } else { requestAnimationFrame(step); }
  });

  // ---- DRAW SVG SPARKLINES (data-spark="1,2,3,...") ----
  document.querySelectorAll('svg[data-spark]').forEach(svg => {
    const pts = svg.dataset.spark.split(',').map(Number);
    const max = Math.max(...pts), min = Math.min(...pts);
    const w = 120, h = 50, pad = 4;
    const stepX = (w - pad * 2) / (pts.length - 1);
    const toY = v => h - pad - ((v - min) / Math.max(max - min, 0.0001)) * (h - pad * 2);
    const points = pts.map((v, i) => [pad + i * stepX, toY(v)]);
    const d = points.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
    const dArea = d + ` L${w - pad},${h} L${pad},${h} Z`;
    const color = svg.dataset.color || 'var(--accent)';
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = `
      <defs>
        <linearGradient id="sg${Math.random().toString(36).slice(2,7)}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="${color}" stop-opacity="0.45"/>
          <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
        </linearGradient>
      </defs>`;
    const grad = svg.querySelector('linearGradient');
    const gid = grad.id;
    svg.innerHTML += `
      <path d="${dArea}" fill="url(#${gid})"/>
      <path d="${d}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    `;
  });

  // ---- DRAW MAIN AREA CHART (data-chart="...") ----
  document.querySelectorAll('svg[data-chart]').forEach(svg => {
    const series = svg.dataset.chart.split('|').map(s => s.split(',').map(Number));
    const labels = (svg.dataset.labels || '').split(',');
    const colors = (svg.dataset.colors || 'var(--accent),var(--warm)').split(',');
    const N = series[0].length;
    const all = series.flat();
    const min = Math.min(...all, 0);
    const max = Math.max(...all);
    const W = 800, H = 240, PAD_L = 36, PAD_R = 12, PAD_T = 18, PAD_B = 26;
    const innerW = W - PAD_L - PAD_R;
    const innerH = H - PAD_T - PAD_B;
    const x = (i) => PAD_L + (i / (N - 1)) * innerW;
    const y = (v) => PAD_T + (1 - (v - min) / Math.max(max - min, 0.0001)) * innerH;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('preserveAspectRatio', 'none');

    const ticks = 4;
    let gridHtml = '';
    for (let i = 0; i <= ticks; i++) {
      const yy = PAD_T + (i / ticks) * innerH;
      const v = max - (i / ticks) * (max - min);
      gridHtml += `<line x1="${PAD_L}" x2="${W - PAD_R}" y1="${yy}" y2="${yy}" stroke="var(--line)" stroke-dasharray="2 4"/>`;
      gridHtml += `<text x="${PAD_L - 8}" y="${yy + 4}" text-anchor="end" font-family="JetBrains Mono, monospace" font-size="9" fill="var(--fg-mute)">${Math.round(v)}</text>`;
    }
    let xlabHtml = '';
    labels.forEach((lab, i) => {
      const xx = x(i);
      xlabHtml += `<text x="${xx}" y="${H - 6}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9" fill="var(--fg-mute)" letter-spacing="0.06em">${lab.toUpperCase()}</text>`;
    });

    let defsHtml = '<defs>';
    series.forEach((s, idx) => {
      const id = `cg${idx}_${Math.random().toString(36).slice(2,7)}`;
      defsHtml += `<linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${colors[idx] || 'var(--accent)'}" stop-opacity="${idx === 0 ? 0.32 : 0.18}"/>
        <stop offset="100%" stop-color="${colors[idx] || 'var(--accent)'}" stop-opacity="0"/>
      </linearGradient>`;
      s._gid = id;
    });
    defsHtml += '</defs>';

    let pathsHtml = '';
    series.forEach((s, idx) => {
      const pts = s.map((v, i) => [x(i), y(v)]);
      const d = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
      const dArea = d + ` L${x(N-1)},${PAD_T + innerH} L${x(0)},${PAD_T + innerH} Z`;
      const c = colors[idx] || 'var(--accent)';
      const dashed = idx > 0 ? 'stroke-dasharray="5 4"' : '';
      pathsHtml += `<path d="${dArea}" fill="url(#${s._gid})"/>`;
      pathsHtml += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2" ${dashed} stroke-linecap="round" stroke-linejoin="round"/>`;
      pts.forEach(([px, py], i) => {
        if (idx === 0 && (i === pts.length - 1 || i === 0)) {
          pathsHtml += `<circle cx="${px}" cy="${py}" r="3.5" fill="${c}" stroke="var(--surface)" stroke-width="2"/>`;
        }
      });
    });

    svg.innerHTML = `<g class="chart-grid">${gridHtml}</g><g class="chart-axis">${xlabHtml}</g>${defsHtml}${pathsHtml}`;
  });

  // ---- HEATMAP CELLS — randomize intensities once for demo ----
  document.querySelectorAll('.heatmap-grid').forEach(grid => {
    const cells = grid.querySelectorAll('.heatmap-cell');
    cells.forEach((c, i) => {
      if (c.dataset.i !== undefined) return;
      // weighted random : more zeros, occasional fours
      const r = Math.random();
      let v = 0;
      if (r > 0.96) v = 4;
      else if (r > 0.85) v = 3;
      else if (r > 0.66) v = 2;
      else if (r > 0.40) v = 1;
      c.dataset.i = v;
      const date = c.dataset.date || '';
      c.title = date ? `${date} · ${v * 7 + Math.floor(Math.random()*6)} entrées` : '';
    });
  });

  // ---- TOASTS (basic api) ----
  const toastHost = document.createElement('div');
  toastHost.style.cssText = 'position:fixed;bottom:24px;right:24px;display:flex;flex-direction:column;gap:8px;z-index:200;';
  document.body.appendChild(toastHost);
  window.c93Toast = (msg, type = 'success') => {
    const colors = { success: 'var(--success)', warm: 'var(--warm)', danger: 'var(--danger)', info: 'var(--info)' };
    const t = document.createElement('div');
    t.style.cssText = `min-width:240px;padding:12px 16px;background:var(--bg-glass-strong);backdrop-filter:blur(20px);border:1px solid var(--line);border-left:3px solid ${colors[type] || colors.success};border-radius:10px;color:var(--fg);font-size:13px;box-shadow:0 10px 30px rgba(0,0,0,.4);opacity:0;transform:translateY(8px);transition:all 240ms cubic-bezier(.16,1,.3,1);`;
    t.textContent = msg;
    toastHost.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = '1'; t.style.transform = 'translateY(0)'; });
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(8px)';
      setTimeout(() => t.remove(), 250);
    }, 3200);
  };

  // ---- CTA buttons demo feedback ----
  document.querySelectorAll('[data-toast]').forEach(b => {
    b.addEventListener('click', (e) => {
      e.preventDefault();
      window.c93Toast(b.dataset.toast, b.dataset.toastType || 'success');
    });
  });

})();
