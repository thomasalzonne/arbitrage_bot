# src/data/analyzer.py - Analyseur avec debug et filtrage corrigé

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta

class ArbitrageAnalyzer:
    """
    Analyseur d'opportunités d'arbitrage avec debug détaillé
    
    Features:
    - Filtrage par APR minimum
    - Debug complet du filtrage
    - Timing optimization corrigé
    - Confiance adaptative
    """
    
    def __init__(self):
        self.max_funding_time_minutes = 2    # Buffer technique minimal
        
    async def filter_profitable_opportunities(self, opportunities: List[Dict], 
                                            min_apr: float = 80) -> List[Dict]:
        """
        Filtre les opportunités - AVEC DEBUG DÉTAILLÉ POUR IDENTIFIER POURQUOI HYPER/SOPH SKIPPÉS
        """
        viable_opportunities = []
        
        
        for i, opp in enumerate(opportunities):
            symbol = opp['symbol']
            apr = opp['apr']
            confidence = opp.get('confidence', 0) * 100 # En pourcentage
            long_ex = opp.get('long_exchange', 'N/A')
            short_ex = opp.get('short_exchange', 'N/A')
            
            # Filtre 1: APR minimum
            if apr < min_apr:
                continue
            else:
                print(f"    APR OK: {apr:.1f}% >= {min_apr}%")
                
            # Filtre 2: Timing funding (CORRIGÉ)
            time_left = self._time_until_funding()
            if time_left <= self.max_funding_time_minutes:
                print(f"    REJETÉ: Timing ({time_left} min <= {self.max_funding_time_minutes} min)")
                continue
            else:
                print(f"    Timing OK: {time_left} min > {self.max_funding_time_minutes} min")
            
            # Filtre 3: Confiance minimum (ASSOUPLI)
            min_confidence = 0.1  # Abaissé de 0.3 à 0.1 pour capturer plus d'opportunités
            if confidence < min_confidence:
                print(f"    REJETÉ: Confiance trop faible ({confidence:.3f} < {min_confidence})")
                continue
            else:
                print(f"    Confiance OK: {confidence:.3f} >= {min_confidence}")
            
            # Filtre 4: Exchanges disponibles
            exchanges_available = all([
                long_ex in ['hyperliquid', 'woofi_pro'],
                short_ex in ['hyperliquid', 'woofi_pro'],
                long_ex != short_ex
            ])
            
            if not exchanges_available:
                print(f"    REJETÉ: Exchanges indisponibles ({long_ex}, {short_ex})")
                continue
            else:
                print(f"    Exchanges OK: {long_ex} ↔ {short_ex}")
            
            #  ACCEPTÉ
            print(f"    ACCEPTÉ: {symbol} ({apr:.1f}% APR)")
            
            # Enrichissement des données
            opp['estimated_profit_1k'] = self._calculate_profit_estimate(opp, 1000)
            opp['risk_score'] = self._calculate_risk_score(opp)
            if confidence > 50:  # Confiance très élevée (ex: MOVE-PERP = 100)
                # Pour les très hautes confidences, on privilégie l'APR
                opp['execution_priority'] = apr * 1.5  # Boost APR pour haute confiance
            elif apr > 500:  # APR très élevé (ex: HYPER, SOPH)
                # Pour les très hauts APR, on privilégie l'APR même avec confiance faible
                opp['execution_priority'] = apr * 2.0  # Double priorité pour haut APR
            else:
                # Calcul standard
                opp['execution_priority'] = apr * (confidence / 10)
            
            print(f"    Priorité d'exécution: {opp['execution_priority']:.1f}")
            
            viable_opportunities.append(opp)
        
        # Tri par priorité d'exécution
        viable_opportunities.sort(key=lambda x: x['execution_priority'], reverse=True)
        
        print(f"\n RÉSULTAT FINAL: {len(viable_opportunities)} opportunités acceptées")
        print("="*80)
        
        # Debug top acceptées
        print("🏆 TOP OPPORTUNITÉS APRÈS FILTRAGE:")
        for i, opp in enumerate(viable_opportunities[:5], 1):
            print(f"   {i}. {opp['symbol']}: {opp['apr']:.1f}% APR (priorité: {opp['execution_priority']:.1f})")
        
        return viable_opportunities

    async def calculate_current_apr(self, position: Dict) -> float:
        """Calcule l'APR actuel d'une position existante"""
        entry_apr = position.get('entry_apr', 100)
        duration_hours = position.get('duration_hours', 0)
        
        # Simulation de déclin APR dans le temps
        decay_factor = max(0.5, 1 - (duration_hours * 0.02))  # 2% déclin par heure (moins agressif)
        current_apr = entry_apr * decay_factor
        
        return max(0, current_apr)

    def _calculate_profit_estimate(self, opportunity: Dict, capital_usdc: float) -> float:
        """Estime le profit pour un capital donné"""
        hourly_rate = opportunity.get('net_rate', 0)
        
        # Différencie funding frequency (Hyperliquid=1h, autres=8h)
        if 'hyperliquid' in [opportunity.get('long_exchange', ''), opportunity.get('short_exchange', '')]:
            periods_per_day = 24
        else:
            periods_per_day = 3
            
        daily_profit = capital_usdc * hourly_rate * periods_per_day
        return daily_profit

    def _calculate_risk_score(self, opportunity: Dict) -> float:
        """Calcule un score de risque (0=safe, 1=risky)"""
        apr = opportunity.get('apr', 0)
        confidence = opportunity.get('confidence', 0.5)
        symbol = opportunity.get('symbol', '')
        
        # APR très élevé = plus risqué (mean reversion)
        apr_risk = min(apr / 1000, 0.4)  # Ajusté pour APR plus élevés
        
        # Faible confiance = plus risqué
        confidence_risk = (1 - confidence) * 0.5
        
        # Coins moins liquides = plus risqués
        major_coins = ['BTC-PERP', 'ETH-PERP', 'SOL-PERP', 'AVAX-PERP']
        liquidity_risk = 0.1 if symbol in major_coins else 0.2
        
        # Score combiné
        risk_score = (apr_risk + confidence_risk + liquidity_risk) / 3
        return min(risk_score, 1.0)

    def _time_until_funding(self) -> int:
        """Minutes jusqu'au prochain funding - AVEC DEBUG"""
        now = datetime.now()
        next_funding = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        minutes_left = int((next_funding - now).total_seconds() / 60)
        
        print(f" TIMING FUNDING:")
        print(f"   Maintenant: {now.strftime('%H:%M:%S')}")
        print(f"   Prochain funding: {next_funding.strftime('%H:%M:%S')}")
        print(f"   Minutes restantes: {minutes_left}")
        
        return minutes_left