#!/usr/bin/env python3
"""
monitor_ticketplace.py
Surveillance ULTRA-RAPIDE des événements Ticketplace.
Mode sniper : vérifie toutes les 3 secondes, alerte instantanée.
Compatible Termux (Android) et Linux.
"""

import smtplib
import os
import json
import time
import requests as std_requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "email_from": "fandresenarakotomandimby@gmail.com",
    "email_password": "bmfs umdl nxbz kjwj",
    "email_to": "fandresenarakotomandimby@gmail.com",
    "seen_events_file": os.path.join(SCRIPT_DIR, "seen_events.json"),
    "notified_important_file": os.path.join(SCRIPT_DIR, "notified_important.json"),

    # ⚡ INTERVALLES : mode normal vs mode alerte active
    "interval_seconds": 5,          # vérification normale toutes les 5s
    "interval_alert_seconds": 2,    # vérification accélérée à 2s si événement détecté récemment
    "alert_boost_duration": 60,     # boost pendant 60s après une détection
    "retry_on_error_seconds": 5,

    "important_keywords": [
        "cgm", "examen", "concours", "inscription",
        "formation", "goethe", "delf", "dalf", "tef",
        "ouverture", "disponible", "places", "limitées",
        "billet", "ticket"
    ]
}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "fr-FR,fr;q=0.9",
    "origin": "https://www.ticketplace.io",
    "referer": "https://www.ticketplace.io/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

API_URLS = [
    ("https://web-api.ticketplace.io/api/events/upcoming-events?search=undefined", "upcoming"),
    ("https://web-api.ticketplace.io/api/events/passed-events", "passed"),
]

# -------------------------
# SESSION — priorité curl_cffi > cloudscraper > requests
# -------------------------
USE_CURL = False

try:
    from curl_cffi import requests as cf_requests
    session = cf_requests.Session(impersonate="chrome124")
    USE_CURL = True
    print("✅ curl_cffi chargé (bypass Cloudflare TLS)")
except ImportError:
    try:
        import cloudscraper
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        print("⚠️  curl_cffi absent — fallback cloudscraper")
    except ImportError:
        session = std_requests.Session()
        session.headers.update(HEADERS)
        print("⚠️  cloudscraper absent — fallback requests basique")


# -------------------------
# PERSISTENCE
# -------------------------
def load_json_set(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return set(json.load(f))
    return set()


def save_json_set(filepath, data):
    with open(filepath, "w") as f:
        json.dump(list(data), f)


# -------------------------
# KEYWORD CHECK
# -------------------------
def is_important(text):
    return any(k in text.lower() for k in CONFIG["important_keywords"])


# -------------------------
# FETCH AVEC RETRY
# -------------------------
def fetch_events():
    events = {}
    for url, label in API_URLS:
        retries = 3
        for attempt in range(retries):
            try:
                r = session.get(url, headers=HEADERS, timeout=10)

                if r.status_code == 403:
                    print(f"   [{label}] ❌ 403 Cloudflare — installez curl_cffi")
                    break

                if r.status_code not in (200, 304):
                    print(f"   [{label}] ⚠️ Ignoré (status {r.status_code})")
                    break

                items = r.json().get("data", [])

                for item in items:
                    eid   = str(item["id"])
                    title = item.get("title", "").strip()
                    if not title:
                        continue
                    events[eid] = {
                        "id":        eid,
                        "text":      title,
                        "url":       f"https://www.ticketplace.io/event/{item.get('eventHashCode', eid)}",
                        "startDate": item.get("startDate", ""),
                        "endDate":   item.get("endDate", ""),
                        "location":  item.get("location", ""),
                        "category":  item.get("category", ""),
                        "type":      label,
                        "important": is_important(title),
                        "found_at":  datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    }
                break  # succès

            except Exception as e:
                err_type = type(e).__name__
                if "ConnectionError" in err_type or "ConnectError" in err_type:
                    print(f"   [{label}] ❌ Pas de connexion (tentative {attempt+1}/{retries})")
                else:
                    print(f"   [{label}] ❌ Erreur: {e}")
                if attempt < retries - 1:
                    time.sleep(CONFIG["retry_on_error_seconds"])
                else:
                    break

    return events


# -------------------------
# EMAIL
# -------------------------
def send_email(new_events, important_events):
    subject = f"🚨 ALERTE PLACES DISPO — {len(new_events)} nouveaux | {len(important_events)} importants — Ticketplace"
    html = "<h2>🎫 Surveillance Ticketplace — ALERTE IMMÉDIATE</h2>"
    html += f"<p style='color:gray'>Détecté le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}</p>"

    if important_events:
        html += "<h3 style='color:red;'>🔥 RÉSERVEZ MAINTENANT — ÉVÉNEMENTS IMPORTANTS</h3>"
        for e in important_events:
            html += f"""
            <div style='border-left:4px solid red;padding:8px 12px;margin:8px 0;background:#fff5f5;'>
                🚨 <b><a href='{e["url"]}' style='color:red;font-size:16px;'>{e["text"]}</a></b><br>
                📍 {e["location"]}<br>
                🗓️ {e["startDate"]} → {e["endDate"]}<br>
                🏷️ {e["category"]}<br>
                🔗 <a href='{e["url"]}'>{e["url"]}</a>
            </div>"""

    if new_events:
        html += "<h3>🆕 Nouveaux événements</h3>"
        for e in new_events:
            icon = "📅" if e["type"] == "upcoming" else "✅"
            flag = " 🔥" if e["important"] else ""
            html += f"""
            <div style='border-left:4px solid #0066cc;padding:8px 12px;margin:8px 0;'>
                {icon}{flag} <a href='{e["url"]}'>{e["text"]}</a><br>
                📍 {e["location"]} — 🗓️ {e["startDate"]}
            </div>"""

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = CONFIG["email_from"]
    msg["To"]      = CONFIG["email_to"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(CONFIG["email_from"], CONFIG["email_password"])
            server.sendmail(CONFIG["email_from"], CONFIG["email_to"], msg.as_string())
        print("   📧 Email envoyé !")
    except Exception as e:
        print(f"   ❌ Erreur email: {e}")


# -------------------------
# NOTIFICATION ANDROID (Termux) — ALERTE MAX
# -------------------------
def termux_notify(title, message, urgent=False):
    if urgent:
        # Vibre 3 fois + son fort pour les événements importants
        for _ in range(3):
            os.system(
                f'termux-notification '
                f'--title "{title}" '
                f'--content "{message}" '
                f'--sound --vibrate 2000 --priority max --ongoing'
            )
            time.sleep(0.5)
    else:
        os.system(
            f'termux-notification '
            f'--title "{title}" '
            f'--content "{message}" '
            f'--sound --vibrate 1000 --priority high'
        )


def termux_toast(message):
    """Affiche un message toast rapide sur l'écran Android."""
    os.system(f'termux-toast -s "{message}"')


# -------------------------
# MAIN
# -------------------------
def main():
    print("=" * 55)
    print("🚀 Monitor Ticketplace — MODE SNIPER")
    print(f"⚡  Intervalle normal  : {CONFIG['interval_seconds']}s")
    print(f"🔥  Intervalle boost   : {CONFIG['interval_alert_seconds']}s (après détection)")
    print(f"🔧  Backend: {'curl_cffi' if USE_CURL else 'cloudscraper/requests'}")
    print("🛑  Ctrl+C pour arrêter")
    print("=" * 55)

    seen               = load_json_set(CONFIG["seen_events_file"])
    notified_important = load_json_set(CONFIG["notified_important_file"])
    cycle = 0
    last_detection_time = 0  # timestamp de la dernière détection

    while True:
        cycle += 1
        now = datetime.now().strftime("%d/%m %H:%M:%S")

        # Calcul de l'intervalle dynamique
        time_since_last = time.time() - last_detection_time
        in_boost_mode = time_since_last < CONFIG["alert_boost_duration"]
        current_interval = CONFIG["interval_alert_seconds"] if in_boost_mode else CONFIG["interval_seconds"]
        boost_label = " ⚡BOOST" if in_boost_mode else ""

        print(f"\n[{now}] 🔄 Cycle #{cycle}{boost_label} (prochain dans {current_interval}s)")

        try:
            events = fetch_events()

            new_events       = []
            important_events = []

            for eid, e in events.items():
                if eid not in seen:
                    new_events.append(e)
                    print(f"   🆕 NOUVEAU: {e['text']}")

                if e["important"] and eid not in notified_important:
                    important_events.append(e)
                    print(f"   🔥 IMPORTANT: {e['text']}")

            if new_events or important_events:
                last_detection_time = time.time()  # active le mode boost
                send_email(new_events, important_events)

                # Notification urgente si événement important
                is_urgent = len(important_events) > 0
                termux_notify(
                    "🚨 TICKETPLACE — NOUVELLES PLACES !",
                    f"🆕 {len(new_events)} nouveaux | 🔥 {len(important_events)} importants — RÉSERVEZ VITE !",
                    urgent=is_urgent
                )
                if is_urgent:
                    termux_toast("🔥 ÉVÉNEMENT IMPORTANT DÉTECTÉ — OUVREZ L'APP !")

                for e in important_events:
                    notified_important.add(e["id"])
                save_json_set(CONFIG["notified_important_file"], notified_important)
            else:
                print("   😐 Rien de nouveau")

            for eid in events:
                seen.add(eid)
            save_json_set(CONFIG["seen_events_file"], seen)

        except KeyboardInterrupt:
            print("\n🛑 Arrêté par l'utilisateur")
            break
        except Exception as e:
            print(f"   ❌ Erreur inattendue: {e}")

        time.sleep(current_interval)


if __name__ == "__main__":
    main()
