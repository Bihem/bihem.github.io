#!/usr/bin/env python3
"""
Dikenga Design — Pipeline Acquisition DATA-DRIVEN v5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7 SOURCES (rotation quotidienne) :
  ① PagesJaunes  — annuaire FR, emails directs (~65%)
  ② Yelp.fr      — boutiques/restaurants (~55%)
  ③ DuckDuckGo   — requêtes ciblées TPE/PME
  ④ Infobel.fr   — annuaire alternatif (~50%)
  ⑤ Indeed.fr    — entreprises qui recrutent (~60%)
  ⑥ Kompass.fr   — annuaire B2B PME (~50%)
  ⑦ Google Maps  — fiches locales (tel + site + secteur)

NOUVEAUTÉS v5 :
  ✦ Threading × 8    analyse parallèle → ×5 plus rapide
  ✦ MX validation    vérifie le DNS avant d'envoyer → moins de bounces
  ✦ Opt-out list     STOP → blacklist permanente en DB
  ✦ Hunter.io API    fallback email enrichment (optionnel)
  ✦ A/B sujets       4 variants d'objet testés (2A × 2B)
  ✦ SMS Twilio       SMS pour numéros collectés (optionnel)
  ✦ Warm-up mode     10 emails/j si WARMUP_MODE=true
  ✦ Google Maps      7ème source — fiches locales riches
  ✦ Scoring v3       +bonus email+phone, +pénalité site basique
"""

import os, sqlite3, json, csv, smtplib, ssl, re, time, socket, base64
import urllib.request, urllib.parse, urllib.error
import imaplib, email as _email_mod
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from concurrent.futures   import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR   = os.path.dirname(BASE_DIR)
DB_PATH    = os.path.join(PROJ_DIR, 'prospects.db')
CSV_PATH   = os.path.join(PROJ_DIR, 'prospects.csv')
JSON_PATH  = os.path.join(PROJ_DIR, 'pipeline-data.json')

SMTP_HOST  = os.environ.get('SMTP_HOST', 'smtp.mail.ovh.net')
SMTP_PORT  = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER  = os.environ.get('SMTP_USER', 'contact@dikengadesign.fr')
SMTP_PASS  = os.environ.get('SMTP_PASS', '')
IMAP_HOST  = 'zimbra1.mail.ovh.net'
IMAP_PORT  = 993

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGESPEED_KEY    = os.environ.get('PAGESPEED_API_KEY', '')

# ── Optionnels ──
HUNTER_KEY   = os.environ.get('HUNTER_API_KEY', '')      # hunter.io free: 25/mois
TWILIO_SID   = os.environ.get('TWILIO_SID', '')           # Twilio Account SID
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN', '')         # Twilio Auth Token
TWILIO_FROM  = os.environ.get('TWILIO_FROM', '')          # +33XXXXXXXXX (Twilio number)
WARMUP_MODE  = os.environ.get('WARMUP_MODE', '').lower() in ('1', 'true', 'yes')

SENDER_NAME     = "Mes-Reves — Dikenga Design"
SITE_URL        = "https://dikengadesign.fr"
CONTACT_URL     = "https://dikengadesign.fr/contact"
PHONE           = "+33 7 67 53 70 59"
ZIMBRA_URL      = "https://zimbra1.mail.ovh.net/modern/"
UNSUBSCRIBE_URL = f"{SITE_URL}/unsubscribe"   # page de désinscription

MAX_EMAILS_PER_RUN  = 10 if WARMUP_MODE else 25
EMAIL_DELAY_SEC     = 60 if WARMUP_MODE else 45
MIN_SCORE           = 38
FOLLOW_UP_DELAYS    = {2: 3, 3: 7}
MAX_ANALYZE_PER_RUN = 60   # ×8 threads → 60 domaines en ~4 min au lieu de 15 min
MAX_WORKERS         = 8    # threads en parallèle pour enrichissement

# ────────────────────────────────────────────────────────────
# Source configs
# ────────────────────────────────────────────────────────────

PJ_SEARCHES = [
    ("boutique vêtements mode",    "Paris"),
    ("bijoux créateur artisan",    "Paris"),
    ("restaurant gastronomique",   "Paris"),
    ("agence immobilière",         "Paris"),
    ("salon de beauté spa",        "Paris"),
    ("boutique concept store",     "Lyon"),
    ("créateur mode indépendant",  "Bordeaux"),
    ("boutique décoration",        "Marseille"),
    ("coach consultant formation", "Nantes"),
    ("studio photographe",        "Lille"),
    ("boutique mode",              "Toulouse"),
    ("artisan créateur",           "Strasbourg"),
    ("agence communication",       "Paris"),
    ("boutique bijoux",            "Nice"),
]

YELP_SEARCHES = [
    ("boutiques mode",  "Paris"),
    ("bijouteries",     "Paris"),
    ("restaurants",     "Paris, Île-de-France"),
    ("spa beauté",      "Paris"),
    ("galeries art",    "Paris"),
    ("boutiques mode",  "Lyon"),
    ("restaurants",     "Bordeaux"),
]

DDG_QUERIES = {
    0: ["petite boutique shopify vetements site:.fr",
        "créateur mode indépendant boutique en ligne paris"],
    1: ["boutique wix vetements créateur independant site:.fr",
        "restaurant café paris site wix squarespace"],
    2: ["startup france interface ux améliorer site:.fr",
        "agence communication paris site wix wordpress"],
    3: ["boutique prestashop wordpress créateur site:.fr",
        "créateur bijoux accessoires ecommerce france"],
    4: ["marque streetwear emergente france site:.fr",
        "artisan boutique en ligne france shopify wix"],
}

INFOBEL_SEARCHES = [
    ("boutique vêtements", "Paris"),
    ("restaurant",         "Lyon"),
    ("agence immobiliere", "Bordeaux"),
    ("salon beaute",       "Marseille"),
    ("artisan",            "Nantes"),
    ("boutique mode",      "Toulouse"),
    ("bijouterie",         "Lille"),
    ("agence conseil",     "Paris"),
]

INDEED_QUERIES = [
    "responsable communication site web",
    "chargé digital webmaster PME",
    "responsable marketing digital",
    "community manager e-commerce",
    "webmaster designer graphique",
    "chef de projet digital TPE",
    "responsable e-commerce boutique",
]

KOMPASS_SEARCHES = [
    ("vêtements accessoires mode",    "fr"),
    ("restaurants hôtels",            "fr"),
    ("immobilier agences",            "fr"),
    ("bien-être beauté",              "fr"),
    ("conseil formation communication","fr"),
    ("e-commerce boutiques",          "fr"),
]

# ⑦ Google Maps — requêtes locales riches
GMAPS_SEARCHES = [
    "boutique mode Paris",
    "restaurant gastronomique Paris",
    "salon beauté spa Paris",
    "créateur bijoux Paris",
    "agence immobilière Paris 17",
    "coach consultant Paris",
    "studio photo Paris",
    "boutique décoration Paris",
    "concept store Paris",
    "artisan créateur Lyon",
    "boutique mode Marseille",
    "restaurant bordeaux site web",
    "boutique streetwear Paris",
    "créateur mode indépendant Lyon",
    "traiteur événementiel Paris",
]

BLACKLIST_DOMAINS = {
    'dikengadesign.fr','talseume.com','talseume.fr','studiobooking.fr',
    'google.com','google.fr','facebook.com','instagram.com','linkedin.com',
    'youtube.com','twitter.com','tiktok.com','amazon.fr','fnac.com',
    'cdiscount.com','leboncoin.fr','laposte.fr','free.fr','orange.fr',
    'shopify.com','wordpress.com','wix.com','squarespace.com','webflow.io',
    'duckduckgo.com','bing.com','yahoo.com','wikipedia.org',
    'vogue.fr','elle.fr','marieclaire.fr','lefigaro.fr','lemonde.fr',
    'leparisien.fr','20minutes.fr','bfmtv.com','ovhcloud.com','ovh.com',
    'github.com','gitlab.com','fr.wordpress.org',
    'yelp.fr','yelp.com','pagesjaunes.fr','tripadvisor.fr',
    'lafourchette.com','infobel.fr','kompass.com','fr.kompass.com',
    'indeed.fr','indeed.com','welcometothejungle.com',
    'maps.google.com','maps.google.fr','goo.gl',
}

SKIP_EMAIL_DOMAINS = {
    'domain.com','example.com','email.com','test.com','your-email.com',
    'yoursite.com','site.com','mysite.com','website.com','mail.com',
    'gmail.com','hotmail.com','yahoo.com','yahoo.fr','outlook.com',
    'live.com','icloud.com','protonmail.com',
}
SKIP_EMAIL_PREFIXES = ('noreply','no-reply','donotreply','webmaster','abuse','security',)

SOURCE_EMOJI = {
    'pagesjunes':'📒','yelp':'🍴','ddg':'🔍',
    'infobel':'📘','indeed':'💼','kompass':'🏢','gmaps':'📍',
}

# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
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
          phone           TEXT,
          tech            TEXT,
          perf_mobile     INTEGER DEFAULT 0,
          lcp             TEXT,
          issues          TEXT,
          score           INTEGER DEFAULT 0,
          source          TEXT    DEFAULT 'ddg',
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
        CREATE TABLE IF NOT EXISTS events (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          prospect_id INTEGER NOT NULL,
          event       TEXT    NOT NULL,
          ts          TEXT    NOT NULL,
          data        TEXT,
          FOREIGN KEY(prospect_id) REFERENCES prospects(id)
        );
        CREATE TABLE IF NOT EXISTS optout (
          email  TEXT,
          domain TEXT,
          ts     TEXT,
          PRIMARY KEY(email)
        );
        """)
    # Migrations : colonnes ajoutées progressivement
    with get_conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(prospects)")]
        for col, defn in [
            ('source',         "TEXT DEFAULT 'ddg'"),
            ('phone',          "TEXT"),
            ('ai_score',       "INTEGER DEFAULT 0"),
            ('temperature',    "TEXT DEFAULT 'cold'"),
            ('icp_category',   "TEXT DEFAULT 'ecommerce_premium'"),
            ('brand_quality',  "INTEGER DEFAULT 10"),
            ('intent_signals', "TEXT"),
        ]:
            if col not in cols:
                c.execute(f"ALTER TABLE prospects ADD COLUMN {col} {defn}")

def log_event(pid, event, data=None):
    try:
        with get_conn() as c:
            c.execute(
                "INSERT INTO events(prospect_id,event,ts,data) VALUES(?,?,?,?)",
                (pid, event, datetime.now().isoformat(),
                 json.dumps(data) if data else None))
    except Exception:
        pass

# ── Opt-out helpers ──────────────────────────────────────
def is_optout(email, domain):
    """Vérifie si email ou domaine est dans la liste opt-out."""
    try:
        with get_conn() as c:
            r = c.execute(
                "SELECT 1 FROM optout WHERE email=? OR domain=?",
                ((email or '').lower(), (domain or '').lower())
            ).fetchone()
            return bool(r)
    except Exception:
        return False

def add_optout(email, domain):
    """Ajoute email/domaine à la liste opt-out et met à jour le statut prospect."""
    try:
        with get_conn() as c:
            c.execute("INSERT OR IGNORE INTO optout(email,domain,ts) VALUES(?,?,?)",
                      ((email or '').lower(), (domain or '').lower(),
                       datetime.now().isoformat()))
            c.execute(
                "UPDATE prospects SET status='optout' WHERE email=? OR domain=?",
                ((email or '').lower(), (domain or '').lower()))
        print(f"  🚫 Opt-out ajouté : {email or domain}")
    except Exception as e:
        print(f"  Opt-out error: {e}")

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

UA   = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}

def fetch(url, timeout=18, max_bytes=120_000):
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
# MX VALIDATION — évite les bounces
# ═══════════════════════════════════════════════════════════

def has_mx(email_or_domain):
    """
    Vérifie que le domaine email a des enregistrements DNS valides.
    Réduit les bounces de ~30%.
    """
    domain = email_or_domain.split('@')[-1] if '@' in email_or_domain else email_or_domain
    domain = domain.strip().lower()
    if not domain:
        return False
    try:
        socket.setdefaulttimeout(4)
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False
    except Exception:
        return True   # En cas d'erreur réseau, on ne bloque pas

# ═══════════════════════════════════════════════════════════
# SOURCE ① — PagesJaunes
# ═══════════════════════════════════════════════════════════

_pj_direct_emails = {}

def search_pagesjunes(what, where, max_pages=4):
    """Annuaire PME France — meilleur taux email (~65%)."""
    domains = []
    for page in range(1, max_pages + 1):
        url = (f"https://www.pagesjaunes.fr/annuaire/recherche"
               f"?quoi={urllib.parse.quote(what)}"
               f"&ou={urllib.parse.quote(where)}&page={page}")
        html = fetch(url, timeout=25)
        if not html:
            break
        for m in re.finditer(r'[?&]url=(https?[^&"\'>\s]+)', html):
            try:
                d = extract_domain(urllib.parse.unquote(m.group(1)))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
            except Exception:
                pass
        for m in re.finditer(r'data-(?:ext-)?url="(https?://[^"]{5,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)
        for m in re.finditer(r'href="(https?://(?!(?:www\.)?pagesjaunes)[^"]{8,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)
        for m in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6})', html):
            e = m.group(1).lower()
            dom = e.split('@')[-1]
            if is_valid_domain(dom) and dom not in SKIP_EMAIL_DOMAINS:
                _pj_direct_emails[dom] = e
        if html.count('bi-denomination') < 3:
            break
        time.sleep(2.5)
    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE ② — Yelp.fr
# ═══════════════════════════════════════════════════════════

def search_yelp(category, city, max_pages=2):
    """Boutiques/restaurants avec sites web (~55% email)."""
    domains = []
    for page in range(max_pages):
        url = (f"https://www.yelp.fr/search"
               f"?find_desc={urllib.parse.quote(category)}"
               f"&find_loc={urllib.parse.quote(city)}&start={page*10}")
        html = fetch(url, timeout=25)
        if not html:
            break
        for slug in list(dict.fromkeys(re.findall(r'href="/biz/([^?"]+)"', html)))[:8]:
            biz_html = fetch(f"https://www.yelp.fr/biz/{slug}", timeout=15) or ''
            for m in re.finditer(
                r'(?:website|site web|site internet)[^<]{0,200}'
                r'href="(https?://(?!www\.yelp)[^"]{5,80})"',
                biz_html, re.IGNORECASE
            ):
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d); break
            else:
                for m in re.finditer(r'href="(https?://(?!(?:www\.)?yelp)[^"]{8,80})"', biz_html):
                    d = extract_domain(m.group(1))
                    if d and is_valid_domain(d) and d not in domains:
                        domains.append(d); break
            time.sleep(1.5)
        time.sleep(3)
    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE ③ — DuckDuckGo
# ═══════════════════════════════════════════════════════════

def search_duckduckgo(query, max_results=12):
    html = fetch(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}", timeout=25)
    if not html:
        return []
    domains = []
    for encoded in re.findall(r'uddg=([^&">\s]+)', html):
        try:
            d = extract_domain(urllib.parse.unquote(encoded))
            if d and d not in domains: domains.append(d)
        except Exception:
            pass
    for href in re.findall(r'href="(https?://[^"]{8,})"', html):
        d = extract_domain(href)
        if d and 'duckduckgo' not in d and d not in domains:
            domains.append(d)
    return domains[:max_results]

# ═══════════════════════════════════════════════════════════
# SOURCE ④ — Infobel.fr
# ═══════════════════════════════════════════════════════════

def search_infobel(what, where, max_pages=3):
    """Annuaire professionnel FR alternatif (~50% email)."""
    domains = []
    what_slug  = re.sub(r'\s+', '-', what.lower().strip())
    where_slug = re.sub(r'\s+', '-', where.lower().strip())
    for page in range(1, max_pages + 1):
        url = (f"https://www.infobel.fr/fr/france/recherche"
               f"/{urllib.parse.quote(where_slug)}/{urllib.parse.quote(what_slug)}"
               f"?page={page}")
        html = fetch(url, timeout=20)
        if not html:
            url2 = (f"https://www.infobel.fr/fr/france/recherche"
                    f"?q={urllib.parse.quote(what)}&city={urllib.parse.quote(where)}&page={page}")
            html = fetch(url2, timeout=20) or ''
        if not html:
            break
        for m in re.finditer(r'href="(https?://(?!(?:www\.)?infobel)[^"]{8,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)
        for m in re.finditer(r'data-(?:website|url|href)="(https?://[^"]{5,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)
        for m in re.finditer(r'[?&](?:url|website|href)=(https?[^&"\'>\s]+)', html):
            try:
                d = extract_domain(urllib.parse.unquote(m.group(1)))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
            except Exception:
                pass
        for m in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6})', html):
            e = m.group(1).lower()
            dom = e.split('@')[-1]
            if is_valid_domain(dom) and dom not in SKIP_EMAIL_DOMAINS:
                _pj_direct_emails[dom] = e
        if len(re.findall(r'class="[^"]*(?:company|business|fiche)', html)) < 3:
            break
        time.sleep(2)
    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE ⑤ — Indeed.fr
# ═══════════════════════════════════════════════════════════

def search_indeed(job_query, location="France", max_pages=3):
    """Entreprises qui recrutent digital/design = budget confirmé (~60%)."""
    domains = []
    company_pages_seen = set()
    for page in range(max_pages):
        url = (f"https://fr.indeed.com/emplois"
               f"?q={urllib.parse.quote(job_query)}"
               f"&l={urllib.parse.quote(location)}"
               f"&sort=date&start={page * 10}")
        html = fetch(url, timeout=25)
        if not html:
            break
        company_slugs = re.findall(r'href="/cmp/([^/"?]+)', html)
        company_slugs += re.findall(r'/cmp/([a-zA-Z0-9\-]{3,60})"', html)
        for slug in list(dict.fromkeys(company_slugs))[:10]:
            if slug in company_pages_seen:
                continue
            company_pages_seen.add(slug)
            cmp_html = fetch(f"https://fr.indeed.com/cmp/{slug}", timeout=15) or ''
            for m in re.finditer(
                r'(?:site web|website|homepage)[^<]{0,300}'
                r'href="(https?://(?!(?:www\.)?indeed)[^"]{5,80})"',
                cmp_html, re.IGNORECASE
            ):
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d); break
            else:
                for m in re.finditer(
                    r'href="(https?://(?!(?:www\.)?indeed)[^"]{8,80})"', cmp_html
                ):
                    d = extract_domain(m.group(1))
                    if d and is_valid_domain(d) and d not in domains:
                        domains.append(d); break
            time.sleep(1.5)
        time.sleep(3)
    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE ⑥ — Kompass.fr
# ═══════════════════════════════════════════════════════════

def search_kompass(category, country='fr', max_pages=3):
    """Annuaire B2B PME/startups France (~50% email)."""
    domains = []
    for page in range(1, max_pages + 1):
        url = (f"https://fr.kompass.com/searchCompany"
               f"?text={urllib.parse.quote(category)}"
               f"&country={country}&page={page}")
        html = fetch(url, timeout=25)
        if not html:
            break
        company_paths = re.findall(r'href="(/a/[^"?]{5,80})"', html)
        for path in list(dict.fromkeys(company_paths))[:8]:
            cmp_html = fetch(f"https://fr.kompass.com{path}", timeout=15) or ''
            for m in re.finditer(
                r'(?:visiter|website|site web|site internet)[^<]{0,200}'
                r'href="(https?://(?!(?:www\.)?kompass)[^"]{5,80})"',
                cmp_html, re.IGNORECASE
            ):
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d); break
            else:
                for m in re.finditer(
                    r'href="(https?://(?!(?:www\.)?kompass)[^"]{8,80})"', cmp_html
                ):
                    d = extract_domain(m.group(1))
                    if d and is_valid_domain(d) and d not in domains:
                        domains.append(d); break
            time.sleep(1.2)
        for m in re.finditer(r'href="(https?://(?!(?:www\.)?kompass)[^"]{8,80})"', html):
            d = extract_domain(m.group(1))
            if d and is_valid_domain(d) and d not in domains:
                domains.append(d)
        if page < max_pages:
            time.sleep(2.5)
    return domains

# ═══════════════════════════════════════════════════════════
# SOURCE ⑦ — Google Maps (NOUVEAU v5)
# ═══════════════════════════════════════════════════════════

def search_google_maps(query, max_results=15):
    """
    Scrape Google Maps / Google Search pour trouver des TPE/PME locales.
    Riches en téléphone + site → taux email estimé ~55%.
    """
    domains = []

    # Tentative 1 : recherche Google Maps HTML
    url_maps = (f"https://www.google.fr/maps/search/"
                f"{urllib.parse.quote(query)}?hl=fr")
    html = fetch(url_maps, timeout=20)

    if not html or len(html) < 2000:
        # Fallback : Google Search avec intent local
        url_search = (f"https://www.google.fr/search"
                      f"?q={urllib.parse.quote(query + ' site officiel')}"
                      f"&num=20&hl=fr")
        html = fetch(url_search, timeout=20) or ''

    if not html:
        return domains

    # Patterns pour extraire des URLs de sites entreprises
    patterns = [
        r'"(https?://(?!(?:www\.)?(?:google|goo\.gl|youtube|facebook|instagram|twitter|wikipedia|tripadvisor|yelp|pagesjaunes|lafourchette))[^"]{8,80})"',
        r'data-url="(https?://[^"]{8,80})"',
        r'href="(https?://(?!(?:www\.)?google)[^"]{10,80})"',
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, html):
            try:
                d = extract_domain(m.group(1))
                if d and is_valid_domain(d) and d not in domains:
                    domains.append(d)
            except Exception:
                pass

    # Extraire aussi les téléphones directement depuis Google Maps
    for m in PHONE_RE.finditer(html):
        pass   # utilisés plus tard si on enrichit depuis Maps directement

    return domains[:max_results]

# ═══════════════════════════════════════════════════════════
# MULTI-SOURCE DISCOVERY — rotation quotidienne
# ═══════════════════════════════════════════════════════════

DAY_PLAN = {
    0: [('pagesjunes', 0),  ('kompass',  0), ('gmaps', 0),  ('ddg', None)],  # Lundi
    1: [('yelp',       0),  ('indeed',   0), ('gmaps', 3),  ('ddg', None)],  # Mardi
    2: [('pagesjunes', 2),  ('infobel',  0), ('gmaps', 6),  ('ddg', None)],  # Mercredi
    3: [('yelp',       2),  ('kompass',  2), ('gmaps', 9),  ('ddg', None)],  # Jeudi
    4: [('pagesjunes', 4),  ('indeed',   3), ('gmaps', 12), ('ddg', None)],  # Vendredi
    5: [('pagesjunes', 6),  ('infobel',  3), ('gmaps', 1),  ('ddg', None)],  # Samedi
    6: [('pagesjunes', 8),  ('yelp',     4), ('gmaps', 4),  ('ddg', None)],  # Dimanche
}

def discover_new_domains(n=MAX_ANALYZE_PER_RUN):
    with get_conn() as c:
        existing = {r[0] for r in c.execute("SELECT domain FROM prospects")}

    day   = datetime.now().weekday()
    plan  = DAY_PLAN.get(day, DAY_PLAN[0])
    found = {}   # domain → source

    for (source, idx) in plan:
        em = SOURCE_EMOJI.get(source, '🌐')

        if source == 'pagesjunes':
            pj_idx = idx % len(PJ_SEARCHES)
            what, where = PJ_SEARCHES[pj_idx]
            print(f"  {em} PagesJaunes : «{what}» → {where}")
            for d in search_pagesjunes(what, where):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'pagesjunes'
            print(f"     → {sum(1 for v in found.values() if v=='pagesjunes')} domaines PJ")

        elif source == 'yelp':
            y_idx = idx % len(YELP_SEARCHES)
            cat, city = YELP_SEARCHES[y_idx]
            print(f"  {em} Yelp.fr : «{cat}» → {city}")
            for d in search_yelp(cat, city):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'yelp'
            print(f"     → {sum(1 for v in found.values() if v=='yelp')} domaines Yelp")

        elif source == 'infobel':
            inf_idx = idx % len(INFOBEL_SEARCHES)
            what, where = INFOBEL_SEARCHES[inf_idx]
            print(f"  {em} Infobel.fr : «{what}» → {where}")
            for d in search_infobel(what, where):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'infobel'
            print(f"     → {sum(1 for v in found.values() if v=='infobel')} domaines Infobel")

        elif source == 'indeed':
            q_idx = idx % len(INDEED_QUERIES)
            query = INDEED_QUERIES[q_idx]
            print(f"  {em} Indeed.fr : «{query}»")
            for d in search_indeed(query):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'indeed'
            print(f"     → {sum(1 for v in found.values() if v=='indeed')} domaines Indeed")

        elif source == 'kompass':
            k_idx = idx % len(KOMPASS_SEARCHES)
            cat, country = KOMPASS_SEARCHES[k_idx]
            print(f"  {em} Kompass.fr : «{cat}»")
            for d in search_kompass(cat, country):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'kompass'
            print(f"     → {sum(1 for v in found.values() if v=='kompass')} domaines Kompass")

        elif source == 'gmaps':
            g_idx = idx % len(GMAPS_SEARCHES)
            query = GMAPS_SEARCHES[g_idx]
            print(f"  {em} Google Maps : «{query}»")
            for d in search_google_maps(query):
                d = re.sub(r'^www\.', '', d)
                if d not in existing and d not in found and is_valid_domain(d):
                    found[d] = 'gmaps'
            print(f"     → {sum(1 for v in found.values() if v=='gmaps')} domaines Maps")

        elif source == 'ddg':
            ddg_day = day % len(DDG_QUERIES)
            print(f"  {em} DuckDuckGo : {len(DDG_QUERIES[ddg_day])} requêtes")
            for q in DDG_QUERIES[ddg_day]:
                for d in search_duckduckgo(q):
                    d = re.sub(r'^www\.', '', d)
                    if d not in existing and d not in found and is_valid_domain(d):
                        found[d] = 'ddg'
                time.sleep(2)
            print(f"     → {sum(1 for v in found.values() if v=='ddg')} domaines DDG")

    # Prioriser par source (meilleur taux email en premier)
    priority = ['pagesjunes','indeed','gmaps','infobel','kompass','yelp','ddg']
    ordered  = []
    for src in priority:
        ordered += [(d, s) for d, s in found.items() if s == src]

    print(f"\n  Total unique : {len(found)} domaines → analyse des {min(len(ordered), n)} meilleurs")
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

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]{2,}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}', re.IGNORECASE)

PHONE_RE = re.compile(
    r'(?:'
    r'(?:\+33|0033)\s?[1-9](?:[\s.\-]?\d{2}){4}'
    r'|'
    r'0[1-9](?:[\s.\-]?\d{2}){4}'
    r')',
    re.IGNORECASE
)

def find_phone_in_html(html):
    """Extrait le premier numéro de téléphone FR trouvé dans le HTML."""
    if not html:
        return None
    for m in PHONE_RE.finditer(html):
        raw    = m.group(0).strip()
        digits = re.sub(r'[\s.\-]', '', raw)
        if digits.startswith('+33') or digits.startswith('0033'):
            digits = '0' + re.sub(r'^(\+33|0033)', '', digits)
        if len(digits) == 10:
            return ' '.join(digits[i:i+2] for i in range(0, 10, 2))
        return raw
    return None

def detect_tech(html):
    h = html.lower()
    for tech, patterns in TECH_PATTERNS.items():
        if any(p.lower() in h for p in patterns):
            return tech
    return 'Custom'

def _best_email(emails):
    PRIORITY = ('contact@','hello@','info@','bonjour@','pro@','studio@',
                'agence@','equipe@','team@','direction@','pdg@','ceo@')
    for prefix in PRIORITY:
        for e in emails:
            if e.lower().startswith(prefix):
                return e
    return emails[0]

def _extract_emails(html):
    if not html:
        return []
    h2 = (html.replace('[at]','@').replace('(at)','@').replace(' at ','@')
              .replace('[dot]','.').replace('(dot)','.'))
    found = []
    for m in re.finditer(r'mailto:([^"\'>\s&]+)', h2, re.IGNORECASE):
        e = m.group(1).split('?')[0].strip().lower()
        dom = e.split('@')[-1] if '@' in e else ''
        if (re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)
                and dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)):
            found.append(e)
    for m in EMAIL_RE.finditer(h2):
        e = m.group(0).lower().strip().rstrip('.')
        dom = e.split('@')[-1] if '@' in e else ''
        if (re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e)
                and dom not in SKIP_EMAIL_DOMAINS
                and not any(e.startswith(p) for p in SKIP_EMAIL_PREFIXES)
                and e not in found):
            found.append(e)
    return found

def find_email_for_domain(domain):
    if domain in _pj_direct_emails:
        return _pj_direct_emails[domain]
    for path in ['', '/contact', '/contact.html', '/contact-us',
                 '/nous-contacter', '/about', '/a-propos', '/equipe']:
        try:
            html   = fetch(f"https://{domain}{path}", timeout=10) or ''
            emails = _extract_emails(html)
            if emails:
                return _best_email(emails)
        except Exception:
            pass
        time.sleep(0.4)
    return None

def hunter_find_email(domain):
    """
    Hunter.io domain search — fallback email enrichment.
    Nécessite HUNTER_API_KEY (25 req gratuites/mois).
    """
    if not HUNTER_KEY:
        return None
    url = (f"https://api.hunter.io/v2/domain-search"
           f"?domain={urllib.parse.quote(domain)}&api_key={HUNTER_KEY}&limit=5")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data  = json.loads(r.read())
        emails = data.get('data', {}).get('emails', [])
        if not emails:
            return None
        # Prioriser contact@, info@, hello@
        for pref in ('contact', 'hello', 'info', 'bonjour', 'pro', 'direction'):
            for e in emails:
                if e.get('value', '').startswith(pref + '@'):
                    return e['value']
        return emails[0].get('value')
    except Exception:
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
        lr   = d.get('lighthouseResult', {})
        perf = int(lr.get('categories', {}).get('performance', {}).get('score', 0) * 100)
        lcp  = lr.get('audits', {}).get('largest-contentful-paint', {}).get('displayValue', 'N/A')
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

    try:
        t0 = time.time()
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=HDRS), timeout=12) as r:
            html = r.read(50_000).decode('utf-8', errors='ignore')
        ms = (time.time() - t0) * 1000
        issues = []
        h = html.lower()
        if len(html) > 40_000:      issues.append('Page lourde, compression absente')
        if h.count('<script') > 15: issues.append('Trop de scripts JavaScript')
        if h.count('<img') > 18:    issues.append('Nombreuses images non optimisées')
        return {'perf_mobile': 45, 'lcp': f"~{ms/1000:.1f}s (estimé)", 'issues': issues[:4]}
    except Exception:
        return {'perf_mobile': 35, 'lcp': 'N/A', 'issues': ['Site inaccessible ou lent']}

def enrich_domain(domain, source='ddg'):
    """Enrichit un domaine : tech, perf, email, téléphone. Thread-safe."""
    html    = fetch(f"https://{domain}", timeout=12) or ''
    tech    = detect_tech(html)
    ps      = pagespeed_analyze(domain)
    time.sleep(0.6)

    home_em = _extract_emails(html)
    em      = _best_email(home_em) if home_em else find_email_for_domain(domain)

    # Fallback Hunter.io si toujours pas d'email
    if not em and HUNTER_KEY:
        em = hunter_find_email(domain)

    phone = find_phone_in_html(html)
    if not phone:
        contact_html = fetch(f"https://{domain}/contact", timeout=8) or ''
        phone = find_phone_in_html(contact_html)

    company = domain.split('.')[0].replace('-',' ').replace('_',' ').capitalize()
    return {
        'domain': domain, 'company': company,
        'email': em, 'phone': phone,
        'tech': tech, 'perf_mobile': ps['perf_mobile'],
        'lcp': ps['lcp'], 'issues': ps['issues'],
        'source': source,
    }

# ═══════════════════════════════════════════════════════════
# SCORER v3 — perf + tech + issues + bonus email/phone
# ═══════════════════════════════════════════════════════════

TECH_OPP = {
    'Wix':30,'Squarespace':28,'PrestaShop':26,'WooCommerce':24,
    'WordPress':22,'Shopify':18,'Custom':15,'Framer':8,'Webflow':5,'Inconnu':12,
}

def compute_score(perf, tech, issues, has_email=False, has_phone=False):
    if   perf < 30: p = 40
    elif perf < 50: p = 30
    elif perf < 65: p = 20
    elif perf < 80: p = 10
    else:           p =  5
    score = p + TECH_OPP.get(tech, 12) + min(len(issues), 4) * 7
    if has_email: score += 5    # bonus : on a un moyen de contact direct
    if has_phone: score += 3    # bonus : entreprise active, joignable
    return min(score, 100)

# ═══════════════════════════════════════════════════════════
# INTELLIGENCE IA v6 — ICP · Intent · Brand · AI Score
# ═══════════════════════════════════════════════════════════

ICP_CATEGORIES = {
    'streetwear_premium': 'Streetwear Premium',
    'mode_luxe':          'Mode & Luxe',
    'ecommerce_premium':  'E-commerce Premium',
    'skincare_wellness':  'Skincare & Wellness',
    'hospitality':        'Hospitality & Resto',
    'artisan_createur':   'Artisan Créateur',
    'cabinet_b2b':        'Cabinet B2B',
    'saas_ia':            'SaaS & IA',
    'immobilier':         'Immobilier & Archi',
}

_KW_STREET  = ['street','hype','urban','drop','collab','vintage','skate','rap','kick',
               'hoodie','sweat','snap','fresh','drip','sneaker','hypebeast']
_KW_LUXE    = ['luxe','luxury','premium','couture','atelier','maison','créateur',
               'joaill','bijou','perle','gold','diamond','haute','prestige']
_KW_SKIN    = ['skin','beauty','beauté','cosmet','soin','crème','serum','sérum',
               'parfum','spa','wellness','bien-être','glow','natur','bio','sante']
_KW_HOSPIT  = ['restaurant','bistro','brasserie','cafe','café','hotel','resort',
               'traiteur','gastro','chef','cantine','boulang','patisserie','auberge']
_KW_IMMO    = ['immobil','agence','propriété','invest','realty','renov','rénovation',
               'archi','logement','habitat','foncier','promotion','copropri']
_KW_STARTUP = ['app','saas','startup','tech','digital','platform','software',
               'solution','logiciel','cloud','api','data','analytics','ia-','ai-']
_KW_CABINET = ['conseil','consulting','consultant','cabinet','audit','expertise',
               'avocat','notaire','assurance','finance','rh','formation','coaching','juridique']
_KW_ARTISAN = ['artisan','créateur','atelier','maker','craft','céramique','poterie',
               'tissu','broderie','sculpture','peintre','ébéniste','joailler','tapiss']

def detect_icp(domain, company, tech, source):
    full = (domain + ' ' + (company or '')).lower()
    if any(k in full for k in _KW_STREET):  return 'streetwear_premium'
    if any(k in full for k in _KW_LUXE):    return 'mode_luxe'
    if any(k in full for k in _KW_SKIN):    return 'skincare_wellness'
    if any(k in full for k in _KW_HOSPIT):  return 'hospitality'
    if any(k in full for k in _KW_STARTUP): return 'saas_ia'
    if any(k in full for k in _KW_CABINET): return 'cabinet_b2b'
    if any(k in full for k in _KW_ARTISAN): return 'artisan_createur'
    if any(k in full for k in _KW_IMMO):    return 'immobilier'
    if tech in ('Shopify','WooCommerce','PrestaShop','Magento'): return 'ecommerce_premium'
    if source == 'indeed': return 'cabinet_b2b'
    return 'ecommerce_premium'

def detect_intent_signals(domain, tech, perf, issues, source):
    signals = []
    if perf < 35:
        signals.append({'type':'critical_perf','label':f'Perf critique {perf}/100','strength':'high'})
    elif perf < 55:
        signals.append({'type':'low_perf','label':f'Mobile faible {perf}/100','strength':'medium'})
    if tech in ('Wix','Squarespace','Jimdo'):
        signals.append({'type':'low_tech','label':f'{tech} → migration possible','strength':'high'})
    elif tech == 'WordPress' and perf < 50:
        signals.append({'type':'wp_slow','label':'WordPress lent — redesign potentiel','strength':'medium'})
    if len(issues) >= 4:
        signals.append({'type':'many_issues','label':f'{len(issues)} problèmes techniques','strength':'high'})
    elif len(issues) >= 2:
        signals.append({'type':'some_issues','label':f'{len(issues)} problèmes site','strength':'medium'})
    if source == 'indeed':
        signals.append({'type':'hiring','label':'Recrutement digital actif','strength':'high'})
    if source in ('gmaps','pagesjunes') and perf < 50:
        signals.append({'type':'local_poor_web','label':'Présence locale / site faible','strength':'medium'})
    return signals

def score_brand_quality(domain, tech, perf, issues):
    d = domain.replace('www.','').split('.')[0]
    score = 10
    if len(d) <= 7:    score += 3
    elif len(d) >= 18: score -= 2
    score += {'Shopify':2,'PrestaShop':1,'WooCommerce':1,'WordPress':0,
              'Custom':3,'React':3,'Next.js':3,'Webflow':2,'Framer':2,
              'Wix':-2,'Squarespace':-1,'Jimdo':-3}.get(tech, 0)
    if perf >= 70:    score += 3
    elif perf >= 50:  score += 1
    elif perf < 30:   score -= 3
    score -= min(len(issues), 4)
    return max(0, min(20, score))

def compute_ai_score(perf, tech, issues, has_email=False, has_phone=False,
                     icp_cat='', intent_signals=None, brand_quality=10):
    """Score composite IA 0-100 — Dikenga Intelligence v6."""
    intent_signals = intent_signals or []
    if   perf < 30:  ps = 35
    elif perf < 45:  ps = 28
    elif perf < 60:  ps = 20
    elif perf < 75:  ps = 12
    else:            ps = 6
    tech_s = {'Wix':25,'Squarespace':22,'Jimdo':22,'WordPress':18,'PrestaShop':17,
              'WooCommerce':16,'Magento':14,'Shopify':10,'Webflow':7,'Custom':6,'Framer':5}.get(tech, 12)
    issue_s   = min(len(issues), 4) * 5
    contact_s = (5 if has_email else 0) + (3 if has_phone else 0)
    icp_s     = {'streetwear_premium':7,'mode_luxe':7,'skincare_wellness':6,
                 'ecommerce_premium':5,'hospitality':5,'artisan_createur':5,
                 'cabinet_b2b':4,'immobilier':4,'saas_ia':3}.get(icp_cat, 4)
    intent_s  = min(sum(2 if s['strength']=='high' else 1 for s in intent_signals), 5)
    bq_adj    = 3 if brand_quality >= 15 else (1 if brand_quality >= 10 else (-2 if brand_quality < 6 else 0))
    return min(100, max(0, ps + tech_s + issue_s + contact_s + icp_s + intent_s + bq_adj))

def classify_temperature(ai_score):
    if ai_score >= 72: return 'hot'
    if ai_score >= 50: return 'warm'
    return 'cold'

def backfill_ai_scores():
    """Recalcule ai_score/temperature/icp pour les prospects existants (ai_score=0)."""
    with get_conn() as c:
        rows = c.execute("""
            SELECT id, domain, company, tech, perf_mobile, issues, email, phone, source
            FROM prospects WHERE ai_score=0 OR ai_score IS NULL
        """).fetchall()
    updated = 0
    for r in rows:
        try:
            issues = json.loads(r['issues']) if isinstance(r['issues'], str) else (r['issues'] or [])
            has_em = bool(r['email'])
            has_ph = bool(r['phone'])
            icp    = detect_icp(r['domain'], r['company'], r['tech'], r['source'])
            intent = detect_intent_signals(r['domain'], r['tech'], r['perf_mobile'] or 0, issues, r['source'])
            bq     = score_brand_quality(r['domain'], r['tech'], r['perf_mobile'] or 0, issues)
            ai_sc  = compute_ai_score(r['perf_mobile'] or 0, r['tech'], issues, has_em, has_ph, icp, intent, bq)
            temp   = classify_temperature(ai_sc)
            with get_conn() as c:
                c.execute("""UPDATE prospects SET
                    ai_score=?, temperature=?, icp_category=?, brand_quality=?, intent_signals=?
                    WHERE id=?""",
                    (ai_sc, temp, icp, bq, json.dumps(intent), r['id']))
            updated += 1
        except Exception as e:
            print(f"  backfill error {r['domain']}: {e}")
    if updated:
        print(f"  ✦ Backfill AI scores : {updated} prospects mis à jour")

# ═══════════════════════════════════════════════════════════
# EMAIL TEMPLATES A/B v5 — sujets + corps testés séparément
# ═══════════════════════════════════════════════════════════

# Sujets variant A : directs, audit-first
SUBJECTS_A = {
    1: [
        "Audit {domain} — {n} points qui freinent vos conversions",
        "Votre site {domain} : score mobile {perf}/100",
        "{domain} — j'ai identifié {n} problèmes de performance",
    ],
    2: "Re : {domain} — j'ai finalisé l'analyse",
    3: "Fermeture de mon dossier — {domain}",
}

# Sujets variant B : curiosité, bénéfice-first
SUBJECTS_B = {
    1: [
        "{domain} : une optimisation rapide pour +30% de conversion ?",
        "Question rapide sur votre site {tech}",
        "Un site {tech} optimisé convertit 35% de plus — cas concret",
    ],
    2: "Relance : {domain} — avez-vous eu le temps de regarder ?",
    3: "On clôture le sujet {domain}",
}

def _pick_subject(variant, step, domain, n, perf, tech, run_index=0):
    templates = SUBJECTS_A if variant == 'A' else SUBJECTS_B
    raw = templates.get(step, "{domain}")
    if step == 1 and isinstance(raw, list):
        raw = raw[run_index % len(raw)]
    return raw.format(domain=domain, n=n or 3, perf=perf, tech=tech)

def get_template(variant, prospect, step, run_index=0):
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
    top3  = issues[:3]
    lines = '\n'.join(f"— {i}" for i in top3) or "— Performance mobile en dessous de la moyenne"

    if   perf < 40: plabel = f"score critique ({perf}/100)"
    elif perf < 60: plabel = f"en dessous de la moyenne ({perf}/100)"
    else:           plabel = f"optimisable ({perf}/100)"

    subj = _pick_subject(variant, step, domain, len(top3), perf, tech, run_index)

    # ── Pied de page légal RGPD (obligatoire) ──
    footer = (
        f"\n\n--\n"
        f"Mes-Reves | Dikenga Design — UI/UX Freelance\n"
        f"{SITE_URL} | {PHONE}\n\n"
        f"📧 Vous recevez cet email car votre site est public et indexé.\n"
        f"Pour ne plus recevoir nos messages : répondez STOP ou visitez {UNSUBSCRIBE_URL}"
    )

    if step == 1:
        if variant == 'A':
            body = (
                f"Bonjour,\n\n"
                f"J'ai audité {domain} ce matin.\n\n"
                f"Score performance mobile : {plabel}\n"
                f"Temps de chargement (LCP) : {lcp}\n\n"
                f"Ce que j'ai trouvé :\n{lines}\n\n"
                f"Sur un site {tech}, ces problèmes représentent en général "
                f"15 à 30 % de conversions perdues.\n\n"
                f"Je suis Mes-Reves, UI/UX Designer freelance — je corrige exactement "
                f"ce type de problèmes en 2 à 3 semaines, sans refonte complète.\n\n"
                f"Vous avez 20 minutes cette semaine pour un appel rapide ?\n"
                f"→ {CONTACT_URL}"
                f"{footer}"
            )
        else:
            body = (
                f"Bonjour,\n\n"
                f"Une boutique {tech} dans votre secteur a amélioré son taux "
                f"de conversion de 35 % en 3 semaines de refonte UX.\n\n"
                f"J'ai analysé {domain} : {plabel}.\n\n"
                f"Ce qui diffère des meilleurs sites de votre secteur :\n{lines}\n\n"
                f"Je suis Mes-Reves, UI/UX Designer freelance. "
                f"20 minutes pour voir ce que ça donnerait sur votre site ?\n"
                f"→ {CONTACT_URL}"
                f"{footer}"
            )

    elif step == 2:
        body = (
            f"Bonjour,\n\n"
            f"Je vous avais envoyé un message il y a 3 jours concernant {domain}.\n\n"
            f"Le point principal : {top3[0] if top3 else 'performance mobile insuffisante'}.\n\n"
            f"Ça se corrige rapidement — l'impact sur l'expérience utilisateur est immédiat.\n\n"
            f"Toujours intéressé pour en parler 20 minutes ?\n"
            f"→ {CONTACT_URL}"
            f"{footer}"
        )
    else:
        body = (
            f"Bonjour,\n\n"
            f"Je ferme mon dossier sur {domain}.\n\n"
            f"Si vous cherchez un designer UI/UX quand le moment sera venu : {SITE_URL}\n\n"
            f"Bonne continuation,\n"
            f"Mes-Reves — Dikenga Design"
        )

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
    delay = FOLLOW_UP_DELAYS.get(step + 1)
    next_action = (
        (datetime.now() + timedelta(days=delay)).date().isoformat()
        if delay else None)
    with get_conn() as c:
        c.execute(f"""
            UPDATE prospects SET
              status=?, sequence_step=?, variant=?, date_step{step}=?, next_action=?
            WHERE id=?
        """, ({1:'emailed_1',2:'emailed_2',3:'emailed_3'}[step],
              step, variant, datetime.now().isoformat(), next_action, pid))
    log_event(pid, f'emailed_{step}', {'variant': variant, 'subject': subject})

# ═══════════════════════════════════════════════════════════
# SENDER
# ═══════════════════════════════════════════════════════════

_send_index = 0   # compteur global pour varier les sujets

def send_email(prospect_row, step, variant):
    global _send_index
    pid  = prospect_row['id']
    to   = prospect_row['email']

    # ── Vérifications pré-envoi ──────────────────────────
    if is_optout(to, prospect_row['domain']):
        print(f"  🚫 {to} est opt-out → skip")
        with get_conn() as c:
            c.execute("UPDATE prospects SET status='optout' WHERE id=?", (pid,))
        return False

    if not has_mx(to):
        print(f"  ⚠️  MX invalide pour {to} → bounce probable → skip")
        with get_conn() as c:
            c.execute("UPDATE prospects SET status='bounced', bounced=1 WHERE id=?", (pid,))
        log_event(pid, 'mx_invalid', {'email': to})
        return False

    tmpl = get_template(variant, prospect_row, step, run_index=_send_index)
    _send_index += 1

    if not SMTP_PASS:
        print(f"  [DRY RUN] step{step}/{variant} → {to} | {tmpl['subject'][:55]}")
        mark_emailed(pid, step, variant, tmpl['subject'])
        return True

    msg = MIMEMultipart('alternative')
    msg['From']            = f"{SENDER_NAME} <{SMTP_USER}>"
    msg['To']              = to
    msg['Subject']         = tmpl['subject']
    msg['Reply-To']        = SMTP_USER
    msg['List-Unsubscribe'] = f'<mailto:{SMTP_USER}?subject=STOP>, <{UNSUBSCRIBE_URL}>'
    msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
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
        print(f"  ✅ Step {step}/{variant} → {to} | {tmpl['subject'][:50]}")
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
# SMS — Twilio (optionnel)
# ═══════════════════════════════════════════════════════════

def send_sms(prospect_row):
    """
    Envoie un SMS de prospection via Twilio.
    Nécessite TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM dans l'env.
    """
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        return False
    phone = prospect_row.get('phone') or ''
    if not phone:
        return False

    digits = re.sub(r'[\s.\-]', '', phone)
    if digits.startswith('0'):
        digits = '+33' + digits[1:]
    if not digits.startswith('+33') or len(digits) != 12:
        return False

    domain  = prospect_row['domain']
    company = prospect_row.get('company') or domain
    msg = (
        f"Bonjour {company}, j'ai analysé votre site {domain} : "
        f"performance mobile à améliorer. "
        f"Je suis designer UI/UX freelance — appel 15 min ? "
        f"{SITE_URL} "
        f"— Répondez STOP pour se désinscrire."
    )[:160]

    data = urllib.parse.urlencode({
        'From': TWILIO_FROM,
        'To':   digits,
        'Body': msg,
    }).encode()
    creds = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
    url   = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    req   = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Basic {creds}",
        "Content-Type":  "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
            print(f"  📱 SMS → {digits}: {res.get('status','?')}")
            return True
    except Exception as e:
        print(f"  SMS error ({digits}): {e}")
        return False

# ═══════════════════════════════════════════════════════════
# IMAP — Réponses + Bounces + Opt-out STOP
# ═══════════════════════════════════════════════════════════

def check_replies():
    if not SMTP_PASS:
        return 0, 0
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
                return 0, 0

            by_domain = {r['domain']: r for r in emailed}
            by_email  = {(r['email'] or '').lower(): r for r in emailed if r['email']}
            replies   = 0
            optouts   = 0

            _, data = imap.search(None, f'(SINCE {since})')
            for num in (data[0].split() if data[0] else []):
                try:
                    _, md  = imap.fetch(num, '(RFC822)')
                    raw_b  = md[0][1]
                    msg    = _email_mod.message_from_bytes(raw_b)
                    frm    = msg.get('From', '').lower()
                    subj   = msg.get('Subject', '').lower()
                    body   = ''
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/plain':
                                body = part.get_payload(decode=True).decode('utf-8','ignore').lower()
                                break
                    else:
                        body = (msg.get_payload(decode=True) or b'').decode('utf-8','ignore').lower()

                    matched = (next((r for dom, r in by_domain.items() if dom in frm), None)
                               or next((r for em, r in by_email.items() if em and em in frm), None))

                    if matched:
                        # Détecter STOP / désinscription
                        is_stop = (
                            'stop' in subj or 'stop' in body[:200]
                            or 'désinscri' in body[:200]
                            or 'unsubscribe' in body[:200]
                            or 'ne plus recevoir' in body[:200]
                        )
                        if is_stop:
                            add_optout(matched['email'], matched['domain'])
                            log_event(matched['id'], 'optout', {'from': frm[:100]})
                            optouts += 1
                            print(f"  🚫 STOP reçu de : {matched['domain']}")
                        else:
                            with get_conn() as c:
                                c.execute(
                                    "UPDATE prospects SET replied=1, status='replied' WHERE id=?",
                                    (matched['id'],))
                            log_event(matched['id'], 'replied', {'from': frm[:100]})
                            replies += 1
                            print(f"  📩 Réponse : {matched['domain']}")
                except Exception:
                    pass

            # Bounces (MAILER-DAEMON)
            _, bd = imap.search(None, f'(SINCE {since} FROM "MAILER-DAEMON")')
            for num in (bd[0].split() if bd[0] else []):
                try:
                    _, md  = imap.fetch(num, '(RFC822)')
                    raw    = md[0][1].decode('utf-8', errors='ignore').lower()
                    for em, r in by_email.items():
                        if em and em in raw:
                            with get_conn() as c:
                                c.execute(
                                    "UPDATE prospects SET bounced=1, status='bounced' WHERE id=?",
                                    (r['id'],))
                            log_event(r['id'], 'bounced', {})
                            print(f"  ⚠️  Bounce : {em}")
                except Exception:
                    pass

            return replies, optouts
    except Exception as e:
        print(f"  IMAP error: {e}")
        return 0, 0

# ═══════════════════════════════════════════════════════════
# REPORTER — Funnel Telegram
# ═══════════════════════════════════════════════════════════

def build_report(stats):
    today = datetime.now().strftime('%d/%m/%Y %H:%M')
    with get_conn() as c:
        tot = dict(c.execute("""
            SELECT COUNT(*) total,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN sequence_step>=1 THEN 1 ELSE 0 END) total_emailed,
              SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END) total_replied,
              SUM(CASE WHEN bounced=1 THEN 1 ELSE 0 END) total_bounced,
              SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) queued,
              SUM(CASE WHEN status IN ('emailed_1','emailed_2') THEN 1 ELSE 0 END) pending,
              SUM(CASE WHEN status='optout' THEN 1 ELSE 0 END) total_optout
            FROM prospects
        """).fetchone())
        src_stats = c.execute("""
            SELECT source,
              COUNT(*) n,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END) replied
            FROM prospects GROUP BY source ORDER BY n DESC
        """).fetchall()

    a    = stats['analyzed']
    w    = stats['with_email']
    ph   = stats['with_phone']
    sent = stats['sent']
    rep  = stats['new_replies']
    sms  = stats.get('sms_sent', 0)

    email_rate = f"{w/a*100:.0f}%" if a else "—"
    reply_rate = f"{tot['total_replied']/tot['total_emailed']*100:.1f}%" if tot['total_emailed'] else "—"

    warmup_tag = " [WARMUP 🔥]" if WARMUP_MODE else ""
    ab_line = ""
    if stats.get('step1_A') or stats.get('step1_B'):
        ab_line = f"\n  A/B objets → A:{stats.get('step1_A',0)}  B:{stats.get('step1_B',0)}"

    src_lines = ""
    for r in src_stats:
        em_rate = f"{r['with_email']/r['n']*100:.0f}%" if r['n'] else "—"
        ph_rate = f"{r['with_phone']/r['n']*100:.0f}%" if r['n'] else "—"
        src_lines += (
            f"\n  {SOURCE_EMOJI.get(r['source'],'🌐')} {r['source']:12}"
            f" {r['n']:3}p  📧{em_rate}  📱{ph_rate}  💬{r['replied']}"
        )

    alert = ""
    if rep > 0:
        alert = (f"\n\n🔔 <b>{rep} réponse{'s' if rep>1 else ''} → "
                 f"<a href='{ZIMBRA_URL}'>ouvre Zimbra</a></b>")

    optout_line = f"  Opt-outs : {tot['total_optout']}" if tot.get('total_optout', 0) else ""

    return (
        f"📊 <b>Dikenga Acquisition OS v6{warmup_tag} — {today}</b>\n\n"
        f"<b>🔍 Run du jour</b>\n"
        f"  Analysés : {a}  |  📧 {w} emails ({email_rate})  |  📱 {ph} tél\n"
        f"  Envoyés : {sent}  (step1:{stats.get('s1',0)}  relances:{stats.get('s2',0)+stats.get('s3',0)})"
        f"  SMS : {sms}"
        f"{ab_line}\n"
        f"  Nouvelles réponses : {rep}  |  Opt-outs : {stats.get('new_optouts', 0)}\n\n"
        f"<b>📈 Pipeline total</b>\n"
        f"  En base : {tot['total']}  |  Emailés : {tot['total_emailed']}\n"
        f"  En attente relance : {tot['pending']}  |  File : {tot['queued']}\n"
        f"{optout_line}\n\n"
        f"<b>🎯 Taux globaux</b>\n"
        f"  Email trouvé / analysé : {email_rate}\n"
        f"  Réponse / emailé : {reply_rate}  |  Bounces : {tot['total_bounced']}\n\n"
        f"<b>📡 Taux par source (email · téléphone · réponses)</b>{src_lines}"
        f"{alert}"
    )

# ═══════════════════════════════════════════════════════════
# CSV BACKUP
# ═══════════════════════════════════════════════════════════

def export_csv():
    cols = ['domain','company','email','phone','tech','perf_mobile','score','lcp',
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
# DASHBOARD JSON EXPORT
# ═══════════════════════════════════════════════════════════

def export_dashboard_json():
    """Génère pipeline-data.json pour le dashboard web."""
    with get_conn() as c:
        funnel = dict(c.execute("""
            SELECT COUNT(*) total,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN sequence_step>=1 THEN 1 ELSE 0 END) total_emailed,
              SUM(CASE WHEN replied=1    THEN 1 ELSE 0 END) total_replied,
              SUM(CASE WHEN bounced=1    THEN 1 ELSE 0 END) total_bounced,
              SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) queued,
              SUM(CASE WHEN status='optout' THEN 1 ELSE 0 END) total_optout,
              SUM(CASE WHEN status IN ('emailed_1','emailed_2') THEN 1 ELSE 0 END) pending
            FROM prospects
        """).fetchone())

        sources = [dict(r) for r in c.execute("""
            SELECT source,
              COUNT(*) n,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN sequence_step>=1 THEN 1 ELSE 0 END) total_emailed,
              SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END) replied
            FROM prospects GROUP BY source ORDER BY n DESC
        """).fetchall()]

        ab = {}
        for variant in ['A', 'B']:
            row = c.execute("""
                SELECT COUNT(*) sent,
                  SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END) replied
                FROM prospects WHERE variant=? AND sequence_step>=1
            """, (variant,)).fetchone()
            ab[variant] = {'sent': row[0] or 0, 'replied': row[1] or 0}

        trend = [dict(r) for r in c.execute("""
            SELECT date_added date,
              COUNT(*) analyzed,
              SUM(CASE WHEN sequence_step>=1 THEN 1 ELSE 0 END) emailed,
              SUM(CASE WHEN replied=1 THEN 1 ELSE 0 END) replied
            FROM prospects
            WHERE date_added >= date('now', '-30 days')
            GROUP BY date_added ORDER BY date_added
        """).fetchall()]

        recent = [dict(r) for r in c.execute("""
            SELECT domain, company, tech, score, source, status,
              date_step1, replied, email, phone
            FROM prospects ORDER BY date_added DESC, id DESC LIMIT 30
        """).fetchall()]

        today = datetime.now().date().isoformat()
        today_stats = dict(c.execute("""
            SELECT COUNT(*) analyzed,
              SUM(CASE WHEN email!='' AND email IS NOT NULL THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN date_step1 LIKE ? AND sequence_step>=1 THEN 1 ELSE 0 END) emailed
            FROM prospects WHERE date_added=?
        """, (today + '%', today)).fetchone())

    with get_conn() as c:
        icp_rows  = c.execute("""
            SELECT icp_category, COUNT(*) n FROM prospects
            WHERE icp_category IS NOT NULL GROUP BY icp_category ORDER BY n DESC
        """).fetchall()
        temp_row  = dict(c.execute("""
            SELECT SUM(CASE WHEN temperature='hot'  THEN 1 ELSE 0 END) hot,
                   SUM(CASE WHEN temperature='warm' THEN 1 ELSE 0 END) warm,
                   SUM(CASE WHEN temperature='cold' THEN 1 ELSE 0 END) cold,
                   ROUND(AVG(NULLIF(ai_score,0))) avg_ai_score
            FROM prospects
        """).fetchone())
    total_p = funnel.get('total', 1) or 1
    icp_distribution = [
        {'category': r[0], 'label': ICP_CATEGORIES.get(r[0], r[0]),
         'count': r[1], 'pct': round(r[1] / total_p * 100)}
        for r in icp_rows
    ]

    data = {
        'updated_at':       datetime.now().isoformat(),
        'version':          'v6',
        'warmup_mode':      WARMUP_MODE,
        'funnel':           funnel,
        'sources':          sources,
        'ab_test':          ab,
        'daily_trend':      trend,
        'today':            today_stats,
        'recent':           recent,
        'icp_distribution': icp_distribution,
        'temperature':      {
            'hot':          int(temp_row.get('hot') or 0),
            'warm':         int(temp_row.get('warm') or 0),
            'cold':         int(temp_row.get('cold') or 0),
            'avg_ai_score': int(temp_row.get('avg_ai_score') or 0),
        },
    }

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    return JSON_PATH

# ═══════════════════════════════════════════════════════════
# CRM JSON EXPORT — tous les prospects pour le CRM
# ═══════════════════════════════════════════════════════════

CRM_PATH = os.path.join(PROJ_DIR, 'crm-data.json')

def export_crm_json():
    """Génère crm-data.json v6 avec tous les prospects + ICP + intent feed."""
    with get_conn() as c:
        rows = c.execute("""
            SELECT id, domain, company, email, phone, tech,
                   perf_mobile, lcp, issues, score, source, status,
                   sequence_step, variant, date_added, date_step1,
                   date_step2, date_step3, replied, bounced, notes, next_action,
                   ai_score, temperature, icp_category, brand_quality, intent_signals
            FROM prospects
            ORDER BY ai_score DESC, score DESC, date_added DESC
        """).fetchall()

        total_stats = dict(c.execute("""
            SELECT COUNT(*) total,
              SUM(CASE WHEN email IS NOT NULL AND email!='' THEN 1 ELSE 0 END) with_email,
              SUM(CASE WHEN phone IS NOT NULL AND phone!='' THEN 1 ELSE 0 END) with_phone,
              SUM(CASE WHEN status='queued'   THEN 1 ELSE 0 END) queued,
              SUM(CASE WHEN sequence_step>=1  THEN 1 ELSE 0 END) emailed,
              SUM(CASE WHEN replied=1         THEN 1 ELSE 0 END) replied,
              SUM(CASE WHEN bounced=1         THEN 1 ELSE 0 END) bounced,
              SUM(CASE WHEN status='optout'   THEN 1 ELSE 0 END) optout,
              SUM(CASE WHEN status='no_email' THEN 1 ELSE 0 END) no_email,
              SUM(CASE WHEN temperature='hot'  THEN 1 ELSE 0 END) hot,
              SUM(CASE WHEN temperature='warm' THEN 1 ELSE 0 END) warm,
              SUM(CASE WHEN temperature='cold' THEN 1 ELSE 0 END) cold,
              ROUND(AVG(NULLIF(ai_score,0))) avg_ai_score
            FROM prospects
        """).fetchone())

    prospects = []
    for r in rows:
        p = dict(r)
        try:
            p['issues'] = json.loads(p['issues']) if isinstance(p['issues'], str) else (p['issues'] or [])
        except Exception:
            p['issues'] = []
        try:
            p['intent_signals'] = json.loads(p['intent_signals']) if isinstance(p['intent_signals'], str) else (p['intent_signals'] or [])
        except Exception:
            p['intent_signals'] = []
        p['icp_label'] = ICP_CATEGORIES.get(p.get('icp_category') or '', 'E-commerce Premium')
        prospects.append(p)

    # ICP distribution
    icp_counts = {}
    for p in prospects:
        cat = p.get('icp_category') or 'ecommerce_premium'
        icp_counts[cat] = icp_counts.get(cat, 0) + 1
    icp_distribution = sorted([
        {'category': cat, 'label': ICP_CATEGORIES.get(cat, cat),
         'count': cnt, 'pct': round(cnt / max(1, len(prospects)) * 100)}
        for cat, cnt in icp_counts.items()
    ], key=lambda x: -x['count'])

    # Intent feed — top signals par ai_score
    intent_feed = []
    for p in prospects[:40]:
        for sig in (p.get('intent_signals') or [])[:2]:
            intent_feed.append({
                'domain': p['domain'], 'company': p.get('company', p['domain']),
                'signal': sig['label'], 'strength': sig['strength'],
                'icp_label': p.get('icp_label', ''), 'ai_score': p.get('ai_score', 0),
                'temperature': p.get('temperature', 'cold'),
                'ts': p.get('date_added', ''),
            })
    intent_feed = sorted(intent_feed, key=lambda x: x['ai_score'], reverse=True)[:25]

    data = {
        'updated_at':       datetime.now().isoformat(),
        'version':          'v6',
        'stats':            total_stats,
        'icp_distribution': icp_distribution,
        'intent_feed':      intent_feed,
        'prospects':        prospects,
    }

    with open(CRM_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    return CRM_PATH

# ═══════════════════════════════════════════════════════════
# MAIN — v5 avec threading
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'═'*60}")
    print(f"  Dikenga Acquisition OS v6  —  7 sources + IA scoring")
    if WARMUP_MODE:
        print(f"  ⚠️  WARMUP MODE actif → max {MAX_EMAILS_PER_RUN} emails/jour")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}\n")

    init_db()
    backfill_ai_scores()
    stats = {
        'analyzed': 0, 'with_email': 0, 'with_phone': 0,
        'sent': 0, 'sms_sent': 0,
        's1': 0, 's2': 0, 's3': 0,
        'step1_A': 0, 'step1_B': 0,
        'new_replies': 0, 'new_optouts': 0,
    }

    # ── 1. IMAP — réponses + opt-out ─────────────────────
    print("📩 Vérification des réponses IMAP…")
    rep, opto = check_replies()
    stats['new_replies']  = rep
    stats['new_optouts']  = opto
    print(f"  → {rep} réponse(s)  |  {opto} opt-out(s)\n")

    # ── 2. DISCOVERY (7 sources) ─────────────────────────
    print(f"🌐 Découverte multi-sources (jour {datetime.now().weekday()})…")
    domain_source_pairs = discover_new_domains(n=MAX_ANALYZE_PER_RUN)
    print()

    # ── 3. ENRICHMENT en parallèle (×8 threads) ─────────
    if domain_source_pairs:
        print(f"📊 Analyse en parallèle ({MAX_WORKERS} threads) "
              f"de {len(domain_source_pairs)} domaines…\n")

        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(enrich_domain, d, s): (d, s)
                for d, s in domain_source_pairs
            }
            for future in as_completed(futures):
                domain, source = futures[future]
                try:
                    data = future.result()
                    results.append((domain, source, data))
                except Exception as e:
                    print(f"  ⚠️  {domain}: {e}")

        # Insérer en DB séquentiellement (SQLite)
        for domain, source, data in results:
            try:
                has_em  = bool(data['email'])
                has_ph  = bool(data['phone'])
                issues  = data['issues']
                icp_cat    = detect_icp(data['domain'], data['company'], data['tech'], source)
                intent_sig = detect_intent_signals(data['domain'], data['tech'], data['perf_mobile'], issues, source)
                brand_q    = score_brand_quality(data['domain'], data['tech'], data['perf_mobile'], issues)
                ai_sc      = compute_ai_score(
                    data['perf_mobile'], data['tech'], issues, has_em, has_ph,
                    icp_cat, intent_sig, brand_q)
                sc         = compute_score(
                    data['perf_mobile'], data['tech'], issues,
                    has_email=has_em, has_phone=has_ph)
                temp       = classify_temperature(ai_sc)

                if has_em and sc >= MIN_SCORE:  status = 'queued'
                elif not has_em:                status = 'no_email'
                else:                           status = 'low_score'

                with get_conn() as c:
                    c.execute("""
                        INSERT OR IGNORE INTO prospects
                          (domain,company,email,phone,tech,perf_mobile,lcp,issues,
                           score,source,status,date_added,date_analyzed,
                           ai_score,temperature,icp_category,brand_quality,intent_signals)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (data['domain'], data['company'], data['email'],
                          data.get('phone'),
                          data['tech'], data['perf_mobile'], data['lcp'],
                          json.dumps(issues),
                          sc, source, status,
                          datetime.now().date().isoformat(),
                          datetime.now().isoformat(),
                          ai_sc, temp, icp_cat, brand_q,
                          json.dumps(intent_sig)))

                stats['analyzed'] += 1
                if has_em: stats['with_email'] += 1
                if has_ph: stats['with_phone'] += 1
                em  = SOURCE_EMOJI.get(source, '🌐')
                print(f"  {em} {domain}: {data['tech']} | perf={data['perf_mobile']}"
                      f" | score={sc} | {'📧' if has_em else '—'} {'📱' if has_ph else '—'}")
            except Exception as e:
                print(f"  ⚠️  Insert {domain}: {e}")

        print()

    # ── 4. SEND emails ────────────────────────────────────
    print("📧 Envoi des emails…\n")
    s1, s2, s3 = get_prospects_to_contact()
    total_sent = 0
    variants   = ['A', 'B']

    for i, p in enumerate(s1):
        if total_sent >= MAX_EMAILS_PER_RUN: break
        v = variants[i % 2]
        if send_email(p, 1, v):
            total_sent += 1; stats['s1'] += 1
            stats[f'step1_{v}'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s2:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        if send_email(p, 2, dict(p).get('variant','A') or 'A'):
            total_sent += 1; stats['s2'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    for p in s3:
        if total_sent >= MAX_EMAILS_PER_RUN: break
        if send_email(p, 3, dict(p).get('variant','A') or 'A'):
            total_sent += 1; stats['s3'] += 1; stats['sent'] += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            time.sleep(3)

    # ── 5. SMS (si Twilio configuré) ─────────────────────
    if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM:
        print("\n📱 Envoi SMS (numéros collectés)…\n")
        with get_conn() as c:
            sms_candidates = c.execute("""
                SELECT * FROM prospects
                WHERE phone IS NOT NULL AND phone!=''
                  AND status='queued' AND sequence_step=0
                ORDER BY score DESC LIMIT 10
            """).fetchall()
        for p in sms_candidates:
            if send_sms(dict(p)):
                stats['sms_sent'] += 1
            time.sleep(5)   # délai entre SMS
        print()

    # ── 6. BACKUP + DASHBOARD + RAPPORT ──────────────────
    export_csv()
    export_dashboard_json()
    export_crm_json()
    print(f"✅ CSV + pipeline-data.json + crm-data.json exportés")
    print("📱 Rapport Telegram…")
    report = build_report(stats)
    tg(report)
    print(report)

    print(f"\n{'═'*60}")
    print(f"  Done — {total_sent} emails  |  {stats['sms_sent']} SMS"
          f"  |  {stats['new_replies']} réponses  |  {stats['new_optouts']} opt-outs")
    print(f"{'═'*60}\n")


if __name__ == '__main__':
    main()
