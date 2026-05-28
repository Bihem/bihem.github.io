#!/usr/bin/env python3
"""
Dikenga Design — Pipeline Acquisition DATA-DRIVEN v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✦ SQLite  — base persistante entre les runs
✦ Séquence 3 touches  — J0 → J+3 → J+7 (stop si réponse)
✦ A/B templates  — variant A (audit direct) vs B (benchmark)
✦ IMAP  — détecte les réponses automatiquement
✦ Funnel  — rapport Telegram avec taux analysé/emailé/répondu
✦ Scoring v2  — 4 signaux : perf + tech + issues + reachability
"""

import os, sys, sqlite3, json, csv, smtplib, ssl, re, time, random
import urllib.request, urllib.parse, urllib.error
import imaplib, email as _email_mod
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text     import MIMEText

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR   = os.path.dirname(BASE_DIR)
DB_PATH    = os.path.join(PROJ_DIR, 'prospects.db')
CSV_PATH   = os.path.join(PROJ_DIR, 'prospects.csv')   # backup GitHub

SMTP_HOST  = os.environ.get('SMTP_HOST', 'smtp.mail.ovh.net')
SMTP_PORT  = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER  = os.environ.get('SMTP_USER', 'contact@dikengadesign.fr')
SMTP_PASS  = os.environ.get('SMTP_PASS', '')
IMAP_HOST  = 'zimbra1.mail.ovh.net'
IMAP_PORT  = 993

TELEGRAM_TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID  = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGESPEED_KEY     = os.environ.get('PAGESPEED_API_KEY', '')

SENDER_NAME        = "Mes-Reves — Dikenga Design"
SITE_URL           = "https://dikengadesign.fr"
CONTACT_URL        = "https://dikengadesign.fr/contact"
PHONE              = "+33 7 67 53 70 59"
ZIMBRA_URL         = "https://zimbra1.mail.ovh.net/modern/"

MAX_EMAILS_PER_RUN = 15
EMAIL_DELAY_SEC    = 45
MIN_SCORE          = 40
FOLLOW_UP_DELAYS   = {2: 3, 3: 7}   # step → jours depuis la touch précédente

# ─── Requêtes DuckDuckGo par jour de semaine ─────────────
SEARCH_QUERIES = {
    0: ["petite boutique shopify vetements site:.fr",
        "créateur mode indépendant boutique en ligne paris"],
    1: ["boutique wix vetements créateur independant france site:.fr",
        "restaurant café paris site wix squarespace"],
    2: ["startup saas france interface ux améliorer site:.fr",
        "agence communication paris site wix wordpress refonte"],
    3: ["boutique prestashop wordpress créateur france site:.fr",
        "créateur bijoux accessoires ecommerce france"],
    4: ["marque streetwear emergente france site:.fr",
        "artisan boutique en ligne france shopify wix"],
}

BLACKLIST_DOMAINS = {
    'dikengadesign.fr','talseume.com','talseume.fr','studiobooking.fr',
    'google.com','google.fr','facebook.com','instagram.com','linkedin.com',
    'youtube.com','twitter.com','tiktok.com','amazon.fr','fnac.com',
    'cdiscount.com','leboncoin.fr','laposte.fr','free.fr','orange.fr',
    'shopify.com','wordpress.com','wix.com','squarespace.com','webflow.io',
    'duckduckgo.com','bing.com','yahoo.com','wikipedia.org',
    'vogue.fr','elle.fr','marieclaire.fr','lefigaro.fr','lemonde.fr',
    'leparisien.fr','20minutes.fr','bfmtv.com','ovhcloud.com','ovh.com',
    'github.com','gitlab.com','dev-wp.fr','fr.wordpress.org',
}

SKIP_EMAIL_DOMAINS = {
    'domain.com','example.com','email.com','test.com','your-email.com',
    'yoursite.com','site.com','mysite.com','website.com','mail.com',
    'gmail.com','hotmail.com','yahoo.com','yahoo.fr','outlook.com',
    'live.com','icloud.com','protonmail.com',
}
SKIP_EMAIL_PREFIXES = (
    'noreply','no-reply','donotreply','webmaster','abuse','security',
)

# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS prospects (
          id              INTEGER PRIMARY KEY AUTOINCREMENT,
          domain          TEXT    UNIQUE NOT NULL,
          company         TEXT,
          email           TEXT,
          tech            TEXT,
          perf_mobile     INTEGER DEFAULT 0,
          lcp             TEXT,
          issues          TEXT,          -- JSON list
          score           INTEGER DEFAULT 0,
          status          TEXT    DEFAULT 'new',
          -- Séquence
          sequence_step   INTEGER DEFAULT 0,
          variant         TEXT,          -- 'A' ou 'B'
          date_added      TEXT,
          date_analyzed   TEXT,
          date_step1      TEXT,
          date_step2      TEXT,
          date_step3      TEXT,
          next_action     TEXT,          -- ISO date quand envoyer la prochaine touch
          -- Metrics
          opens           INTEGER DEFAULT 0,
          replied         INTEGER DEFAULT 0,
          bounced         INTEGER DEFAULT 0,
          notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          prospect_id INTEGER NOT NULL,
          event       TEXT    NOT NULL,  -- sourced/analyzed/emailed/replied/bounced
          ts          TEXT    NOT NULL,
          data        TEXT,
          FOREIGN KEY(prospect_id) REFERENCES prospects(id)
        );
        """)

def log_event(pid, event, data=None):
    try:
        with get_conn() as c:
            c.execute(
                "INSERT INTO events(prospect_id,event,ts,data) VALUES(?,?,?,?)",
                (pid, event, datetime.now().isoformat(),
                 json.dumps(data) if data else None)
            )
    except Exception as e:
        print(f"  [DB event error] {e}")

# ═══════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════

def tg(text):
    if not TELEGRAM_TOKEN:
        print(text); return
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4096],
        "parse_mode": "HTML"
    }).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10): pass
    except Exception as e:
        print(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════
# HTTP HELPERS
# ═══════════════════════════════════════════════════════════

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch(url, timeout=15, max_bytes=80_000):
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(max_bytes).decode('utf-8', errors='ignore')
    except Exception:
        return None

def extract_domain(url_str):
    try:
        h = urllib.parse.urlparse(url_str).netloc or url_str
        return re.sub(r'^www\.', '', h.lower().split('/')[0].split('?')[0].strip())
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════
# SOURCES — Prospect Discovery
# ═══════════════════════════════════════════════════════════

def ddg_search(query, max_results=12):
    html = fetch(
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
        timeout=25
    )
    if not html:
        return []
    domains = []
    for encoded in re.findall(r'uddg=([^&">\s]+)', html):
        try:
            real_url = urllib.parse.unquote(encoded)
            d = extract_domain(real_url)
            if d and '.' in d and d not in domains:
                domains.append(d)
        except Exception:
            pass
    # fallback hrefs directs
    for href in re.findall(r'href="(https?://[^"]{8,})"', html):
        d = extract_domain(href)
        if d and '.' in d and 'duckduckgo' not in d and d not in domains:
            domains.append(d)
    return domains[:max_results]

def discover_new_domains(n=25):
    """Retourne des domaines non encore dans la DB."""
    day = datetime.now().weekday() % len(SEARCH_QUERIES)
    queries = SEARCH_QUERIES[day]

    with get_conn() as c:
        existing = {r[0] for r in c.execute("SELECT domain FROM prospects")}

    found = []
    for q in queries:
        print(f"  🔍 {q}")
        for d in ddg_search(q):
            d = re.sub(r'^www\.', '', d)
            if (d not in existing and
                d not in BLACKLIST_DOMAINS and
                d not in [x for x in found] and
                '.' in d and len(d) < 60 and d.count('.') <= 3 and
                not any(b in d for b in BLACKLIST_DOMAINS)):
                found.append(d)
        time.sleep(2)

    unique = list(dict.fromkeys(found))[:n]
    print(f"  → {len(unique)} nouveaux domaines trouvés")
    return unique

# ═══════════════════════════════════════════════════════════
# ENRICHER — Site Analysis
# ═══════════════════════════════════════════════════════════

TECH_PATTERNS = {
    'Shopify':     ['cdn.shopify.com', 'shopify.com/s/', 'shopify-section'],
    'Wix':         ['wixstatic.com', 'wix.com/_api', 'X-Wix-'],
    'Squarespace': ['squarespace.com', 'sqspcdn.com', 'static1.squarespace'],
    'WordPress':   ['wp-content/', 'wp-includes/', '/wp-json/'],
    'PrestaShop':  ['prestashop', '/modules/ps_'],
    'Webflow':     ['webflow.io', 'assets.website-files.com', 'data-wf-'],
    'Framer':      ['framerusercontent.com', 'framer.com/m/'],
    'WooCommerce': ['woocommerce', 'wc-api', 'add-to-cart='],
}

def detect_tech(html):
    h = html.lower()
    for tech, patterns in TECH_PATTERNS.items():
        if any(p.lower() in h for p in patterns):
            return tech
    return 'Custom'

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]{2,}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}',
    re.IGNORECASE
)

def _best_email(emails_found):
    """Choisit le meilleur email dans une liste (priorise contact@, info@, etc.)"""
    PRIORITY_PREFIXES = ('contact@', 'hello@', 'info@', 'bonjour@',
                         'pro@', 'studio@', 'agence@', 'equipe@')
    for prefix in PRIORITY_PREFIXES:
        for e in emails_found:
            if e.lower().startswith(prefix):
                return e
    return emails_found[0] if emails_found else None

def find_email(domain):
    for path in ['', '/contact', '/contact.html', '/contact-us',
                 '/nous-contacter', '/about', '/a-propos']:
        try:
            html = fetch(f"https://{domain}{path}", timeout=10) or ''
            # Dénormaliser obfuscations
            html = (html
                .replace('[at]', '@').replace('(at)', '@').replace(' at ', '@')
                .replace('[dot]', '.').replace('(dot)', '.'))
            # Chercher dans mailto: d'abord
            for m in re.finditer(r'mailto:([^"\'>\s&]+)', html, re.IGNORECASE):
                e = m.group(1).split('?')[0].strip().lower()
                dom = e.split('@')[-1] if '@' in e else ''
                if (dom not in SKIP_EMAIL_DOMAINS
                        and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                        and re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)):
                    return e
            # Chercher emails en texte brut
            found = []
            for m in EMAIL_RE.finditer(html):
                e = m.group(0).lower().strip().rstrip('.')
                dom = e.split('@')[-1] if '@' in e else ''
                if (dom not in SKIP_EMAIL_DOMAINS
                        and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                        and re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)):
                    found.append(e)
            if found:
                return _best_email(found)
        except Exception:
            pass
        time.sleep(0.5)
    return None

def pagespeed_analyze(domain):
    url = f"https://{domain}"
    api_url = (
        f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={urllib.parse.quote(url, safe='')}&strategy=mobile"
        + (f"&key={PAGESPEED_KEY}" if PAGESPEED_KEY else '')
    )
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        lr    = d.get('lighthouseResult', {})
        perf  = int(lr.get('categories', {}).get('performance', {}).get('score', 0) * 100)
        lcp   = lr.get('audits', {}).get('largest-contentful-paint', {}).get('displayValue', 'N/A')
        issues = []
        AUDIT_LABELS = {
            'uses-optimized-images':    'Images non optimisées',
            'render-blocking-resources':'Ressources bloquantes au chargement',
            'unused-css-rules':         'CSS inutilisé chargé',
            'uses-text-compression':    'Compression texte absente (Gzip)',
            'unused-javascript':        'JavaScript inutilisé',
            'uses-responsive-images':   'Images non responsives',
        }
        for k, label in AUDIT_LABELS.items():
            a = lr.get('audits', {}).get(k, {})
            if isinstance(a.get('score'), (int, float)) and a['score'] < 0.5:
                issues.append(label)
        return {'perf_mobile': perf, 'lcp': lcp, 'issues': issues[:4]}

    except urllib.error.HTTPError as e:
        code = e.code
        print(f"  PageSpeed {code} → fallback timing")
    except Exception as e:
        print(f"  PageSpeed error → fallback: {e}")

    # ── Fallback HTTP timing ─────────────────────────────────
    try:
        t0 = time.time()
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read(50_000).decode('utf-8', errors='ignore')
        ms = (time.time() - t0) * 1000
        issues = []
        h = html.lower()
        if len(html) > 40_000:        issues.append('Page lourde, compression absente')
        if h.count('<script') > 15:   issues.append('Trop de scripts JavaScript')
        if h.count('<img') > 18:      issues.append('Nombreuses images non optimisées')
        return {'perf_mobile': 45, 'lcp': f"~{ms/1000:.1f}s (estimé)", 'issues': issues[:4]}
    except Exception:
        return {'perf_mobile': 35, 'lcp': 'N/A', 'issues': ['Site inaccessible ou très lent']}

def enrich_domain(domain):
    """Analyse complète d'un domaine → dict."""
    print(f"  Analyzing {domain}…")
    html = fetch(f"https://{domain}", timeout=12) or ''
    tech    = detect_tech(html)
    ps      = pagespeed_analyze(domain)
    time.sleep(1)
    em      = find_email_in_html(html) or find_email(domain)
    company = domain.split('.')[0].replace('-', ' ').replace('_', ' ').capitalize()
    return {
        'domain':      domain,
        'company':     company,
        'email':       em,
        'tech':        tech,
        'perf_mobile': ps['perf_mobile'],
        'lcp':         ps['lcp'],
        'issues':      ps['issues'],
    }

def find_email_in_html(html):
    """Cherche un email directement dans un HTML déjà récupéré."""
    if not html:
        return None
    html2 = (html
        .replace('[at]', '@').replace('(at)', '@')
        .replace('[dot]', '.').replace('(dot)', '.'))
    for m in re.finditer(r'mailto:([^"\'>\s&]+)', html2, re.IGNORECASE):
        e = m.group(1).split('?')[0].strip().lower()
        dom = e.split('@')[-1] if '@' in e else ''
        if (dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                and re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)):
            return e
    found = []
    for m in EMAIL_RE.finditer(html2):
        e = m.group(0).lower().strip().rstrip('.')
        dom = e.split('@')[-1] if '@' in e else ''
        if (dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                and re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)):
            found.append(e)
    return _best_email(found)

# ═══════════════════════════════════════════════════════════
# SCORER v2 — Multi-factor (100 pts)
# ═══════════════════════════════════════════════════════════

TECH_OPPORTUNITY = {
    'Wix':         30,   # site builder → plafond UX vite atteint
    'Squarespace': 28,
    'PrestaShop':  26,
    'WooCommerce': 24,
    'WordPress':   22,
    'Shopify':     18,   # bon outil mais design souvent générique
    'Custom':      15,
    'Framer':       8,
    'Webflow':      5,   # déjà bien conçu
    'Inconnu':     12,
}

def compute_score(perf_mobile, tech, issues):
    # Performance mobile (0–40 pts)
    if   perf_mobile < 30: perf_pts = 40
    elif perf_mobile < 50: perf_pts = 30
    elif perf_mobile < 65: perf_pts = 20
    elif perf_mobile < 80: perf_pts = 10
    else:                  perf_pts =  5

    # Tech stack (0–30 pts)
    tech_pts = TECH_OPPORTUNITY.get(tech, 12)

    # Issues (0–30 pts, 7 pts par issue, max 4)
    issue_pts = min(len(issues), 4) * 7

    return min(perf_pts + tech_pts + issue_pts, 100)

# ═══════════════════════════════════════════════════════════
# EMAIL TEMPLATES A/B — 3 étapes
# ═══════════════════════════════════════════════════════════

def get_email_template(variant, prospect_row, step):
    p       = dict(prospect_row)
    domain  = p['domain']
    company = p.get('company') or domain.split('.')[0].capitalize()
    tech    = p.get('tech', 'votre solution actuelle')
    perf    = p.get('perf_mobile', 0)
    lcp     = p.get('lcp', 'N/A')
    try:
        issues = json.loads(p['issues']) if isinstance(p['issues'], str) else (p['issues'] or [])
    except Exception:
        issues = []
    issues_top3 = issues[:3]

    # Contexte performance
    if   perf < 40: perf_label = f"score critique ({perf}/100)"
    elif perf < 60: perf_label = f"score en dessous de la moyenne ({perf}/100)"
    else:           perf_label = f"marge d'optimisation ({perf}/100)"

    issues_lines = '\n'.join(f"— {i}" for i in issues_top3) or "— Performance mobile insuffisante"

    # ── STEP 1 ───────────────────────────────────────────
    if step == 1:
        if variant == 'A':
            subject = f"Audit {domain} — {len(issues_top3) or 3} points qui freinent vos conversions"
            body = f"""Bonjour,

J'ai audité {domain} ce matin.

Score performance mobile : {perf_label}
Temps de chargement : {lcp}

Ce que j'ai trouvé :
{issues_lines}

Sur un site {tech}, ces problèmes représentent en général 15 à 30 % de conversions perdues.

Je suis Mes-Reves, UI/UX Designer freelance. Je corrige exactement ce type de problèmes — en 2 à 3 semaines, sans refonte complète.

Vous avez 20 minutes cette semaine pour un appel rapide ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL} | {PHONE}

--
Pour ne plus recevoir ces emails : répondez STOP."""

        else:  # variant B — benchmark concurrents
            subject = f"{domain} : votre score mobile est de {perf}/100"
            body = f"""Bonjour,

Une boutique {tech} dans votre secteur a augmenté son temps de visite de 40 % après 3 semaines de refonte UX.

J'ai regardé {domain} — {perf_label}.

Ce qui diffère des meilleures boutiques de votre secteur :
{issues_lines}

Je suis Mes-Reves, UI/UX Designer spécialisé dans l'optimisation de sites {tech}.

Vous avez 20 minutes pour voir ce que ça donnerait sur votre site ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL}

--
Pour ne plus recevoir ces emails : répondez STOP."""

    # ── STEP 2 — relance J+3 ─────────────────────────────
    elif step == 2:
        subject = f"Re : {domain} — j'ai finalisé l'audit"
        body = f"""Bonjour,

Je vous avais envoyé un message il y a 3 jours concernant {domain}.

Le problème principal que j'ai identifié : {issues_top3[0] if issues_top3 else 'performances mobile insuffisantes'}.

Ça se corrige rapidement — et l'impact sur l'expérience utilisateur est immédiat.

Toujours intéressé pour en parler 20 minutes ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL}

--
Pour ne plus recevoir ces emails : répondez STOP."""

    # ── STEP 3 — dernière relance J+7 ────────────────────
    else:
        subject = f"Dernière relance — {domain}"
        body = f"""Bonjour,

Je ferme mon dossier sur {domain}.

Si vous cherchez un designer UI/UX quand le moment sera venu, mon portfolio est ici : {SITE_URL}

Bonne continuation,
Mes-Reves — Dikenga Design"""

    return {'subject': subject, 'body': body}

# ═══════════════════════════════════════════════════════════
# SEQUENCER — État de la machine
# ═══════════════════════════════════════════════════════════

def get_prospects_to_contact():
    """Retourne 3 listes : step1 (nouveaux), step2 (relance J+3), step3 (relance J+7)."""
    today = datetime.now().date().isoformat()
    with get_conn() as c:
        step1 = c.execute("""
            SELECT * FROM prospects
            WHERE status = 'queued'
              AND email IS NOT NULL AND email != ''
              AND score >= ? AND sequence_step = 0
            ORDER BY score DESC LIMIT ?
        """, (MIN_SCORE, MAX_EMAILS_PER_RUN)).fetchall()

        step2 = c.execute("""
            SELECT * FROM prospects
            WHERE status = 'emailed_1'
              AND next_action <= ? AND replied = 0 AND bounced = 0
            ORDER BY score DESC
        """, (today,)).fetchall()

        step3 = c.execute("""
            SELECT * FROM prospects
            WHERE status = 'emailed_2'
              AND next_action <= ? AND replied = 0 AND bounced = 0
            ORDER BY score DESC
        """, (today,)).fetchall()

    return list(step1), list(step2), list(step3)

def mark_emailed(pid, step, variant, subject):
    status_map  = {1: 'emailed_1', 2: 'emailed_2', 3: 'emailed_3'}
    date_col    = f"date_step{step}"
    next_delay  = FOLLOW_UP_DELAYS.get(step + 1)
    next_action = (
        (datetime.now() + timedelta(days=next_delay)).date().isoformat()
        if next_delay else None
    )
    with get_conn() as c:
        c.execute(f"""
            UPDATE prospects
            SET status=?, sequence_step=?, variant=?, {date_col}=?, next_action=?
            WHERE id=?
        """, (status_map[step], step, variant,
              datetime.now().isoformat(), next_action, pid))
    log_event(pid, f'emailed_{step}', {'variant': variant, 'subject': subject})

# ═══════════════════════════════════════════════════════════
# SENDER — SMTP
# ═══════════════════════════════════════════════════════════

def send_email(prospect_row, step, variant):
    pid  = prospect_row['id']
    to   = prospect_row['email']
    tmpl = get_email_template(variant, prospect_row, step)

    if not SMTP_PASS:
        print(f"  [DRY RUN] → {to}  subject: {tmpl['subject']}")
        mark_emailed(pid, step, variant, tmpl['subject'])
        return True

    msg = MIMEMultipart('alternative')
    msg['From']     = f"{SENDER_NAME} <{SMTP_USER}>"
    msg['To']       = to
    msg['Subject']  = tmpl['subject']
    msg['Reply-To'] = SMTP_USER
    msg.add_header('List-Unsubscribe', f'<mailto:{SMTP_USER}?subject=STOP>')
    msg.attach(MIMEText(tmpl['body'], 'plain', 'utf-8'))

    ctx = ssl.create_default_context()
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.ehlo(); s.starttls(context=ctx); s.ehlo()
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to, msg.as_string())

        print(f"  ✅ Step {step}/{variant} → {to}")
        mark_emailed(pid, step, variant, tmpl['subject'])
        return True

    except Exception as e:
        print(f"  ❌ SMTP error → {to}: {e}")
        with get_conn() as c:
            c.execute("UPDATE prospects SET status='error', notes=? WHERE id=?",
                      (str(e)[:200], pid))
        log_event(pid, 'error', {'step': step, 'error': str(e)})
        return False

# ═══════════════════════════════════════════════════════════
# IMAP — Détection des réponses
# ═══════════════════════════════════════════════════════════

def check_replies():
    """Vérifie la boîte mail pour des réponses de prospects emailés."""
    if not SMTP_PASS:
        return 0

    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx) as imap:
            imap.login(SMTP_USER, SMTP_PASS)
            imap.select('INBOX')

            since = (datetime.now() - timedelta(days=21)).strftime('%d-%b-%Y')
            _, data = imap.search(None, f'(SINCE {since})')
            if not data[0]:
                return 0

            with get_conn() as c:
                emailed = c.execute("""
                    SELECT id, domain, email FROM prospects
                    WHERE status IN ('emailed_1','emailed_2','emailed_3')
                      AND replied = 0 AND bounced = 0
                """).fetchall()

            if not emailed:
                return 0

            # Index par domaine et par email
            by_domain = {r['domain']: r for r in emailed}
            by_email  = {r['email'].lower(): r for r in emailed if r['email']}

            replied_count = 0
            for num in data[0].split():
                try:
                    _, msg_data = imap.fetch(num, '(RFC822.HEADER)')
                    msg = _email_mod.message_from_bytes(msg_data[0][1])
                    from_hdr = msg.get('From', '').lower()

                    matched = None
                    for dom, prospect in by_domain.items():
                        if dom in from_hdr:
                            matched = prospect; break
                    if not matched:
                        for em, prospect in by_email.items():
                            if em in from_hdr:
                                matched = prospect; break

                    if matched:
                        with get_conn() as c:
                            c.execute(
                                "UPDATE prospects SET replied=1, status='replied' WHERE id=?",
                                (matched['id'],)
                            )
                        log_event(matched['id'], 'replied', {'from': from_hdr[:100]})
                        replied_count += 1
                        print(f"  📩 Réponse détectée : {matched['domain']}")
                except Exception:
                    pass

            # Détecter les bounces (MAILER-DAEMON)
            _, bounce_data = imap.search(None, f'(SINCE {since} FROM "MAILER-DAEMON")')
            if bounce_data[0]:
                for num in bounce_data[0].split():
                    try:
                        _, msg_data = imap.fetch(num, '(RFC822)')
                        raw = msg_data[0][1].decode('utf-8', errors='ignore').lower()
                        for em, prospect in by_email.items():
                            if em in raw:
                                with get_conn() as c:
                                    c.execute(
                                        "UPDATE prospects SET bounced=1, status='bounced' WHERE id=?",
                                        (prospect['id'],)
                                    )
                                log_event(prospect['id'], 'bounced', {})
                                print(f"  ⚠️ Bounce détecté : {em}")
                    except Exception:
                        pass

            return replied_count

    except Exception as e:
        print(f"  IMAP error: {e}")
        return 0

# ═══════════════════════════════════════════════════════════
# REPORTER — Funnel Telegram
# ═══════════════════════════════════════════════════════════

def build_telegram_report(run_stats):
    today = datetime.now().strftime('%d/%m/%Y %H:%M')

    with get_conn() as c:
        totals = dict(c.execute("""
            SELECT
              COUNT(*)                                              AS total,
              SUM(CASE WHEN email IS NOT NULL AND email!='' THEN 1 ELSE 0 END) AS with_email,
              SUM(CASE WHEN sequence_step >= 1 THEN 1 ELSE 0 END) AS total_emailed,
              SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END)          AS total_replied,
              SUM(CASE WHEN bounced=1 THEN 1 ELSE 0 END)          AS total_bounced,
              SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END)    AS queued,
              SUM(CASE WHEN status IN ('emailed_1','emailed_2') THEN 1 ELSE 0 END) AS pending
            FROM prospects
        """).fetchone())

    # Taux
    analyzed  = run_stats['analyzed']
    w_email   = run_stats['with_email']
    sent_day  = run_stats['sent']
    new_rep   = run_stats['new_replies']

    email_rate  = f"{w_email/analyzed*100:.0f}%" if analyzed else "—"
    reply_rate  = f"{totals['total_replied']/totals['total_emailed']*100:.1f}%" if totals['total_emailed'] else "—"
    ab_note     = ""
    if run_stats.get('step1_A') or run_stats.get('step1_B'):
        ab_note = f"\nA/B today → A:{run_stats.get('step1_A',0)}  B:{run_stats.get('step1_B',0)}"

    reply_alert = ""
    if new_rep > 0:
        reply_alert = (f"\n\n🔔 <b>{new_rep} nouvelle{'s' if new_rep>1 else ''} réponse{'s' if new_rep>1 else ''} "
                       f"→ <a href='{ZIMBRA_URL}'>ouvre Zimbra</a></b>")

    return (
        f"📊 <b>Dikenga Acquisition — {today}</b>\n\n"
        f"<b>🔍 Run du jour</b>\n"
        f"  Analysés : {analyzed}   |   Emails trouvés : {w_email} ({email_rate})\n"
        f"  Envoyés : {sent_day} (step1:{run_stats.get('s1',0)} relances:{run_stats.get('s2',0)+run_stats.get('s3',0)})"
        f"{ab_note}\n"
        f"  Nouvelles réponses IMAP : {new_rep}\n\n"
        f"<b>📈 Pipeline total</b>\n"
        f"  Prospects en base : {totals['total']}\n"
        f"  Total emailés : {totals['total_emailed']}\n"
        f"  En attente relance : {totals['pending']}\n"
        f"  File queued : {totals['queued']}\n\n"
        f"<b>🎯 Taux globaux</b>\n"
        f"  Email trouvé / analysé : {email_rate}\n"
        f"  Réponse / emailé : {reply_rate}\n"
        f"  Bounces : {totals['total_bounced']}"
        f"{reply_alert}"
    )

# ═══════════════════════════════════════════════════════════
# CSV BACKUP — pour GitHub
# ═══════════════════════════════════════════════════════════

def export_csv():
    with get_conn() as c:
        rows = c.execute(
            "SELECT domain,company,email,tech,perf_mobile,score,lcp,issues,"
            "status,date_added,date_analyzed,sequence_step,variant,notes "
            "FROM prospects ORDER BY date_added DESC"
        ).fetchall()
    cols = ['domain','company','email','tech','perf_mobile','score','lcp',
            'issues','status','date_added','date_analyzed','sequence_step','variant','notes']
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'═'*55}")
    print(f"  Dikenga Acquisition DATA-DRIVEN v2")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*55}\n")

    init_db()

    stats = {
        'analyzed': 0, 'with_email': 0, 'sent': 0,
        's1': 0, 's2': 0, 's3': 0,
        'step1_A': 0, 'step1_B': 0,
        'new_replies': 0,
    }

    # ── 1. IMAP — Check replies ──────────────────────────
    print("📩 Vérification des réponses IMAP…")
    stats['new_replies'] = check_replies()
    print(f"  → {stats['new_replies']} nouvelle(s) réponse(s)\n")

    # ── 2. DISCOVERY ────────────────────────────────────
    print("🔍 Découverte de prospects…")
    new_domains = discover_new_domains(n=25)
    print()

    # ── 3. ENRICHMENT + STORE ───────────────────────────
    if new_domains:
        print(f"📊 Analyse de {len(new_domains)} domaines…\n")
        for domain in new_domains[:20]:
            try:
                data  = enrich_domain(domain)
                sc    = compute_score(data['perf_mobile'], data['tech'], data['issues'])
                has_email = bool(data['email'])

                if has_email and sc >= MIN_SCORE:
                    status = 'queued'
                elif not has_email:
                    status = 'no_email'
                else:
                    status = 'low_score'

                with get_conn() as c:
                    c.execute("""
                        INSERT OR IGNORE INTO prospects
                          (domain,company,email,tech,perf_mobile,lcp,issues,
                           score,status,date_added,date_analyzed)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        data['domain'], data['company'], data['email'],
                        data['tech'], data['perf_mobile'], data['lcp'],
                        json.dumps(data['issues']),
                        sc, status,
                        datetime.now().date().isoformat(),
                        datetime.now().isoformat()
                    ))

                stats['analyzed'] += 1
                if has_email:
                    stats['with_email'] += 1

                print(f"  {domain}: {data['tech']} | perf={data['perf_mobile']} "
                      f"| score={sc} | email={'✅' if has_email else '❌'} | {status}")

            except Exception as e:
                print(f"  ⚠️  {domain}: {e}")
            time.sleep(1.5)
        print()

    # ── 4. SEQUENCER + SEND ─────────────────────────────
    print("📧 Envoi des emails…\n")
    s1, s2, s3 = get_prospects_to_contact()
    total_sent = 0
    variants   = ['A', 'B']

    for i, p in enumerate(s1):
        if total_sent >= MAX_EMAILS_PER_RUN: break
        v  = variants[i % 2]
        ok = send_email(p, step=1, variant=v)
        if ok:
            total_sent += 1; stats['s1'] += 1
            stats[f'step1_{v}'] += 1
            stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s2:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        ok = send_email(p, step=2, variant=p.get('variant', 'A') or 'A')
        if ok:
            total_sent += 1; stats['s2'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s3:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        ok = send_email(p, step=3, variant=p.get('variant', 'A') or 'A')
        if ok:
            total_sent += 1; stats['s3'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    # ── 5. CSV BACKUP ────────────────────────────────────
    export_csv()
    print(f"\n✅ CSV exporté → {CSV_PATH}")

    # ── 6. TELEGRAM REPORT ──────────────────────────────
    print("\n📱 Rapport Telegram…")
    report = build_telegram_report(stats)
    tg(report)
    print(report)

    print(f"\n{'═'*55}")
    print(f"  Done. {total_sent} emails envoyés | {stats['new_replies']} réponses")
    print(f"{'═'*55}\n")


if __name__ == '__main__':
    main()
