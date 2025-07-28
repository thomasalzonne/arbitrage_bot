# ===============================
# 📋 Instructions de déploiement
# ===============================

deployment_instructions = """
 INSTRUCTIONS DE DÉPLOIEMENT - BOT ARBITRAGE

1. 📁 CRÉATION DE LA STRUCTURE:
   mkdir arbitrage_bot && cd arbitrage_bot
   mkdir -p src/{exchanges,data,trading,monitoring,utils} config logs data/{postgres,redis}

2.  FICHIERS À CRÉER:
   - Copier tous les fichiers .py dans src/
   - Créer requirements.txt avec les dépendances
   - Créer .env avec vos clés API
   - Créer docker-compose.yml
   - Créer les configs JSON dans config/

3. 🔑 CONFIGURATION .env:
   cp .env.example .env
   # Éditer avec vos vraies clés API

4. 🐳 DÉMARRAGE:
   docker-compose up -d postgres redis
   # Ou en local: python -m src.main

5.  MONITORING:
   # Logs: tail -f logs/arbitrage_bot.log
   # Grafana: http://localhost:3000 (admin/admin123)
   # Prometheus: http://localhost:9090

6. 🧪 TESTS INITIAUX:
   # Le bot fait des tests automatiques au démarrage
   # Vérifiez les logs pour les  de validation

7.  ALERTES TELEGRAM:
   # Créer un bot: @BotFather sur Telegram
   # Récupérer token et chat_id
   # Ajouter dans .env

 BOT PRÊT EN 7 JOURS COMME PRÉVU!
Phase 1: WooFi Pro + Hyperliquid 
Phase 2: 5 autres exchanges (à venir)