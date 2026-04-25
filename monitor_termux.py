#!/usr/bin/env python3

import smtplib
import os
import json
import time
import requests
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
    "interval_seconds": 30,
    "retry_on_error_seconds": 10,  # réessaie après 10s si erreur réseau
    "important_keywords": [
        "cgm", "examen", "concours", "inscription",
        "formation", "goethe", "delf", "dalf", "tef"
    ]
}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "fr-FR,fr;q=0.9",
    "origin": "https://www.ticketplace.io",
    "referer": "https://www.ticketplace.io/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

API_URLS = [
    ("https://web-api.ticketplace.io/api/events/upcoming-events?search=undefined", "upcoming"),
    ("https://web-api.ticketplace.io/api/events/passed-events", "passed"),
]

# Session persistante avec cloudscraper
try:
    import cloudscraper
    session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    print("✅ cloudscraper chargé")
except ImportError:
    session = requests.Session()
    session.headers.update(HEADERS)
    print("⚠️  cloudscraper absent, utilisation de requests")


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
                r = session.get(url, headers=HEADERS, timeout=15)
                print(f"   [{label}] Status: {r.status_code}")
                if r.status_code not in (200, 304):
                    print(f"   [{label}] ⚠️ Ignoré")
                    break
                items = r.json().get("data", [])
                print(f"   [{label}] 📊 {len(items)} événements")
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
                break  # succès, on sort du retry

            except requests.exceptions.ConnectionError:
                print(f"   [{label}] ❌ Pas de connexion (tentative {attempt+1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(CONFIG["retry_on_error_seconds"])
            except Exception as e:
                print(f"   [{label}] ❌ Erreur: {e}")
                break

    return events


# -------------------------
# EMAIL
# -------------------------
def send_email(new_events, important_events):
    subject = f"🎫 {len(new_events)} nouveaux | 🔥 {len(important_events)} importants — Ticketplace"
    html = f"<h2>🎫 Surveillance Ticketplace</h2>"
    html += f"<p style='color:gray'>Détecté le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}</p>"

    if important_events:
        html += "<h3 style='color:red;'>🔥 IMPORTANTS</h3>"
        for e in important_events:
            icon = "📅" if e["type"] == "upcoming" else "✅"
            html += f"""<div style='border-left:4px solid red;padding:8px 12px;margin:8px 0;'>
                {icon} <b><a href='{e["url"]}'>{e["text"]}</a></b><br>
                📍 {e["location"]}<br>
                🗓️ {e["startDate"]} → {e["endDate"]}<br>
                🏷️ {e["category"]}</div>"""

    if new_events:
        html += "<h3>🆕 Nouveaux</h3>"
        for e in new_events:
            icon = "📅" if e["type"] == "upcoming" else "✅"
            flag = " 🔥" if e["important"] else ""
            html += f"""<div style='border-left:4px solid #0066cc;padding:8px 12px;margin:8px 0;'>
                {icon}{flag} <a href='{e["url"]}'>{e["text"]}</a><br>
                📍 {e["location"]} — 🗓️ {e["startDate"]}</div>"""

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
# NOTIFICATION ANDROID
# -------------------------
def termux_notify(title, message):
    os.system(f'termux-notification --title "{title}" --content "{message}" --sound --vibrate 1000 --priority high')


# -------------------------
# MAIN
# -------------------------
def main():
    print("=" * 50)
    print("🚀 Monitor Ticketplace — mode boucle Termux")
    print(f"⏱️  Intervalle: {CONFIG['interval_seconds']}s")
    print("🛑  Ctrl+C pour arrêter")
    print("=" * 50)

    seen               = load_json_set(CONFIG["seen_events_file"])
    notified_important = load_json_set(CONFIG["notified_important_file"])
    cycle = 0

    while True:
        cycle += 1
        now = datetime.now().strftime("%d/%m %H:%M:%S")
        print(f"\n[{now}] 🔄 Cycle #{cycle}")

        try:
            events = fetch_events()
            print(f"   📊 Total: {len(events)} événements")

            new_events       = []
            important_events = []

            for eid, e in events.items():
                # Nouveau = jamais vu
                if eid not in seen:
                    new_events.append(e)
                    print(f"   🆕 NOUVEAU: {e['text']}")

                # Important = jamais notifié (évite les doublons)
                if e["important"] and eid not in notified_important:
                    important_events.append(e)
                    print(f"   🔥 IMPORTANT: {e['text']}")

            if new_events or important_events:
                send_email(new_events, important_events)
                termux_notify(
                    "🎫 Ticketplace",
                    f"🆕 {len(new_events)} nouveaux | 🔥 {len(important_events)} importants"
                )
                # Marquer les importants comme notifiés
                for e in important_events:
                    notified_important.add(e["id"])
                save_json_set(CONFIG["notified_important_file"], notified_important)
            else:
                print("   😐 Rien de nouveau")

            # Marquer tous comme vus
            for eid in events:
                seen.add(eid)
            save_json_set(CONFIG["seen_events_file"], seen)

        except KeyboardInterrupt:
            print("\n🛑 Arrêté par l'utilisateur")
            break
        except Exception as e:
            print(f"   ❌ Erreur inattendue: {e}")

        time.sleep(CONFIG["interval_seconds"])


if __name__ == "__main__":
    main()
