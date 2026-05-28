#!/usr/bin/env python3
"""
Dikenga Design — Pipeline Acquisition DATA-DRIVEN v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOURCES (rotation quotidienne) :
  ① PagesJaunes  — annuaire FR, emails directs sur les fiches
  ② Yelp.fr      — boutiques/restaurants Paris avec sites web
  ③ DuckDuckGo   — requêtes ciblées TPE/PME mauvais sites

PIPELINE :
  ✦ SQLite        persistance locale entre les runs
  ✦ Scoring v2    perf + tech + issues + source quality
  ✦ Séquence 3×   J0 → J+3 → J+7, stop si réponse
  ✦ A/B templates audit direct vs benchmark concurrents
  ✦ IMAP          détecte réponses + bounces automatiquement
  ✦ Funnel report Telegram avec taux par source
  ✦ 25 emails/j   max (vs 15 avant)
"""

import os, sys, sqlite3, json, csv, smtplib, ssl, re, time
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
CSV_PATH   = os.path.join(PROJ_DIR, 'prospects.csv')

SMTP_HOST  = os.environ.get('SMTP_HOST', 'smtp.mail.ovh.net')
SMTP_PORT  = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER  = os.environ.get('SMTP_USER', 'contact@dikengadesign.fr')
SMTP_PASS  = os.environ.get('SMTP_PASS', '')
IMAP_HOST  = 'zimbra1.mail.ovh.net'
IMAP_PORT  = 993

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGESPEED_KEY    = os.environ.get('PAGESPEED_API_KEY', '')

SENDER_NAME        = "Mes-Reves — Dikenga Design"
SITE_URL           = "https://dikengadesign.fr"
CONTACT_URL        = "https://dikengadesign.fr/contact"
PHONE              = "+33 7 67 53 70 59"
ZIMBRA_URL         = "https://zimbra1.mail.ovh.net/modern/"

MAX_EMAILS_PER_RUN = 25      # ↑ augmenté à 25
EMAIL_DELAY_SEC    = 45
MIN_SCORE          = 38
FOLLOW_UP_DELAYS   = {2: 3, 3: 7}
MAX_ANALYZE_PER_RUN= 40      # domaines à analyser par run

# ─── Sources PagesJaunes ────────────────────────────────
# Rotation : 1 catégorie + ville différente chaque jour
PJ_SEARCHES = [
    ("boutique vêtements mode",    "Paris"),
    ("bijoux créateur artisan",    "Paris"),
    ("restaurant gastronomique",   "Paris"),
    ("agence immobilière",         "Paris"),
    ("salon de beauté spa",        "Paris"),
    ("boutique concept store",     "Lyon"),
    ("créateur mode indépendant",  "Bordeaux"),
    ("boutique décoration",        "Marseille"),
    ("coach consultant formation", "Paris"),
    ("studio photographe",        "Paris"),
]

# ─── Sources Yelp.fr ────────────────────────────────────
YELP_SEARCHES = [
    ("boutiques mode", "Paris"),
    ("bijouteries",    "Paris"),
    ("restaurants",    "Paris, Île-de-France"),
    ("spa beauté",     "Paris"),
    ("galeries art",   "Paris"),
]

# ─── Sources DuckDuckGo (requêtes affinées) ─────────────
DDG_QUERIES = {
    0: ["petite boutique shopify vetements site:.fr",
        "créateur mode indépendant boutique en ligne paris"],
    1: ["boutique wix vetements créateur independant site:.fr",
        "restaurant café paris site wix squarespace"],
    2: ["startup france interface ux améliorer site:.fr",
        "agence communication paris site wix wordpress refonte"],
    3: ["boutique prestashop wordpress créateur site:.fr",
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
    'github.com','gitlab.com','fr.wordpress.org','yelp.fr','yelp.com',
    'pagesjaunes.fr','tripadvisor.fr','lafourchette.com',
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
          issues          TEXT,
          score           INTEGER DEFAULT 0,
          source          TEXT    DEFAULT 'ddg',   -- 'ddg','pagesjunes','yelp'
          status          TEXT    DEFAULT 'new',
          sequence_step   INTEGER DEFAULT 0,
          variant         TEXT,
          date_added      TEXT,
          date_analyzed   TEXT,
          date_step1      TEXT,
          date_step2      TEXT,
          date_step3      TEXT,
          next_action     TEXT,
          opens           INTEGER DEFAULT 0,
          replied         INTEGER DEFAULT 0,
          bounced         INTEGER DEFAULT 0,
          notes           TEXT
        );
        -- Ajouter colonne source si elle n'existe pas (migration)
        CREATE TABLE IF NOT EXISTS events (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          prospect_id INTEGER NOT NULL,
          event       TEXT    NOT NULL,
          ts          TEXT    NOT NULL,
          data        TEXT,
          FOREIGN KEY(prospect_id) REFERENCES prospects(id)
        );
        """)
    # Migration : ajouter source si absent
    with get_conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(prospects)")]
        if 'source' not in cols:
            c.execute("ALTER TABLE prospects ADD COLUMN source TEXT DEFAULT 'ddg'")

def log_event(pid, event, data=None):
    try:
        with get_conn() as c:
            c.execute(
                "INSERT INTO events(prospect_id,event,ts,data) VALUES(?,?,?,?)",
                (pid, event, datetime.now().isoformat(),
                 json.dumps(data) if data else None))
    except Exception:
        pass

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
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10): pass
    except Exception as e:
        print(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════
# HTTP HELPERS
# ═══════════════════════════════════════════════════════════

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}

def fetch(url, timeout=15, max_bytes=120_000):
    try:
        req = urllib.request.Request(url, headers=HDRS)
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

def is_valid_domain(d):
    return (d and '.' in d and len(d) < 65
            and d.count('.') <= 3
            and not any(b in d for b in BLACKLIST_DOMAINS)
            and d not in BLACKLIST_DOMAINS)

# ═══════════════════════════════════════════════════════════
# SOURCE 1 — PagesJaunes
# ═══════════════════════════════════════════════════════════

def search_pagesjunes(what, where, max_pages=4):
    """
    Scrape PagesJaunes annuaire → domaines + emails directs.
    PagesJaunes liste des PME avec sites web → très bon taux email.
    """
    domains = []
    direct_emails = {}   # domain → email trouvé directement sur PJ

    for page in range(1, max_pages + 1):
        url = (f"https://www.pagesjaunes.fr/annuaire/recherche"
               f"?quoi={urllib.parse.quote(what)}"
               f"&ou={urllib.parse.quote(where)}"
               f"&page={page}")
        html = fetch(url, timeout=25)
        if not html:
            break

        # ── Extraire les URLs de sites web ─────────────────
        # Méthode 1 : redirects PJ encodés ?url=https://...
        for m in re.finditer(r'[?&]url=(https?[^&"\'>\s]+)', html):
            try:
                decoded = urllib.parse.unquote(m.group(1))
                d = extract_domain(decoded)
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
            except Exception:
                pass

        # Méthode 2 : data-ext-url ou data-url attributs
        for m in re.finditer(r'data-(?:ext-)?url="(https?://[^"]{5,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)

        # Méthode 3 : href vers domaines externes (pas pagesjaunes)
        for m in re.finditer(r'href="(https?://(?!(?:www\.)?pagesjaunes)[^"]{8,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)

        # ── Extraire emails directs depuis les fiches ───────
        # PagesJaunes affiche parfois l'email directement
        for m in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6})', html):
            e = m.group(1).lower()
            dom = e.split('@')[-1]
            if is_valid_domain(dom) and dom not in SKIP_EMAIL_DOMAINS:
                direct_emails[dom] = e

        # Peu de résultats = dernière page
        if html.count('bi-denomination') < 3:
            break

        time.sleep(2.5)

    # Stocker les emails directs dans un fichier temporaire pour enrichment
    _pj_direct_emails.update(direct_emails)
    return domains

_pj_direct_emails = {}   # buffer emails directs PagesJaunes

# ═══════════════════════════════════════════════════════════
# SOURCE 2 — Yelp.fr
# ═══════════════════════════════════════════════════════════

def search_yelp(category, city, max_pages=3):
    """
    Scrape Yelp.fr → domaines de commerces avec sites web.
    Bonne source pour boutiques/restaurants Paris haut de gamme.
    """
    domains = []

    for page in range(max_pages):
        url = (f"https://www.yelp.fr/search"
               f"?find_desc={urllib.parse.quote(category)}"
               f"&find_loc={urllib.parse.quote(city)}"
               f"&start={page * 10}")
        html = fetch(url, timeout=25)
        if not html:
            break

        # Yelp encode les URLs de sites dans leurs pages biz
        # Chercher les liens vers pages business Yelp
        biz_slugs = re.findall(r'href="/biz/([^?"]+)"', html)
        for slug in list(dict.fromkeys(biz_slugs))[:8]:
            biz_url = f"https://www.yelp.fr/biz/{slug}"
            biz_html = fetch(biz_url, timeout=15)
            if not biz_html:
                continue

            # Extraire le site web depuis la page business Yelp
            for m in re.finditer(
                r'(?:website|site web|site internet)[^<]{0,200}'
                r'href="(https?://(?!www\.yelp)[^"]{5,80})"',
                biz_html, re.IGNORECASE
            ):
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
                    break

            # Fallback : tout lien externe sur la page business
            for m in re.finditer(
                r'href="(https?://(?!(?:www\.)?yelp)[^"]{8,80})"',
                biz_html
            ):
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
                    break

            time.sleep(1.5)

        time.sleep(3)

    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE 3 — DuckDuckGo (existante, améliorée)
# ═══════════════════════════════════════════════════════════

def search_duckduckgo(query, max_results=12):
    html = fetch(
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
        timeout=25)
    if not html:
        return []
    domains = []
    for encoded in re.findall(r'uddg=([^&">\s]+)', html):
        try:
            real_url = urllib.parse.unquote(encoded)
            d = extract_domain(real_url)
            if d and d not in domains:
                domains.append(d)
        except Exception:
            pass
    for href in re.findall(r'href="(https?://[^"]{8,})"', html):
        d = extract_domain(href)
        if d and 'duckduckgo' not in d and d not in domains:
            domains.append(d)
    return domains[:max_results]

# ═══════════════════════════════════════════════════════════
# MULTI-SOURCE DISCOVERY
# ═══════════════════════════════════════════════════════════

SOURCE_ROTATION = ['pagesjunes', 'yelp', 'ddg']   # rotation quotidienne

def discover_new_domains(n=MAX_ANALYZE_PER_RUN):
    """
    Rotation des sources selon le jour :
      Lun/Mer/Ven → PagesJaunes  (meilleur taux email)
      Mar/Jeu     → Yelp + DDG   (diversité)
    """
    with get_conn() as c:
        existing = {r[0] for r in c.execute("SELECT domain FROM prospects")}

    day = datetime.now().weekday()   # 0=Lun … 6=Dim
    found  = {}   # domain → source

    # ── PagesJaunes (Lun, Mer, Ven) ─────────────────────────
    if day in (0, 2, 4):
        pj_idx = (day // 2) % len(PJ_SEARCHES)
        what, where = PJ_SEARCHES[pj_idx]
        print(f"  📒 PagesJaunes : «{what}» à {where}")
        for d in search_pagesjunes(what, where, max_pages=4):
            d = re.sub(r'^www\.', '', d)
            if d not in existing and d not in found:
                found[d] = 'pagesjunes'
        print(f"     → {sum(1 for v in found.values() if v=='pagesjunes')} domaines PJ")

    # ── Yelp.fr (Mar, Mer) ──────────────────────────────────
    if day in (1, 2):
        yelp_idx = day % len(YELP_SEARCHES)
        cat, city = YELP_SEARCHES[yelp_idx]
        print(f"  🍴 Yelp.fr : «{cat}» à {city}")
        for d in search_yelp(cat, city, max_pages=2):
            d = re.sub(r'^www\.', '', d)
            if d not in existing and d not in found:
                found[d] = 'yelp'
        print(f"     → {sum(1 for v in found.values() if v=='yelp')} domaines Yelp")

    # ── DuckDuckGo (tous les jours en complément) ────────────
    ddg_day = day % len(DDG_QUERIES)
    queries  = DDG_QUERIES[ddg_day]
    print(f"  🔍 DuckDuckGo : {len(queries)} requêtes")
    for q in queries:
        for d in search_duckduckgo(q):
            d = re.sub(r'^www\.', '', d)
            if d not in existing and d not in found and is_valid_domain(d):
                found[d] = 'ddg'
        time.sleep(2)
    print(f"     → {sum(1 for v in found.values() if v=='ddg')} domaines DDG")

    total = len(found)
    print(f"\n  Total unique nouveaux : {total}")
    # Trier : PagesJaunes d'abord (meilleur taux email)
    ordered = (
        [(d, s) for d, s in found.items() if s == 'pagesjunes'] +
        [(d, s) for d, s in found.items() if s == 'yelp'] +
        [(d, s) for d, s in found.items() if s == 'ddg']
    )
    return ordered[:n]

# ═══════════════════════════════════════════════════════════
# ENRICHER
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
    re.IGNORECASE)

def _best_email(emails):
    PRIORITY = ('contact@','hello@','info@','bonjour@',
                'pro@','studio@','agence@','equipe@','team@')
    for prefix in PRIORITY:
        for e in emails:
            if e.lower().startswith(prefix):
                return e
    return emails[0]

def _extract_emails_from_html(html):
    if not html:
        return []
    html2 = (html
        .replace('[at]', '@').replace('(at)', '@').replace(' at ', '@')
        .replace('[dot]', '.').replace('(dot)', '.'))
    found = []
    for m in re.finditer(r'mailto:([^"\'>\s&]+)', html2, re.IGNORECASE):
        e = m.group(1).split('?')[0].strip().lower()
        dom = e.split('@')[-1] if '@' in e else ''
        if (re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)
                and dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)):
            found.append(e)
    for m in EMAIL_RE.finditer(html2):
        e = m.group(0).lower().strip().rstrip('.')
        dom = e.split('@')[-1] if '@' in e else ''
        if (re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)
                and dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                and e not in found):
            found.append(e)
    return found

def find_email_for_domain(domain):
    """Cherche l'email sur le site — homepage + pages contact."""
    # Email direct depuis PagesJaunes ?
    if domain in _pj_direct_emails:
        return _pj_direct_emails[domain]

    for path in ['', '/contact', '/contact.html', '/contact-us',
                 '/nous-contacter', '/about', '/a-propos', '/equipe']:
        try:
            html = fetch(f"https://{domain}{path}", timeout=10) or ''
            emails = _extract_emails_from_html(html)
            if emails:
                return _best_email(emails)
        except Exception:
            pass
        time.sleep(0.4)
    return None

def pagespeed_analyze(domain):
    url = f"https://{domain}"
    api_url = (
        f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={urllib.parse.quote(url, safe='')}&strategy=mobile"
        + (f"&key={PAGESPEED_KEY}" if PAGESPEED_KEY else ''))
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        lr    = d.get('lighthouseResult', {})
        perf  = int(lr.get('categories', {}).get('performance', {}).get('score', 0) * 100)
        lcp   = lr.get('audits', {}).get('largest-contentful-paint', {}).get('displayValue', 'N/A')
        issues = []
        for k, label in {
            'uses-optimized-images':    'Images non optimisées',
            'render-blocking-resources':'Ressources bloquant le chargement',
            'unused-css-rules':         'CSS inutilisé chargé',
            'uses-text-compression':    'Compression absente (Gzip/Brotli)',
            'unused-javascript':        'JavaScript inutilisé',
            'uses-responsive-images':   'Images non responsives',
        }.items():
            a = lr.get('audits', {}).get(k, {})
            if isinstance(a.get('score'), (int, float)) and a['score'] < 0.5:
                issues.append(label)
        return {'perf_mobile': perf, 'lcp': lcp, 'issues': issues[:4]}
    except urllib.error.HTTPError as e:
        print(f"  PageSpeed {e.code} → fallback")
    except Exception as e:
        print(f"  PageSpeed error → fallback: {type(e).__name__}")

    # Fallback timing
    try:
        t0 = time.time()
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=HDRS), timeout=12) as r:
            html = r.read(50_000).decode('utf-8', errors='ignore')
        ms = (time.time() - t0) * 1000
        issues = []
        h = html.lower()
        if len(html) > 40_000:       issues.append('Page lourde, compression absente')
        if h.count('<script') > 15:  issues.append('Trop de scripts JavaScript')
        if h.count('<img') > 18:     issues.append('Nombreuses images non optimisées')
        return {'perf_mobile': 45, 'lcp': f"~{ms/1000:.1f}s (estimé)", 'issues': issues[:4]}
    except Exception:
        return {'perf_mobile': 35, 'lcp': 'N/A', 'issues': ['Site inaccessible ou très lent']}

def enrich_domain(domain, source='ddg'):
    """Analyse complète → dict."""
    html = fetch(f"https://{domain}", timeout=12) or ''
    tech = detect_tech(html)
    ps   = pagespeed_analyze(domain)
    time.sleep(0.8)
    # Email : chercher dans HTML homepage d'abord (rapide)
    emails_home = _extract_emails_from_html(html)
    em = _best_email(emails_home) if emails_home else find_email_for_domain(domain)
    company = domain.split('.')[0].replace('-', ' ').replace('_', ' ').capitalize()
    return {
        'domain':      domain,
        'company':     company,
        'email':       em,
        'tech':        tech,
        'perf_mobile': ps['perf_mobile'],
        'lcp':         ps['lcp'],
        'issues':      ps['issues'],
        'source':      source,
    }

# ═══════════════════════════════════════════════════════════
# SCORER v2
# ═══════════════════════════════════════════════════════════

TECH_OPP = {
    'Wix':         30, 'Squarespace': 28, 'PrestaShop': 26,
    'WooCommerce': 24, 'WordPress':   22, 'Shopify':    18,
    'Custom':      15, 'Framer':       8, 'Webflow':     5, 'Inconnu': 12,
}

def compute_score(perf, tech, issues):
    if   perf < 30: p = 40
    elif perf < 50: p = 30
    elif perf < 65: p = 20
    elif perf < 80: p = 10
    else:           p =  5
    return min(p + TECH_OPP.get(tech, 12) + min(len(issues), 4) * 7, 100)

# ═══════════════════════════════════════════════════════════
# EMAIL TEMPLATES A/B — 3 étapes
# ═══════════════════════════════════════════════════════════

def get_template(variant, prospect, step):
    p       = dict(prospect)
    domain  = p['domain']
    company = p.get('company') or domain.split('.')[0].capitalize()
    tech    = p.get('tech', 'votre solution actuelle')
    perf    = p.get('perf_mobile', 0)
    lcp     = p.get('lcp', 'N/A')
    try:
        issues = json.loads(p['issues']) if isinstance(p['issues'], str) else (p['issues'] or [])
    except Exception:
        issues = []
    top3   = issues[:3]
    lines  = '\n'.join(f"— {i}" for i in top3) or "— Performance mobile en dessous de la moyenne"

    if   perf < 40: plabel = f"score critique ({perf}/100)"
    elif perf < 60: plabel = f"en dessous de la moyenne ({perf}/100)"
    else:           plabel = f"optimisable ({perf}/100)"

    # ── STEP 1 ───────────────────────────────────────────
    if step == 1:
        if variant == 'A':
            subj = f"Audit {domain} — {len(top3) or 3} points qui freinent vos conversions"
            body = f"""Bonjour,

J'ai audité {domain} ce matin.

Score performance mobile : {plabel}
Temps de chargement : {lcp}

Ce que j'ai trouvé :
{lines}

Sur un site {tech}, ces problèmes représentent en général 15 à 30 % de conversions perdues.

Je suis Mes-Reves, UI/UX Designer freelance — je corrige exactement ce type de problèmes en 2 à 3 semaines, sans refonte complète.

Vous avez 20 minutes cette semaine pour un appel rapide ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL} | {PHONE}

--
Pour ne plus recevoir ces emails : répondez STOP."""

        else:
            subj = f"{domain} : score mobile {perf}/100 — une piste d'amélioration"
            body = f"""Bonjour,

Une boutique {tech} dans votre secteur a amélioré son taux de conversion de 35 % après 3 semaines de refonte UX.

J'ai regardé {domain} : {plabel}.

Ce qui diffère des meilleurs sites de votre secteur :
{lines}

Je suis Mes-Reves, UI/UX Designer freelance. 20 minutes pour voir ce que ça donnerait sur votre site ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL}

--
Pour ne plus recevoir ces emails : répondez STOP."""

    # ── STEP 2 — relance J+3 ─────────────────────────────
    elif step == 2:
        subj = f"Re : {domain} — j'ai finalisé l'audit"
        body = f"""Bonjour,

Je vous avais envoyé un message il y a 3 jours concernant {domain}.

Le point principal que j'ai identifié : {top3[0] if top3 else 'performance mobile insuffisante'}.

Ça se corrige rapidement — et l'impact sur l'expérience utilisateur est immédiat.

Toujours intéressé pour en parler 20 minutes ?
→ {CONTACT_URL}

Cordialement,
Mes-Reves — Dikenga Design
{SITE_URL}

--
Pour ne plus recevoir ces emails : répondez STOP."""

    # ── STEP 3 — dernière relance ─────────────────────────
    else:
        subj = f"Dernière relance — {domain}"
        body = f"""Bonjour,

Je ferme mon dossier sur {domain}.

Si vous cherchez un designer UI/UX quand le moment sera venu, mon portfolio : {SITE_URL}

Bonne continuation,
Mes-Reves — Dikenga Design"""

    return {'subject': subj, 'body': body}

# ═══════════════════════════════════════════════════════════
# SEQUENCER
# ═══════════════════════════════════════════════════════════

def get_prospects_to_contact():
    today = datetime.now().date().isoformat()
    with get_conn() as c:
        s1 = c.execute("""
            SELECT * FROM prospects WHERE status='queued'
              AND email IS NOT NULL AND email!='' AND score>=? AND sequence_step=0
            ORDER BY score DESC LIMIT ?
        """, (MIN_SCORE, MAX_EMAILS_PER_RUN)).fetchall()
        s2 = c.execute("""
            SELECT * FROM prospects WHERE status='emailed_1'
              AND next_action<=? AND replied=0 AND bounced=0
            ORDER BY score DESC
        """, (today,)).fetchall()
        s3 = c.execute("""
            SELECT * FROM prospects WHERE status='emailed_2'
              AND next_action<=? AND replied=0 AND bounced=0
            ORDER BY score DESC
        """, (today,)).fetchall()
    return list(s1), list(s2), list(s3)

def mark_emailed(pid, step, variant, subject):
    status_map = {1:'emailed_1', 2:'emailed_2', 3:'emailed_3'}
    delay = FOLLOW_UP_DELAYS.get(step + 1)
    next_action = (
        (datetime.now() + timedelta(days=delay)).date().isoformat()
        if delay else None)
    with get_conn() as c:
        c.execute(f"""
            UPDATE prospects
            SET status=?, sequence_step=?, variant=?, date_step{step}=?, next_action=?
            WHERE id=?
        """, (status_map[step], step, variant,
              datetime.now().isoformat(), next_action, pid))
    log_event(pid, f'emailed_{step}', {'variant': variant, 'subject': subject})

# ═══════════════════════════════════════════════════════════
# SENDER
# ═══════════════════════════════════════════════════════════

def send_email(prospect_row, step, variant):
    pid  = prospect_row['id']
    to   = prospect_row['email']
    tmpl = get_template(variant, prospect_row, step)

    if not SMTP_PASS:
        print(f"  [DRY RUN] → {to}  |  {tmpl['subject'][:60]}")
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
        print(f"  ❌ {to}: {e}")
        with get_conn() as c:
            c.execute("UPDATE prospects SET status='error', notes=? WHERE id=?",
                      (str(e)[:200], pid))
        log_event(pid, 'error', {'step': step, 'error': str(e)})
        return False

# ═══════════════════════════════════════════════════════════
# IMAP — Réponses + Bounces
# ═══════════════════════════════════════════════════════════

def check_replies():
    if not SMTP_PASS:
        return 0
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx) as imap:
            imap.login(SMTP_USER, SMTP_PASS)
            imap.select('INBOX')
            since = (datetime.now() - timedelta(days=21)).strftime('%d-%b-%Y')

            with get_conn() as c:
                emailed = c.execute("""
                    SELECT id, domain, email FROM prospects
                    WHERE status IN ('emailed_1','emailed_2','emailed_3')
                      AND replied=0 AND bounced=0
                """).fetchall()
            if not emailed:
                return 0

            by_domain = {r['domain']: r for r in emailed}
            by_email  = {(r['email'] or '').lower(): r for r in emailed if r['email']}
            count = 0

            # Réponses normales
            _, data = imap.search(None, f'(SINCE {since})')
            for num in (data[0].split() if data[0] else []):
                try:
                    _, msg_data = imap.fetch(num, '(RFC822.HEADER)')
                    msg  = _email_mod.message_from_bytes(msg_data[0][1])
                    frm  = msg.get('From', '').lower()
                    matched = next(
                        (r for dom, r in by_domain.items() if dom in frm), None
                    ) or next(
                        (r for em, r in by_email.items() if em and em in frm), None
                    )
                    if matched:
                        with get_conn() as c:
                            c.execute("UPDATE prospects SET replied=1, status='replied' WHERE id=?",
                                      (matched['id'],))
                        log_event(matched['id'], 'replied', {'from': frm[:100]})
                        count += 1
                        print(f"  📩 Réponse : {matched['domain']}")
                except Exception:
                    pass

            # Bounces MAILER-DAEMON
            _, bd = imap.search(None, f'(SINCE {since} FROM "MAILER-DAEMON")')
            for num in (bd[0].split() if bd[0] else []):
                try:
                    _, msg_data = imap.fetch(num, '(RFC822)')
                    raw = msg_data[0][1].decode('utf-8', errors='ignore').lower()
                    for em, r in by_email.items():
                        if em and em in raw:
                            with get_conn() as c:
                                c.execute("UPDATE prospects SET bounced=1, status='bounced' WHERE id=?",
                                          (r['id'],))
                            log_event(r['id'], 'bounced', {})
                            print(f"  ⚠️  Bounce : {em}")
                except Exception:
                    pass
            return count
    except Exception as e:
        print(f"  IMAP error: {e}")
        return 0

# ═══════════════════════════════════════════════════════════
# REPORTER — Funnel Telegram
# ═══════════════════════════════════════════════════════════

def build_report(stats):
    today = datetime.now().strftime('%d/%m/%Y %H:%M')
    with get_conn() as c:
        tot = dict(c.execute("""
            SELECT COUNT(*) total,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN sequence_step>=1 THEN 1 ELSE 0 END) total_emailed,
              SUM(CASE WHEN replied=1    THEN 1 ELSE 0 END) total_replied,
              SUM(CASE WHEN bounced=1    THEN 1 ELSE 0 END) total_bounced,
              SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) queued,
              SUM(CASE WHEN status IN ('emailed_1','emailed_2') THEN 1 ELSE 0 END) pending
            FROM prospects
        """).fetchone())
        # Taux email par source
        src_stats = c.execute("""
            SELECT source,
              COUNT(*) n,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email
            FROM prospects GROUP BY source
        """).fetchall()

    a = stats['analyzed']
    w = stats['with_email']
    sent = stats['sent']
    rep  = stats['new_replies']

    email_rate  = f"{w/a*100:.0f}%" if a else "—"
    reply_rate  = f"{tot['total_replied']/tot['total_emailed']*100:.1f}%" if tot['total_emailed'] else "—"

    src_lines = ""
    for r in src_stats:
        rate = f"{r['with_email']/r['n']*100:.0f}%" if r['n'] else "—"
        src_lines += f"\n  {r['source']:12} {r['n']:3} prospects  email:{rate}"

    ab_line = ""
    if stats.get('step1_A') or stats.get('step1_B'):
        ab_line = f"\n  A/B step1 → A:{stats.get('step1_A',0)}  B:{stats.get('step1_B',0)}"

    alert = ""
    if rep > 0:
        alert = (f"\n\n🔔 <b>{rep} réponse{'s' if rep>1 else ''} reçue{'s' if rep>1 else ''}"
                 f" — <a href='{ZIMBRA_URL}'>ouvre Zimbra</a></b>")

    return (
        f"📊 <b>Dikenga Acquisition v3 — {today}</b>\n\n"
        f"<b>🔍 Run du jour</b>\n"
        f"  Analysés : {a}  |  Emails trouvés : {w} ({email_rate})\n"
        f"  Envoyés : {sent}  (step1:{stats.get('s1',0)}  relances:{stats.get('s2',0)+stats.get('s3',0)})"
        f"{ab_line}\n"
        f"  Nouvelles réponses IMAP : {rep}\n\n"
        f"<b>📈 Pipeline total</b>\n"
        f"  En base : {tot['total']}  |  Emailés : {tot['total_emailed']}\n"
        f"  En attente relance : {tot['pending']}  |  File : {tot['queued']}\n\n"
        f"<b>🎯 Taux globaux</b>\n"
        f"  Email trouvé / analysé : {email_rate}\n"
        f"  Réponse / emailé : {reply_rate}  |  Bounces : {tot['total_bounced']}\n\n"
        f"<b>📡 Taux par source</b>{src_lines}"
        f"{alert}"
    )

# ═══════════════════════════════════════════════════════════
# CSV BACKUP
# ═══════════════════════════════════════════════════════════

def export_csv():
    cols = ['domain','company','email','tech','perf_mobile','score','lcp',
            'issues','source','status','date_added','sequence_step','variant','notes']
    with get_conn() as c:
        rows = c.execute(
            f"SELECT {','.join(cols)} FROM prospects ORDER BY date_added DESC"
        ).fetchall()
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'═'*56}")
    print(f"  Dikenga Acquisition DATA-DRIVEN v3")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*56}\n")

    init_db()
    stats = {'analyzed':0,'with_email':0,'sent':0,
             's1':0,'s2':0,'s3':0,'step1_A':0,'step1_B':0,'new_replies':0}

    # ── 1. IMAP ──────────────────────────────────────────
    print("📩 Vérification des réponses IMAP…")
    stats['new_replies'] = check_replies()
    print(f"  → {stats['new_replies']} réponse(s)\n")

    # ── 2. DISCOVERY ─────────────────────────────────────
    print("🌐 Découverte multi-sources…")
    domain_source_pairs = discover_new_domains(n=MAX_ANALYZE_PER_RUN)
    print()

    # ── 3. ENRICHMENT ────────────────────────────────────
    if domain_source_pairs:
        print(f"📊 Analyse de {len(domain_source_pairs)} domaines…\n")
        for domain, source in domain_source_pairs[:MAX_ANALYZE_PER_RUN]:
            try:
                data  = enrich_domain(domain, source)
                sc    = compute_score(data['perf_mobile'], data['tech'], data['issues'])
                has_em = bool(data['email'])

                if has_em and sc >= MIN_SCORE:  status = 'queued'
                elif not has_em:                status = 'no_email'
                else:                           status = 'low_score'

                with get_conn() as c:
                    c.execute("""
                        INSERT OR IGNORE INTO prospects
                          (domain,company,email,tech,perf_mobile,lcp,issues,
                           score,source,status,date_added,date_analyzed)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        data['domain'], data['company'], data['email'],
                        data['tech'], data['perf_mobile'], data['lcp'],
                        json.dumps(data['issues']),
                        sc, source, status,
                        datetime.now().date().isoformat(),
                        datetime.now().isoformat()
                    ))

                stats['analyzed'] += 1
                if has_em: stats['with_email'] += 1
                src_tag = {'pagesjunes':'📒','yelp':'🍴','ddg':'🔍'}.get(source,'🌐')
                print(f"  {src_tag} {domain}: {data['tech']} | perf={data['perf_mobile']} "
                      f"| score={sc} | email={'✅' if has_em else '❌'}")
            except Exception as e:
                print(f"  ⚠️  {domain}: {e}")
            time.sleep(1.2)
        print()

    # ── 4. SEND ───────────────────────────────────────────
    print("📧 Envoi des emails…\n")
    s1, s2, s3 = get_prospects_to_contact()
    total_sent = 0
    variants   = ['A', 'B']

    for i, p in enumerate(s1):
        if total_sent >= MAX_EMAILS_PER_RUN: break
        v = variants[i % 2]
        if send_email(p, 1, v):
            total_sent += 1; stats['s1'] += 1; stats[f'step1_{v}'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s2:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        if send_email(p, 2, dict(p).get('variant', 'A') or 'A'):
            total_sent += 1; stats['s2'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s3:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        if send_email(p, 3, dict(p).get('variant', 'A') or 'A'):
            total_sent += 1; stats['s3'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    # ── 5. BACKUP + REPORT ───────────────────────────────
    export_csv()
    print(f"\n✅ CSV exporté")

    print("📱 Rapport Telegram…")
    report = build_report(stats)
    tg(report)
    print(report)

    print(f"\n{'═'*56}")
    print(f"  Done — {total_sent} emails  |  {stats['new_replies']} réponses")
    print(f"{'═'*56}\n")


if __name__ == '__main__':
    main()
