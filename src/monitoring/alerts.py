#  src/monitoring/alerts.py - Gestionnaire d'alertes

import asyncio
import aiohttp
from typing import Dict, Optional
import os

class AlertManager:
    """
     Gestionnaire d'alertes Telegram
    
    Features:
    - Alertes arbitrages exécutés
    - Alertes erreurs critiques
    - Résumés quotidiens
    - Seuils personnalisables
    """
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.telegram_token and self.telegram_chat_id)
        
        if not self.enabled:
            print(" Alertes Telegram désactivées (tokens manquants)")

    async def send_alert(self, message: str, priority: str = "info") -> bool:
        """
        Envoie une alerte Telegram
        
        Args:
            message: Message à envoyer
            priority: "info", "warning", "error", "critical"
            
        Returns:
            True si envoi réussi
        """
        if not self.enabled:
            print(f"📢 [ALERT-{priority.upper()}] {message}")
            return True
        
        try:
            # Formatage du message avec emoji selon priorité
            emoji_map = {
                "info": "ℹ️",
                "warning": "", 
                "error": "",
                "critical": ""
            }
            
            formatted_message = f"{emoji_map.get(priority, 'ℹ️')} {message}"
            
            # Envoi via API Telegram
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": formatted_message,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        print(f" Erreur envoi Telegram: {response.status}")
                        return False
                        
        except Exception as e:
            print(f" Erreur alert manager: {e}")
            return False

        async def send_daily_summary(self, portfolio_summary: Dict):
                """Envoie le résumé quotidien"""
                try:
                    summary_message = f"""
         <b>RÉSUMÉ QUOTIDIEN - BOT ARBITRAGE</b>

         <b>Performance:</b>
        • PnL Quotidien: {portfolio_summary.get('daily_pnl_usdc', 0):.2f} USDC
        • PnL Non-réalisé: {portfolio_summary.get('total_unrealized_pnl_usdc', 0):.2f} USDC
        • APR Moyen: {portfolio_summary.get('average_entry_apr', 0):.1f}%

         <b>Positions:</b>
        • Positions Actives: {portfolio_summary.get('active_positions_count', 0)}
        • Capital Utilisé: {portfolio_summary.get('capital_utilization_percent', 0):.1f}%
        • Capital Total: {portfolio_summary.get('total_capital_usdc', 0):,.0f} USDC

        🕐 <b>Dernière MAJ:</b> {portfolio_summary.get('last_updated', 'N/A')}
                    """
                    
                    await self.send_alert(summary_message.strip(), "info")
                    
                except Exception as e:
                    print(f" Erreur résumé quotidien: {e}")
