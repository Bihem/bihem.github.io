/* ==========================================================================
   CANAL 93 ADMIN — DATA SERVICE
   - Auth GitHub via Personal Access Token (PAT) stocké dans localStorage
   - CRUD sur des fichiers JSON dans le repo Bihem/bihem.github.io sous /canal93/data/
   - Upload d'images binaires dans /canal93/uploads/
   - Push direct via GitHub Contents API (PUT)
   ========================================================================== */
(function (global) {
  'use strict';

  const REPO = 'Bihem/bihem.github.io';
  const BRANCH = 'main';
  const BASE_PATH = 'canal93';
  const API = (path) => `https://api.github.com/repos/${REPO}/contents/${path}`;
  const TOKEN_KEY = 'c93admin.gh-token';
  const USER_KEY = 'c93admin.gh-user';

  // ---- TOKEN STORAGE ----
  const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
  const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch {} };
  const clearToken = () => {
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch {}
  };
  const getUser = () => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; }
  };

  // ---- LOW-LEVEL FETCH WRAPPER ----
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
    // Check repo access
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
    const user = await verifyToken(token);
    setToken(token);
    try { localStorage.setItem(USER_KEY, JSON.stringify({ login: user.login, name: user.name, avatar: user.avatar_url })); } catch {}
    return user;
  }

  function logout() {
    clearToken();
    location.href = 'login.html';
  }

  function requireAuth() {
    if (!getToken()) {
      const next = encodeURIComponent(location.pathname.split('/').pop() || 'index.html');
      location.href = `login.html?next=${next}`;
      return false;
    }
    return true;
  }

  // ---- READ JSON ----
  // Lecture publique (sans token requis) via GitHub Pages CDN — plus rapide et fonctionne aussi côté front public
  async function readJSON(relpath) {
    const url = `/${BASE_PATH}/${relpath}?v=${Date.now()}`;
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) {
      if (r.status === 404) return { data: null, sha: null };
      throw new Error(`Read failed: ${r.status}`);
    }
    return r.json();
  }

  // Lecture côté admin avec SHA (nécessaire pour update)
  async function readJSONWithSha(relpath) {
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
    const existing = await readJSONWithSha(relpath);
    const json = JSON.stringify(data, null, 2);
    const utf8 = new TextEncoder().encode(json);
    const b64 = btoa(String.fromCharCode(...utf8));
    const payload = {
      message: message || `update ${relpath}`,
      content: b64,
      branch: BRANCH,
    };
    if (existing.sha) payload.sha = existing.sha;
    return ghFetch(API(`${BASE_PATH}/${relpath}`), { method: 'PUT', body: JSON.stringify(payload) });
  }

  // ---- UPLOAD BINARY (image) ----
  async function uploadImage(file, subdir = 'uploads/events') {
    if (!file) throw new Error('Aucun fichier');
    const safeName = file.name.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/-+/g, '-');
    const ts = Date.now().toString(36);
    const filename = `${ts}-${safeName}`;
    const relpath = `${subdir}/${filename}`;
    const buf = await file.arrayBuffer();
    // Convert ArrayBuffer to base64
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
    const b64 = btoa(bin);
    const payload = {
      message: `upload ${relpath}`,
      content: b64,
      branch: BRANCH,
    };
    await ghFetch(API(`${BASE_PATH}/${relpath}`), { method: 'PUT', body: JSON.stringify(payload) });
    return `/${BASE_PATH}/${relpath}`;
  }

  // ---- WRITE HTML/TEXT (raw, no JSON wrap) ----
  async function writeFile(relpath, text, message) {
    const existing = await ghFetch(API(`${BASE_PATH}/${relpath}`)).catch(e => { if (e.status === 404) return null; throw e; });
    const utf8 = new TextEncoder().encode(text);
    const b64 = btoa(String.fromCharCode(...utf8));
    const payload = {
      message: message || `update ${relpath}`,
      content: b64,
      branch: BRANCH,
    };
    if (existing && existing.sha) payload.sha = existing.sha;
    return ghFetch(API(`${BASE_PATH}/${relpath}`), { method: 'PUT', body: JSON.stringify(payload) });
  }

  // ---- DELETE FILE ----
  async function deleteFile(relpath, message) {
    const info = await ghFetch(API(`${BASE_PATH}/${relpath}`));
    return ghFetch(API(`${BASE_PATH}/${relpath}`), {
      method: 'DELETE',
      body: JSON.stringify({
        message: message || `delete ${relpath}`,
        sha: info.sha,
        branch: BRANCH,
      }),
    });
  }

  // ---- ID GENERATOR ----
  function genId() {
    return 'id_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
  }

  global.C93Data = {
    REPO, BRANCH, BASE_PATH,
    getToken, setToken, clearToken, getUser,
    verifyToken, login, logout, requireAuth,
    readJSON, readJSONWithSha, writeJSON,
    uploadImage, writeFile, deleteFile,
    genId,
  };
})(window);
