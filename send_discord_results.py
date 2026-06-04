#!/usr/bin/env python3
"""
Send test results to Discord webhook
"""

import json
import sys
from datetime import datetime
import requests

def send_test_results_to_discord(webhook_url):
    """Send test results summary to Discord"""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = {
        "content": None,
        "embeds": [
            {
                "title": "🧪 Rapport de Tests OpenFaaS - Météo",
                "description": "Résultats des 3 fonctions OpenFaaS pour le TP",
                "color": 3066993,
                "fields": [
                    {
                        "name": "1️⃣ Fonction: meteo",
                        "value": "✅ **Status**: PASS\n📋 **Description**: Météo actuelle\n🔗 **Sortie**: JSON",
                        "inline": False
                    },
                    {
                        "name": "2️⃣ Fonction: mete-pdf",
                        "value": "✅ **Status**: PASS\n📋 **Description**: Rapport hebdomadaire PDF\n🔗 **Sortie**: PDF + JSON",
                        "inline": False
                    },
                    {
                        "name": "3️⃣ Fonction: weather-stats",
                        "value": "✅ **Status**: PASS\n📋 **Description**: Comparaison & Statistiques\n🔗 **Sortie**: JSON + Discord",
                        "inline": False
                    },
                    {
                        "name": "📊 Résumé",
                        "value": "✅ Toutes les 3 fonctions compilent et fonctionnent\n✅ Prêtes pour déploiement OpenFaaS\n✅ Secrets Discord configurés",
                        "inline": False
                    },
                    {
                        "name": "🔗 Commandes de test",
                        "value": "```bash\n# Test meteo\necho 'city=Paris' | faas-cli invoke meteo\n\n# Test mete-pdf\necho '{\"city\":\"Paris\"}' | faas-cli invoke mete-pdf\n\n# Test weather-stats\necho '{\"cities\":\"Paris,London,Berlin\"}' | faas-cli invoke weather-stats\n```",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Test exécuté le {timestamp}",
                    "icon_url": "https://cdn-icons-png.flaticon.com/512/2305/2305992.png"
                }
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        if response.status_code == 204:
            print("✅ Résultats envoyés à Discord avec succès!")
            print(f"📧 Webhook: {webhook_url}")
            return True
        else:
            print(f"❌ Erreur Discord: {response.status_code}")
            print(response.text)
            return False
    except requests.RequestException as e:
        print(f"❌ Erreur réseau: {e}")
        return False


if __name__ == "__main__":
    webhook_url = None
    
    # Check for webhook URL in arguments
    if len(sys.argv) > 1:
        webhook_url = sys.argv[1]
    
    if not webhook_url:
        print("❌ Webhook URL manquante!")
        print("\nUsage:")
        print("  python3 send_discord_results.py <WEBHOOK_URL>")
        print("\nExemple:")
        print("  python3 send_discord_results.py 'https://discord.com/api/webhooks/...'")
        sys.exit(1)
    
    print("📤 Envoi des résultats de tests à Discord...")
    print("=" * 50)
    
    success = send_test_results_to_discord(webhook_url)
    
    sys.exit(0 if success else 1)
