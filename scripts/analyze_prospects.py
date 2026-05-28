#!/usr/bin/env python3
"""
Dikenga Design — Pipeline d'acquisition automatique
Chaque matin (lun-ven) :
  1. Cherche de nouveaux prospects via DuckDuckGo
  2. Analyse leur site (PageSpeed, tech stack)
  3. Trouve leur email de contact
  4. Envoie un email d'audit personnalisé
  5. Rapport complet sur Telegram

Tu n'as qu'à regarder les réponses.
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import csv
import os
import re
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN  = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID= os.environ.get('TELEGRAM_CHAT_ID', '')
SMTP_HOST       = os.environ.get('SMTP_HOST', 'zimbra1.mail.ovh.net')
SMTP_PORT       = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER       = os.environ.get('SMTP_USER', 'contact@dikengadesign.fr')
SMTP_PASS       = os.environ.get('SMTP_PASS', '')
SENDER_NAME     = "Mes-Reves — Dikenga Design"
MAX_EMAILS_PER_RUN = 15   # limite quotidienne de sécurité
EMAIL_DELAY_SEC    = 40   # secondes entre chaque envoi (évite le spam filter)
MIN_SCORE_TO_EMAIL = 55   # score minimum pour envoyer un email

# Requêtes DuckDuckGo — rotation par jour de la semaine
SEARCH_QUERIES = {
    0: ["boutique shopify streetwear france", "shop mode shopify paris site:.fr"],           # Lundi
    1: ["boutique wix vetements paris", "ecommerce wix mode france"],                         # Mardi
    2: ["startup saas paris ux interface", "saas b2b france product design"],                 # Mercredi
    3: ["boutique ligne mode paris refonte", "ecommerce france site wordpress mode"],         # Jeudi
    4: ["agence digitale paris freelance design", "boutique shopify beaute paris"],          # Vendredi
}

# Domaines à ne JAMAIS contacter
BLACKLIST_DOMAINS = {
    'dikengadesign.fr','talseume.com','talseume.fr','studiobooking.fr',
    'google.com','google.fr','facebook.com','instagram.com','linkedin.com',
    'youtube.com','twitter.com','tiktok.com','amazon.fr','fnac.com',
    'cdiscount.com','leboncoin.fr','laposte.fr','free.fr','orange.fr',
    'shopify.com','wordpress.com','wix.com','squarespace.com','webflow.io',
}


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def tg(text):
    if not TELEGRAM_TOKEN:
        print(text); return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096], "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10): pass
    except Exception as e:
        print(f"Telegram: {e}")


# ─── HTTP HELPERS ─────────────────────────────────────────────────────────────

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch(url, timeout=15, max_bytes=80000):
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(max_bytes).decode('utf-8', errors='ignore')
    except Exception:
        return None

def extract_domain(url):
    try:
        h = urllib.parse.urlparse(url).netloc or url
        return re.sub(r'^www\.', '', h.lower().split('/')[0].split('?')[0].strip())
    except Exception:
        return None


# ─── PROSPECTING — DuckDuckGo ─────────────────────────────────────────────────

def ddg_search(query, max_results=10):
    """Recherche DuckDuckGo → liste de domaines uniques."""
    domains = []
    html = fetch(
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
        timeout=25
    )
    if not html:
        return domains

    # Extraire les URLs réelles depuis les redirects DDG (uddg=URL_encodée)
    for encoded in re.findall(r'uddg=([^&">\s]+)', html):
        try:
            real_url = urllib.parse.unquote(encoded)
            d = extract_domain(real_url)
            if d and '.' in d and d not in domains:
                domains.append(d)
        except Exception:
            pass

    # Fallback: hrefs directs
    for href in re.findall(r'href="(https?://[^"]{8,})"', html):
        d = extract_domain(href)
        if d and '.' in d and 'duckduckgo' not in d and d not in domains:
            domains.append(d)

    return domains[:max_results]


def get_new_prospects(existing_domains, max_per_day=25):
    """Retourne de nouveaux domaines à analyser aujourd'hui."""
    day = datetime.now().weekday() % len(SEARCH_QUERIES)
    queries = SEARCH_QUERIES[day]
    found = []

    for query in queries:
        print(f"  🔍 {query}")
        results = ddg_search(query, max_results=12)
        for d in results:
            d_clean = d.replace('www.', '')
            skip = (
                d_clean in existing_domains or
                d_clean in BLACKLIST_DOMAINS or
                any(b in d_clean for b in BLACKLIST_DOMAINS) or
                d_clean in [x.replace('www.', '') for x in found] or
                len(d_clean) > 60 or
                d_clean.count('.') > 3
            )
            if not skip:
                found.append(d_clean)
        time.sleep(3)

    return list(dict.fromkeys(found))[:max_per_day]


# ─── EMAIL FINDER ─────────────────────────────────────────────────────────────

EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9._%+\-]{2,}[@＠][a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}',
    re.IGNORECASE
)
SKIP_EMAIL_PREFIXES = ('noreply','no-reply','donotreply','example','test@','demo@',
                       'admin@','webmaster@','abuse@','security@','support@noreply')

def find_email(domain):
    """Cherche l'email de contact sur le site."""
    for path in ['', '/contact', '/contact-us', '/nous-contacter', '/about']:
        html = fetch(f"https://{domain}{path}", timeout=12)
        if not html:
            continue

        # Normaliser les obfuscations courantes : [at], (at), [dot]
        normalized = (html
            .replace('[at]', '@').replace('(at)', '@').replace(' at ', '@')
            .replace('[dot]', '.').replace('(dot)', '.'))

        emails = EMAIL_REGEX.findall(normalized)
        cleaned = []
        for e in emails:
            e = e.lower().strip().rstrip('.')
            if not any(s in e for s in SKIP_EMAIL_PREFIXES):
                if re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,6}$', e):
                    cleaned.append(e)

        if cleaned:
            # Priorité : contact@ hello@ info@ bonjour@
            for prefix in ('contact@','hello@','info@','bonjour@','pro@','studio@','agency@'):
                for e in cleaned:
                    if e.startswith(prefix):
                        return e
            return cleaned[0]

        time.sleep(1)

    return None


# ─── TECH STACK ───────────────────────────────────────────────────────────────

def detect_tech(domain):
    html = fetch(f"https://{domain}", timeout=15) or ''
    h = html.lower()
    if 'cdn.shopify.com' in h or 'shopify.com/s/' in h:   return 'Shopify'
    if 'wixstatic.com' in h or 'wix.com/_api' in h:        return 'Wix'
    if 'squarespace' in h:                                   return 'Squarespace'
    if 'webflow.io' in h or 'assets.website-files.com' in h:return 'Webflow'
    if 'wp-content' in h or 'wp-includes' in h:             return 'WordPress'
    if 'prestashop' in h:                                    return 'PrestaShop'
    return 'Custom'


# ─── PAGESPEED ────────────────────────────────────────────────────────────────

def pagespeed(domain):
    """Retourne (score, lcp, [issues]) ou None."""
    try:
        key = os.environ.get('PAGESPEED_API_KEY', '')
        api = (f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
               f"?url={urllib.parse.quote('https://'+domain, safe='')}&strategy=mobile"
               + (f"&key={key}" if key else ''))
        req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())

        lr     = d.get('lighthouseResult', {})
        score  = int(lr.get('categories',{}).get('performance',{}).get('score',0) * 100)
        lcp    = lr.get('audits',{}).get('largest-contentful-paint',{}).get('displayValue','N/A')
        issues = []
        checks = {
            'uses-optimized-images'   : 'Images non optimisées',
            'render-blocking-resources': 'Ressources bloquantes au chargement',
            'unused-css-rules'         : 'CSS inutilisé chargé',
            'uses-text-compression'    : 'Compression texte absente (Gzip)',
        }
        for k, label in checks.items():
            a = lr.get('audits',{}).get(k,{})
            if isinstance(a.get('score'), (int,float)) and a['score'] < 0.5:
                issues.append(label)
        return score, lcp, issues[:3]
    except Exception as e:
        print(f"  PageSpeed error: {e}")
        return None


# ─── SCORING ──────────────────────────────────────────────────────────────────

TECH_SCORES = {'Shopify':30,'Wix':28,'Squarespace':25,'PrestaShop':22,
               'WordPress':20,'Webflow':10,'Custom':8,'Inconnu':5}

def score(perf, tech, issues_n):
    s  = 35 if perf < 40 else (25 if perf < 60 else (15 if perf < 75 else 5))
    s += TECH_SCORES.get(tech, 5)
    s += issues_n * 5
    return min(s, 100)


# ─── EMAIL BUILDER ────────────────────────────────────────────────────────────

def build_email(domain, perf, lcp, tech, issues):
    problems = list(issues)
    if perf < 55 and not any('chargement' in i.lower() for i in problems):
        problems.insert(0, f"Vitesse mobile insuffisante ({perf}/100 sur Google PageSpeed)")
    if tech == 'Shopify' and len(problems) < 3:
        problems.append("Frais Shopify élevés — solutions alternatives à ~10€/mois existent")

    lines = '\n'.join(f"— {p}" for p in problems[:3])
    subject = f"Audit {domain} — 3 points à corriger"
    body = (
        f"Bonjour,\n\n"
        f"En visitant {domain} ce matin, j'ai repéré 3 choses "
        f"qui freinent probablement vos conversions :\n\n"
        f"{lines}\n\n"
        f"Je vous les ai documentées gratuitement, sans engagement.\n\n"
        f"Si vous voulez qu'on en parle 20 minutes :\n"
        f"dikengadesign.fr/audit-ux-gratuit.html\n\n"
        f"Bien cordialement,\n"
        f"Mes-Reves — Dikenga Design\n"
        f"dikengadesign.fr | +33 7 67 53 70 59\n\n"
        f"--\nPour ne plus recevoir ces emails, répondez « STOP ».\n"
    )
    return subject, body


# ─── EMAIL SENDER ─────────────────────────────────────────────────────────────

def send_email(to, subject, body):
    if not SMTP_PASS:
        print(f"  [DRY RUN — SMTP_PASS non configuré] → {to}")
        return True  # mode test

    try:
        msg = MIMEMultipart('alternative')
        msg['From']     = f"{SENDER_NAME} <{SMTP_USER}>"
        msg['To']       = to
        msg['Subject']  = subject
        msg['Reply-To'] = SMTP_USER
        msg.add_header('List-Unsubscribe', f'<mailto:{SMTP_USER}?subject=STOP>')
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, to, msg.as_string())
        return True
    except Exception as e:
        print(f"  SMTP error ({to}): {e}")
        return False


# ─── CSV HELPERS ──────────────────────────────────────────────────────────────

FIELDNAMES = ['domain','company','email','tech','perf_score','score',
              'lcp','issues','status','date_added','last_analyzed','notes']

def load_prospects(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save_prospects(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    today    = datetime.now().strftime('%d/%m/%Y')
    today_iso= datetime.now().strftime('%Y-%m-%d')
    cutoff   = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'prospects.csv')

    existing = load_prospects(csv_path)

    # Domains + emails already contacted in last 90 days
    known_domains  = set()
    known_emails   = set()
    for r in existing:
        d = r.get('domain','').replace('www.','').strip()
        e = r.get('email','').lower().strip()
        la= r.get('last_analyzed', r.get('date_added',''))
        if la >= cutoff and r.get('status','') not in ('new',''):
            if d: known_domains.add(d)
            if e: known_emails.add(e)

    tg(f"🚀 <b>Dikenga Acquisition — {today}</b>\n\nRecherche de prospects...")

    # ── 1. SOURCING ──────────────────────────────────────────────────────────
    print("\n=== SOURCING ===")
    new_domains = get_new_prospects(known_domains, max_per_day=25)
    print(f"→ {len(new_domains)} nouveaux domaines\n")

    if not new_domains:
        tg("📭 Aucun nouveau prospect trouvé aujourd'hui.\nLe pipeline reprend demain.")
        return

    # ── 2-3. ANALYSE + EMAIL FINDING ─────────────────────────────────────────
    print("=== ANALYSE ===")
    candidates = []

    for domain in new_domains[:20]:
        print(f"→ {domain}")
        tech    = detect_tech(domain)
        ps      = pagespeed(domain)
        if ps is None:
            print("  skip (PageSpeed failed)")
            continue

        perf, lcp, issues = ps
        opp = score(perf, tech, len(issues))
        print(f"  Score {opp}/100 | {tech} | perf {perf} | LCP {lcp}")

        if opp < MIN_SCORE_TO_EMAIL:
            print("  skip (score trop bas)")
            continue

        email = find_email(domain)
        print(f"  Email: {email or '—'}")

        candidates.append({
            'domain'  : domain,
            'company' : domain.split('.')[0].capitalize(),
            'email'   : email,
            'tech'    : tech,
            'perf'    : perf,
            'lcp'     : lcp,
            'issues'  : issues,
            'opp'     : opp,
        })
        time.sleep(2)

    candidates.sort(key=lambda x: x['opp'], reverse=True)

    # ── 4. SEND EMAILS ────────────────────────────────────────────────────────
    print("\n=== ENVOI ===")
    sent_ok  = []
    no_email = []
    errors   = []
    sent_count = 0

    for c in candidates:
        if sent_count >= MAX_EMAILS_PER_RUN:
            break

        if not c['email'] or c['email'].lower() in known_emails:
            no_email.append(c)
            continue

        subject, body = build_email(c['domain'], c['perf'], c['lcp'], c['tech'], c['issues'])
        print(f"📧 {c['domain']} → {c['email']}")
        ok = send_email(c['email'], subject, body)

        if ok:
            sent_ok.append(c)
            known_emails.add(c['email'].lower())
            sent_count += 1
            time.sleep(EMAIL_DELAY_SEC)
        else:
            errors.append(c)

    # ── 5. LOG CSV ────────────────────────────────────────────────────────────
    new_rows = []
    for c in candidates:
        if c in sent_ok:     status = 'emailed'
        elif c in no_email:  status = 'no_email'
        elif c in errors:    status = 'error'
        else:                status = 'analyzed'

        new_rows.append({
            'domain'       : c['domain'],
            'company'      : c['company'],
            'email'        : c.get('email') or '',
            'tech'         : c['tech'],
            'perf_score'   : c['perf'],
            'score'        : c['opp'],
            'lcp'          : c['lcp'],
            'issues'       : ' | '.join(c.get('issues',[])),
            'status'       : status,
            'date_added'   : today_iso,
            'last_analyzed': today_iso,
            'notes'        : '',
        })

    save_prospects(csv_path, existing + new_rows)

    # ── 6. TELEGRAM REPORT ───────────────────────────────────────────────────
    sent_lines = '\n'.join(
        f"  ✅ {c['company']} ({c['domain']})\n"
        f"      → <code>{c['email']}</code> | Score {c['opp']}/100 | {c['tech']}"
        for c in sent_ok
    ) or '  (aucun — GMAIL_PASS non configuré)'

    no_email_lines = '\n'.join(
        f"  📭 {c['domain']} [{c['opp']}/100 — {c['tech']}]"
        for c in no_email[:5]
    )

    tg(
        f"📊 <b>Rapport Acquisition — {today}</b>\n\n"
        f"🔎 Prospects analysés : <b>{len(candidates)}</b>\n"
        f"📧 Emails envoyés : <b>{sent_count}</b>\n"
        f"📭 Sans email trouvé : <b>{len(no_email)}</b>\n\n"
        f"<b>Emails envoyés :</b>\n{sent_lines}\n\n"
        + (f"<b>Sans email :</b>\n{no_email_lines}\n\n" if no_email_lines else '') +
        f"💬 Surveille <code>contact@dikengadesign.fr</code> pour les réponses."
    )


if __name__ == '__main__':
    main()
