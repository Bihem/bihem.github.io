"""
Dikenga Design — Audit automatique de prospects
Tourne chaque matin via GitHub Actions.
Lit prospects.csv, analyse chaque site, envoie les meilleurs sur Telegram.
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import csv
import os
import time
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGESPEED_API_KEY = os.environ.get('PAGESPEED_API_KEY', '')  # optionnel


# ─── TELEGRAM ────────────────────────────────────────────────────────────────

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("=== TELEGRAM (non configuré) ===")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4096],
        "parse_mode": "HTML"
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Telegram error: {e}")


# ─── PAGESPEED ────────────────────────────────────────────────────────────────

def get_pagespeed(url):
    """Retourne (perf_score, lcp, issues) ou None si erreur."""
    try:
        api_url = (
            f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={urllib.parse.quote(url, safe='')}&strategy=mobile"
        )
        if PAGESPEED_API_KEY:
            api_url += f"&key={PAGESPEED_API_KEY}"

        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read())

        lr = data.get('lighthouseResult', {})
        categories = lr.get('categories', {})
        audits = lr.get('audits', {})

        perf_score = int(categories.get('performance', {}).get('score', 0) * 100)
        lcp = audits.get('largest-contentful-paint', {}).get('displayValue', 'N/A')

        # Problèmes réels (score < 0.5 = raté)
        audit_labels = {
            'uses-optimized-images': 'Images non optimisées',
            'render-blocking-resources': 'Ressources bloquantes au chargement',
            'unused-css-rules': 'CSS inutilisé chargé',
            'uses-responsive-images': 'Images non adaptées au mobile',
            'uses-text-compression': 'Pas de compression texte (Gzip)',
            'offscreen-images': 'Images hors-écran chargées inutilement',
        }
        issues = []
        for key, label in audit_labels.items():
            audit = audits.get(key, {})
            if isinstance(audit.get('score'), (int, float)) and audit['score'] < 0.5:
                issues.append(label)

        return perf_score, lcp, issues[:3]

    except Exception as e:
        print(f"PageSpeed error ({url}): {e}")
        return None


# ─── TECH STACK ───────────────────────────────────────────────────────────────

def detect_tech(url):
    """Détection simple de la plateforme via le HTML source."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(60000).decode('utf-8', errors='ignore').lower()

        if 'cdn.shopify.com' in html or 'shopify' in html:
            return 'Shopify'
        if 'wixstatic.com' in html or 'wix.com' in html:
            return 'Wix'
        if 'squarespace' in html:
            return 'Squarespace'
        if 'webflow.io' in html or 'webflow' in html:
            return 'Webflow'
        if 'wp-content' in html or 'wordpress' in html:
            return 'WordPress'
        if 'prestashop' in html:
            return 'PrestaShop'
        return 'Custom'

    except Exception as e:
        print(f"Tech detect error ({url}): {e}")
        return 'Inconnu'


# ─── SCORING ──────────────────────────────────────────────────────────────────

def score_prospect(perf_score, tech, issues_count):
    """Score d'opportunité 0-100 (plus haut = meilleure opportunité)."""
    score = 0

    # Performance mobile (inversée)
    if perf_score < 40:
        score += 35
    elif perf_score < 60:
        score += 25
    elif perf_score < 75:
        score += 15
    else:
        score += 5

    # Stack = niveau d'opportunité
    tech_scores = {
        'Shopify': 30,      # argument coût Système Dikenga
        'Wix': 28,          # plateforme dépassée
        'Squarespace': 25,  # design limité
        'WordPress': 20,    # lourd, souvent mal maintenu
        'PrestaShop': 22,
        'Webflow': 10,      # déjà bien
        'Custom': 8,
        'Inconnu': 5,
    }
    score += tech_scores.get(tech, 5)

    # Problèmes détectés
    score += issues_count * 5

    return min(score, 100)


# ─── GÉNÉRATION EMAIL ─────────────────────────────────────────────────────────

def build_email_draft(domain, company, perf_score, lcp, tech, issues):
    issues_lines = '\n'.join(f"- {i}" for i in issues) if issues else '- Analyser visuellement le site'

    shopify_note = ""
    if tech == 'Shopify':
        shopify_note = (
            "\n\n💡 <b>Angle Shopify :</b> Mentionner que leur stack coûte "
            "80-180€/mois et qu'on peut descendre à ~10€/mois avec mêmes features."
        )

    email = (
        f"Objet : Audit {domain} — 3 points à corriger\n\n"
        f"Bonjour,\n\n"
        f"En visitant {domain} ce matin, j'ai repéré 3 choses qui freinent probablement vos conversions :\n\n"
        f"{issues_lines}\n\n"
        f"Je vous les ai documentées gratuitement, sans engagement.\n\n"
        f"Si vous voulez qu'on en parle 20 minutes :\n"
        f"cal.com/dikenga\n\n"
        f"Mes-Reves — Dikenga Design\n"
        f"dikengadesign.fr"
    )

    return email, shopify_note


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime('%d/%m/%Y')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(os.path.dirname(script_dir), 'prospects.csv')

    if not os.path.exists(csv_path):
        send_telegram(
            "⚠️ <b>Dikenga Audit</b>\n\n"
            "prospects.csv introuvable dans le repo.\n"
            "Ajoute des prospects (status=new) pour lancer l'analyse."
        )
        return

    # Lire les prospects "new"
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    new_prospects = [r for r in rows if r.get('status', '').strip().lower() == 'new']

    if not new_prospects:
        send_telegram(
            f"📭 <b>Dikenga Audit — {today}</b>\n\n"
            "Aucun nouveau prospect à analyser.\n"
            "Ajoute des lignes avec <code>status=new</code> dans prospects.csv"
        )
        return

    send_telegram(
        f"🔍 <b>Dikenga Audit — {today}</b>\n\n"
        f"Analyse de {len(new_prospects[:10])} prospect(s)..."
    )

    results = []

    for prospect in new_prospects[:10]:  # max 10/jour pour rester dans les limites API
        domain = prospect.get('domain', '').strip().rstrip('/')
        company = prospect.get('company', domain).strip()
        segment = prospect.get('segment', 'général').strip()

        if not domain:
            continue

        url = domain if domain.startswith('http') else f"https://{domain}"
        print(f"→ Analyse {domain}...")

        ps = get_pagespeed(url)
        if ps is None:
            print(f"  Skipped (PageSpeed failed)")
            continue

        perf_score, lcp, issues = ps
        tech = detect_tech(url)
        opportunity = score_prospect(perf_score, tech, len(issues))

        results.append({
            'domain': domain,
            'company': company,
            'segment': segment,
            'perf_score': perf_score,
            'lcp': lcp,
            'tech': tech,
            'issues': issues,
            'score': opportunity,
        })

        # Mettre à jour le statut dans le CSV
        for row in rows:
            if row.get('domain', '').strip() == domain:
                row['status'] = 'analyzed'
                row['score'] = str(opportunity)
                row['perf_score'] = str(perf_score)
                row['tech'] = tech
                row['last_analyzed'] = datetime.now().strftime('%Y-%m-%d')
                break

        time.sleep(2)

    # Réécrire le CSV avec les scores mis à jour
    if rows:
        fieldnames = rows[0].keys()
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    if not results:
        send_telegram("😶 Aucun prospect analysé avec succès. Vérifie les domaines dans prospects.csv")
        return

    # Trier par score décroissant
    results.sort(key=lambda x: x['score'], reverse=True)

    # Envoyer les top 5
    for r in results[:5]:
        email_draft, shopify_note = build_email_draft(
            r['domain'], r['company'], r['perf_score'],
            r['lcp'], r['tech'], r['issues']
        )

        issues_text = '\n'.join(f"  • {i}" for i in r['issues']) or '  • Vérifier visuellement'

        msg = (
            f"📊 <b>{r['company']}</b> — Opportunité : <b>{r['score']}/100</b>\n"
            f"🌐 {r['domain']}\n"
            f"⚙️ Stack : {r['tech']} | 📱 Perf mobile : {r['perf_score']}/100 | LCP : {r['lcp']}\n"
            f"🎯 Segment : {r['segment']}\n"
            f"{shopify_note}\n\n"
            f"⚠️ <b>Problèmes détectés :</b>\n{issues_text}\n\n"
            f"✉️ <b>Email prêt à envoyer :</b>\n"
            f"<pre>{email_draft}</pre>"
        )
        send_telegram(msg)
        time.sleep(1)

    best = results[0]
    send_telegram(
        f"✅ <b>Récap du jour</b>\n\n"
        f"{len(results)} prospect(s) analysé(s)\n"
        f"🏆 Meilleure opportunité : <b>{best['company']}</b> ({best['score']}/100)\n\n"
        f"→ Personnalise et envoie les emails ci-dessus dès aujourd'hui."
    )


if __name__ == '__main__':
    main()
