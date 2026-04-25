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
    "seen_file": os.path.join(SCRIPT_DIR, "seen_test.json"),
    "interval_seconds": 30,
}

URL = "https://www.reddit.com/r/worldnews/new.json?limit=5"
HEADERS = {"User-Agent": "TicketplaceTestMonitor/1.0"}


def load_seen():
    if os.path.exists(CONFIG["seen_file"]):
        with open(CONFIG["seen_file"], "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(CONFIG["seen_file"], "w") as f:
        json.dump(list(seen), f)


def fetch_posts():
    posts = {}
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        print(f"   Status: {r.status_code}")
        if r.status_code != 200:
            return posts
        items = r.json()["data"]["children"]
        for item in items:
            d = item["data"]
            posts[d["id"]] = {
                "id":       d["id"],
                "title":    d["title"],
                "url":      f"https://reddit.com{d['permalink']}",
                "found_at": datetime.now().strftime("%H:%M:%S"),
            }
            print(f"   📰 {d['title'][:60]}")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    return posts


def send_email(new_posts):
    subject = f"🆕 {len(new_posts)} nouveaux posts Reddit — TEST MONITOR"
    html = "<h2>🧪 Test Monitor — Reddit r/worldnews</h2><h3>🆕 Nouveaux posts</h3>"
    for p in new_posts:
        html += f"""<div style='border-left:4px solid #0066cc;padding:8px 12px;margin:8px 0;'>
            <a href='{p["url"]}'>{p["title"]}</a><br>
            <small>Détecté à {p["found_at"]}</small></div>"""

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


def termux_notify(title, message):
    os.system(f'termux-notification --title "{title}" --content "{message}" --sound --vibrate 1000 --priority high')


def main():
    print("=" * 50)
    print("🧪 TEST MONITOR — Reddit r/worldnews")
    print(f"⏱️  Intervalle: {CONFIG['interval_seconds']}s")
    print("🛑  Ctrl+C pour arrêter")
    print("=" * 50)

    seen  = load_seen()
    cycle = 0

    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 🔄 Cycle #{cycle}")

        try:
            posts = fetch_posts()
            print(f"   📊 {len(posts)} posts trouvés")

            new_posts = []
            for pid, p in posts.items():
                if pid not in seen:
                    new_posts.append(p)
                    print(f"   🆕 NOUVEAU: {p['title'][:50]}")

            if new_posts:
                print(f"   🆕 {len(new_posts)} nouveaux !")
                send_email(new_posts)
                termux_notify("🆕 Nouveau post Reddit", f"{len(new_posts)} nouveaux posts détectés")
            else:
                print("   😐 Rien de nouveau")

            for pid in posts:
                seen.add(pid)
            save_seen(seen)

        except KeyboardInterrupt:
            print("\n🛑 Arrêté")
            break
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

        time.sleep(CONFIG["interval_seconds"])


if __name__ == "__main__":
    main()
