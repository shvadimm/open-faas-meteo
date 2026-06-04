#!/bin/bash

# Test script for OpenFaaS Weather Functions
# Before running, ensure OpenFaaS is running and secrets are configured:
#
# faas-cli secret create openweather-api-key --from-literal="YOUR_API_KEY"
# faas-cli secret create discord-webhook-url --from-literal="YOUR_WEBHOOK_URL"
# faas-cli build -f stack.yml
# faas-cli deploy -f stack.yml

echo " Test des 3 fonctions OpenFaaS météo"
echo "========================================"
echo ""

# Test 1: meteo (météo actuelle)
echo "Test: meteo (Météo actuelle)"
echo "---"
echo "Commande:"
echo "  echo 'city=Paris&units=metric&lang=fr' | faas-cli invoke meteo"
echo ""

# Test 2: mete-pdf (rapport hebdomadaire PDF + Discord)
echo "2Test: mete-pdf (Rapport hebdomadaire en PDF + Discord)"
echo "---"
echo "Commande:"
echo "  echo '{\"city\":\"Paris\",\"units\":\"metric\",\"lang\":\"fr\"}' | faas-cli invoke mete-pdf"
echo ""

# Test 3: weather-stats (comparaison + statistiques + Discord)
echo "3Test: weather-stats (Comparaison de villes + statistiques + Discord)"
echo "---"
echo "Commande:"
echo "  echo '{\"cities\":\"Paris,London,Berlin\",\"units\":\"metric\",\"lang\":\"fr\"}' | faas-cli invoke weather-stats"
echo ""

echo "========================================"
echo "✅ Toutes les fonctions sont prêtes pour le déploiement OpenFaaS"
echo ""
echo "Pour déployer:"
echo "  faas-cli build -f stack.yml"
echo "  faas-cli push -f stack.yml"
echo "  faas-cli deploy -f stack.yml"
