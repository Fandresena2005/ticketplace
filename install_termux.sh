#!/data/data/com.termux/files/usr/bin/bash

echo "📦 Installation Termux Monitor Ticketplace"

# Mise à jour
pkg update -y && pkg upgrade -y

# Python et pip
pkg install python -y

# Notifications Android
pkg install termux-api -y

# Dépendances Python
pip install requests cloudscraper

echo ""
echo "✅ Installation terminée !"
echo ""
echo "👉 Configure ton email dans monitor_termux.py"
echo "👉 Lance avec: python monitor_termux.py"
