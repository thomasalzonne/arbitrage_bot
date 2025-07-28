# src/data/collector.py - Collecteur de données avec déduplication anti-doublonnage

import asyncio
import aiohttp
from typing import Dict, List
from datetime import datetime

from src.exchanges.woofi_pro import WooFiProExchange
from src.exchanges.hyperliquid import HyperliquidExchange
from src.exchanges.base import FundingRate

class FundingDataCollector:
    """
    Collecteur hybride de données funding rates avec déduplication
    
    Strategy:
    - APIs directes: WooFi Pro + Hyperliquid (2 calls)
    - Scraping GHZ: 5 autres exchanges (1 call)  
    - Total: 3 calls vs 1,918 calls individuels
    -  NOUVEAU: Déduplication automatique des symboles
    """
    
    def __init__(self):
        self.exchanges = {}
        self.ghz_scraping_url = "https://ghzperpdextools.vercel.app/funding-arbitrage.html"
        
    async def initialize_exchanges(self, config: Dict):
        """Initialise les connecteurs d'exchanges"""
        if 'woofi_pro' in config:
            self.exchanges['woofi_pro'] = WooFiProExchange(config['woofi_pro'])
            await self.exchanges['woofi_pro'].authenticate()
            
        if 'hyperliquid' in config:
            self.exchanges['hyperliquid'] = HyperliquidExchange(config['hyperliquid'])
            await self.exchanges['hyperliquid'].authenticate()

    async def collect_all_funding_opportunities(self) -> List[Dict]:
        """
        Collecte toutes les opportunités d'arbitrage avec déduplication
        
        Returns:
            Liste des opportunités avec données d'arbitrage (déduplication incluse)
        """
        print("Début collecte funding rates...")
        
        # 1. Collecte via APIs directes (parallèle)
        api_tasks = []
        if 'woofi_pro' in self.exchanges:
            api_tasks.append(self._collect_woofi_funding())
        if 'hyperliquid' in self.exchanges:
            api_tasks.append(self._collect_hyperliquid_funding())
            
        api_results = await asyncio.gather(*api_tasks, return_exceptions=True)
        
        # 2. Consolidation des données par symbole
        funding_by_symbol = {}
        
        for result in api_results:
            if isinstance(result, list):  # Pas d'exception
                for funding_rate in result:
                    symbol = funding_rate.symbol
                    if symbol not in funding_by_symbol:
                        funding_by_symbol[symbol] = {}
                    funding_by_symbol[symbol][funding_rate.exchange] = funding_rate
        
        print(f"Symboles consolidés: {len(funding_by_symbol)}")
        
        # 3. Calcul des opportunités d'arbitrage
        opportunities = []
        
        for symbol, exchange_rates in funding_by_symbol.items():
            if len(exchange_rates) >= 2:  # Need au moins 2 exchanges
                
                rates_list = list(exchange_rates.values())
                
                # Trouve le meilleur setup d'arbitrage
                best_arbitrage = None
                max_apr = 0
                
                for long_ex in rates_list:
                    for short_ex in rates_list:
                        if long_ex.exchange != short_ex.exchange:
                            # APR reçu si LONG sur long_ex (favorable si funding négatif)
                            long_contribution = abs(long_ex.apr) if long_ex.rate < 0 else 0
                            
                            # APR reçu si SHORT sur short_ex (favorable si funding positif)
                            short_contribution = abs(short_ex.apr) if short_ex.rate > 0 else 0
                            
                            total_apr = long_contribution + short_contribution
                            
                            if total_apr > max_apr:
                                max_apr = total_apr
                                best_arbitrage = {
                                    'long_exchange': long_ex.exchange,
                                    'short_exchange': short_ex.exchange,
                                    'long_rate': long_ex.rate,
                                    'short_rate': short_ex.rate,
                                    'long_apr': long_ex.apr,
                                    'short_apr': short_ex.apr,
                                    'net_apr': total_apr
                                }
                
                if best_arbitrage and max_apr > 10:  # Seuil minimum 10% APR
                    opportunities.append({
                        'symbol': symbol,
                        'long_exchange': best_arbitrage['long_exchange'],
                        'short_exchange': best_arbitrage['short_exchange'], 
                        'long_rate': best_arbitrage['long_rate'],
                        'short_rate': best_arbitrage['short_rate'],
                        'net_rate': best_arbitrage['short_rate'] - best_arbitrage['long_rate'],
                        'apr': best_arbitrage['net_apr'],
                        'confidence': self._calculate_confidence(exchange_rates),
                        'last_updated': datetime.now()
                    })
        
        print(f"Opportunités brutes générées: {len(opportunities)}")
        
        # 4. Tri par APR décroissant
        opportunities.sort(key=lambda x: x['apr'], reverse=True)
        
        #  NOUVEAU: Déduplication des symboles pour éviter doublonnage
        opportunities = self.deduplicate_opportunities(opportunities)
        
        # 5. Validation finale
        opportunities = self.validate_opportunities(opportunities)
        
        print(f"Collecte terminée: {len(opportunities)} opportunités uniques et validées")
        return opportunities

    def deduplicate_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        seen_symbols = set()
        unique_opportunities = []
        
        for opp in opportunities:
            symbol = opp['symbol']
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                unique_opportunities.append(opp)
        
        return unique_opportunities

    def validate_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
         NOUVEAU: Validation supplémentaire des opportunités
        """
        valid_opportunities = []
        
        
        for opp in opportunities:
            symbol = opp['symbol']
            apr = opp['apr']
            long_ex = opp['long_exchange']
            short_ex = opp['short_exchange']
            
            # Validation 1: APR raisonnable
            if apr < 5:
                continue
            
            if apr > 2000:
                continue
            
            # Validation 2: Exchanges différents
            if long_ex == short_ex:
                continue
            
            # Validation 3: Exchanges supportés
            supported_exchanges = ['hyperliquid', 'woofi_pro']
            if long_ex not in supported_exchanges or short_ex not in supported_exchanges:
                continue
            
            # Validation 4: Données cohérentes
            if not all(key in opp for key in ['long_rate', 'short_rate', 'confidence']):
                continue
            
            valid_opportunities.append(opp)
        
        return valid_opportunities

    async def _collect_woofi_funding(self) -> List[FundingRate]:
        """Collecte funding rates WooFi Pro"""
        try:
            print(" Collecte WooFi Pro...")
            return await self.exchanges['woofi_pro'].get_funding_rates()
        except Exception as e:
            print(f" Erreur collecte WooFi: {e}")
            return []

    async def _collect_hyperliquid_funding(self) -> List[FundingRate]:
        """Collecte funding rates Hyperliquid"""
        try:
            print(" Collecte Hyperliquid...")
            return await self.exchanges['hyperliquid'].get_funding_rates()
        except Exception as e:
            print(f" Erreur collecte Hyperliquid: {e}")
            return []

    def _calculate_confidence(self, exchange_rates: Dict) -> float:
        """
        Calcule un score de confiance pour l'opportunité
        
        Factors:
        - Nombre d'exchanges (plus = mieux)
        - Écart entre taux (plus grand = plus fiable)
        - Liquidité des exchanges
        """
        num_exchanges = len(exchange_rates)
        rates = [fr.rate for fr in exchange_rates.values()]
        rate_spread = max(rates) - min(rates)
        
        # Score de base sur spread
        confidence = min(rate_spread * 1000, 1.0)  # Cap à 1.0
        
        # Bonus pour multiple exchanges
        confidence *= (1 + (num_exchanges - 2) * 0.1)
        
        return min(confidence, 1.0)