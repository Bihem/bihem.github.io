/* ==========================================================================
   CANAL 93 ADMIN — DATA SERVICE
   - MODE = 'local' : modifications stockées dans localStorage du navigateur,
                       aucun push GitHub, aucun token requis. Mode démo.
   - MODE = 'github': push live via GitHub Contents API + auth PAT.

   Bascule UNE LIGNE ci-dessous pour passer en prod.
   ========================================================================== */
(function (global) {
  'use strict';

  // ============== MODE ==============
  const MODE = 'local';   // ← 'local' (démo, pas de push) | 'github' (prod, push live)
  // =================================

  const REPO = 'Bihem/bihem.github.io';
  const BRANCH = 'main';
  const BASE_PATH = 'canal93';
  const API = (path) => `https://api.github.com/repos/${REPO}/contents/${path}`;
  const TOKEN_KEY = 'c93admin.gh-token';
  const USER_KEY = 'c93admin.gh-user';
  const LOCAL_PREFIX = 'c93admin.local.';   // localStorage prefix pour les JSON en mode local
  const IMG_PREFIX = 'c93admin.img.';

  // ---- TOKEN STORAGE ----
  const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
  const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch {} };
  const clearToken = () => { try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch {} };
  const getUser = () => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (raw) return JSON.parse(raw);
    } catch {}
    if (MODE === 'local') return { login: 'demo', name: 'Démo', avatar: '' };
    return null;
  };

  // ---- LOW-LEVEL FETCH WRAPPER (GitHub) ----
  const headers = () => ({
    'Authorization': `token ${getToken()}`,
    'Accept': 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
  });

  async function ghFetch(url, opts = {}) {
    const r = await fetch(url, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
    if (!r.ok) {
      const body = await r.text().catch(() => '');
      const err = new Error(`GitHub API ${r.status}: ${body.slice(0, 200)}`);
      err.status = r.status;
      throw err;
    }
    return r.json();
  }

  // ---- AUTH ----
  async function verifyToken(token) {
    const r = await fetch('https://api.github.com/user', {
      headers: { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json' }
    });
    if (!r.ok) throw new Error('Token invalide ou révoqué');
    const user = await r.json();
    const r2 = await fetch(`https://api.github.com/repos/${REPO}`, {
      headers: { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json' }
    });
    if (!r2.ok) throw new Error(`Pas d'accès au repo ${REPO}`);
    const repoInfo = await r2.json();
    if (!repoInfo.permissions || !repoInfo.permissions.push) {
      throw new Error(`Le token n'a pas le scope "repo" (push requis)`);
    }
    return user;
  }

  async function login(token) {
    if (MODE === 'local') {
      const fake = { login: 'demo', name: 'Démo', avatar_url: '' };
      try { localStorage.setItem(USER_KEY, JSON.stringify({ login: fake.login, name: fake.name, avatar: fake.avatar_url })); } catch {}
      return fake;
    }
    const user = await verifyToken(token);
    setToken(token);
    try { localStorage.setItem(USER_KEY, JSON.stringify({ login: user.login, name: user.name, avatar: user.avatar_url })); } catch {}
    return user;
  }

  function logout() {
    clearToken();
    if (MODE === 'local') {
      // Reset démo : vider aussi les modifs locales
      try {
        Object.keys(localStorage).forEach(k => {
          if (k.startsWith(LOCAL_PREFIX) || k.startsWith(IMG_PREFIX)) localStorage.removeItem(k);
        });
      } catch {}
    }
    location.href = 'login.html';
  }

  function requireAuth() {
    if (MODE === 'local') return true;  // pas d'auth en mode local
    if (!getToken()) {
      const next = encodeURIComponent(location.pathname.split('/').pop() || 'index.html');
      location.href = `login.html?next=${next}`;
      return false;
    }
    return true;
  }

  // ---- READ JSON ----
  async function readJSON(relpath) {
    // 1) En mode local, regarder d'abord le localStorage
    if (MODE === 'local') {
      try {
        const raw = localStorage.getItem(LOCAL_PREFIX + relpath);
        if (raw) return JSON.parse(raw);
      } catch {}
    }
    // 2) Fallback : charger le fichier servi par le site
    const url = `/${BASE_PATH}/${relpath}?v=${Date.now()}`;
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) {
      if (r.status === 404) return null;
      throw new Error(`Read failed: ${r.status}`);
    }
    return r.json();
  }

  async function readJSONWithSha(relpath) {
    if (MODE === 'local') {
      return { data: await readJSON(relpath), sha: null };
    }
    try {
      const info = await ghFetch(API(`${BASE_PATH}/${relpath}`));
      const content = atob(info.content.replace(/\n/g, ''));
      const data = JSON.parse(new TextDecoder().decode(Uint8Array.from(content, c => c.charCodeAt(0))));
      return { data, sha: info.sha };
    } catch (e) {
      if (e.status === 404) return { data: null, sha: null };
      throw e;
    }
  }

  // ---- WRITE JSON ----
  async function writeJSON(relpath, data, message) {
    if (MODE === 'local') {
      // Pas de push — stockage navigateur uniquement
      const json = JSON.stringify(data, null, 2);
      try { localStorage.setItem(LOCAL_PREFIX + relpath, json); } catch (e) {
        throw new Error('Quota localStorage dépassé. Supprime des images ou exporte les données.');
      }
      // Petit delay simulé pour cohérence UX (spinner visible)
      await new Promise(r => setTimeout(r, 220));
      return { commit: { sha: 'local-' + Date.now().toString(36) }, content: { path: relpath } };
    }

    const existing = await readJSONWithSha(relpath);
    const json = JSON.stringify(data, null, 2);
    const utf8 = new TextEncoder().encode(json);
    const b64 = btoa(String.fromCharCode(...utf8));
    const payload = { message: message || `update ${relpath}`, content: b64, branch: BRANCH };
    if (existing.sha) payload.sha = existing.sha;
    return ghFetch(API(`${BASE_PATH}/${relpath}`), { method: 'PUT', body: JSON.stringify(payload) });
  }

  // ---- UPLOAD IMAGE ----
  async function uploadImage(file, subdir = 'uploads/events') {
    if (!file) throw new Error('Aucun fichier');

    if (MODE === 'local') {
      // En mode local : on convertit en data URL et on retourne directement.
      // Pas de stockage permanent (gros = saturé), mais utilisable pour preview.
      return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Lecture image échouée'));
        reader.readAsDataURL(file);
      });
    }

    const safeName = file.name.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/-+/g, '-');
    const ts = Date.now().toString(36);
    const filename = `${ts}-${safeName}`;
    const relpath = `${subdir}/${filename}`;
    const buf = await file.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
    const b64 = btoa(bin);
    const payload = { message: `upload ${relpath}`, content: b64, branch: BRANCH };
    await ghFetch(API(`${BASE_PATH}/${relpath}`), { method: 'PUT', body: JSON.stringify(payload) });
    return `/${BASE_PATH}/${relpath}`;
  }

  async function deleteFile(relpath, message) {
    if (MODE === 'local') {
      try { localStorage.removeItem(LOCAL_PREFIX + relpath); } catch {}
      return { ok: true };
    }
    const info = await ghFetch(API(`${BASE_PATH}/${relpath}`));
    return ghFetch(API(`${BASE_PATH}/${relpath}`), {
      method: 'DELETE',
      body: JSON.stringify({ message: message || `delete ${relpath}`, sha: info.sha, branch: BRANCH }),
    });
  }

  // ---- RESET LOCAL ----
  function resetLocal() {
    try {
      Object.keys(localStorage).forEach(k => {
        if (k.startsWith(LOCAL_PREFIX) || k.startsWith(IMG_PREFIX)) localStorage.removeItem(k);
      });
    } catch {}
  }

  // ---- EXPORT / IMPORT (utile en mode local) ----
  function exportAll() {
    const out = {};
    try {
      Object.keys(localStorage).forEach(k => {
        if (k.startsWith(LOCAL_PREFIX)) {
          out[k.slice(LOCAL_PREFIX.length)] = JSON.parse(localStorage.getItem(k));
        }
      });
    } catch {}
    return out;
  }

  // ---- ID GENERATOR ----
  function genId() {
    return 'id_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
  }

  // ---- DEMO BANNER ----
  function injectDemoBanner() {
    if (MODE !== 'local') return;
    if (document.getElementById('c93DemoBanner')) return;
    const banner = document.createElement('div');
    banner.id = 'c93DemoBanner';
    banner.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; z-index: 999;
      background: linear-gradient(90deg, rgba(255,107,53,0.96), rgba(198,244,50,0.96));
      color: #0A0B0E; font-family: 'Inter', system-ui, sans-serif;
      font-size: 12px; font-weight: 600;
      padding: 7px 16px; text-align: center; letter-spacing: 0.01em;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      display: flex; align-items: center; justify-content: center; gap: 12px;
    `;
    banner.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <span><strong>MODE DÉMO</strong> · les modifications restent dans ton navigateur — aucun push GitHub, le site live n'est pas affecté.</span>
      <button id="c93DemoReset" style="background:rgba(10,11,14,0.18);border:1px solid rgba(10,11,14,0.3);color:#0A0B0E;border-radius:4px;padding:3px 9px;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;">Reset</button>
    `;
    document.body.prepend(banner);
    // Décale le contenu sous le banner
    document.body.style.paddingTop = '32px';
    document.getElementById('c93DemoReset').addEventListener('click', () => {
      if (confirm('Reset démo : supprime toutes les modifs locales et recharge depuis les JSON du site. Continuer ?')) {
        resetLocal();
        location.reload();
      }
    });
  }

  // Auto-injection au DOMContentLoaded
  if (MODE === 'local') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectDemoBanner);
    } else {
      injectDemoBanner();
    }
  }

  global.C93Data = {
    MODE,
    REPO, BRANCH, BASE_PATH,
    getToken, setToken, clearToken, getUser,
    verifyToken, login, logout, requireAuth,
    readJSON, readJSONWithSha, writeJSON,
    uploadImage, deleteFile,
    resetLocal, exportAll,
    genId,
  };
})(window);
