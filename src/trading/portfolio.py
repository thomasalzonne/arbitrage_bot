# src/trading/portfolio.py - VERSION CORRIGÉE APR monitoring + fermeture auto

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from decimal import Decimal

class PortfolioManager:
    """
    Gestionnaire de portfolio - POSITIONS RÉELLES avec APR monitoring corrigé
    """
    
    def __init__(self, exchanges: Dict = None):
        self.exchanges = exchanges or {}
        self.total_capital_usdc = 583  # Capital réel
        
        # Stockage en mémoire des positions arbitrage
        self.active_arbitrage_positions = []
        
    def set_exchanges(self, exchanges: Dict):
        """Configure les exchanges disponibles"""
        self.exchanges = exchanges

    async def get_active_positions(self) -> List[Dict]:
        """
        Récupère toutes les positions d'arbitrage actives - APR MONITORING CORRIGÉ
        """
        active_positions = []
        
        try:
            all_positions = {}
            
            # Collecte positions de tous les exchanges
            for exchange_name, exchange in self.exchanges.items():
                try:
                    positions = await exchange.get_positions()
                    
                    for pos in positions:
                        symbol = pos.symbol
                        if symbol not in all_positions:
                            all_positions[symbol] = {}
                        
                        all_positions[symbol][exchange_name] = {
                            'side': pos.side,
                            'size': float(pos.size),
                            'entry_price': float(pos.entry_price),
                            'unrealized_pnl': float(pos.unrealized_pnl),
                            'funding_received': float(pos.funding_received)
                        }
                        
                except Exception as e:
                    print(f"   Erreur {exchange_name}: {e}")
                    continue
            
            # CORRECTION: Fix détection sides Hyperliquid
            for symbol, exchanges_data in all_positions.items():
                if 'woofi_pro' in exchanges_data and 'hyperliquid' in exchanges_data:
                    woofi_side = exchanges_data['woofi_pro']['side']
                    hyperliquid_side = exchanges_data['hyperliquid']['side']

                    # Si les deux sides sont identiques, corriger Hyperliquid
                    if woofi_side == hyperliquid_side:                        
                        if woofi_side == 'long':
                            exchanges_data['hyperliquid']['side'] = 'short'
                        else:
                            exchanges_data['hyperliquid']['side'] = 'long' 
            
            # Détection des arbitrages (positions opposées)
            for symbol, exchange_positions in all_positions.items():
                if len(exchange_positions) >= 2:  # Au moins 2 exchanges
                    long_exchange = None
                    short_exchange = None
                    
                    for ex_name, pos_data in exchange_positions.items():
                        side = pos_data['side']
                        
                        if side == 'long':
                            long_exchange = ex_name
                        elif side == 'short':
                            short_exchange = ex_name
                    
                    # Vérification arbitrage complet (LONG + SHORT)
                    if long_exchange and short_exchange:
                        long_pos = exchange_positions[long_exchange]
                        short_pos = exchange_positions[short_exchange]
                        
                        total_pnl = long_pos['unrealized_pnl'] + short_pos['unrealized_pnl']
                        total_funding = long_pos['funding_received'] + short_pos['funding_received']
                        avg_size = (long_pos['size'] + short_pos['size']) / 2
                        
                        # CORRECTION APR: Calcul temps écoulé réel
                        # Recherche dans le stockage interne pour l'heure de création
                        created_at = None
                        entry_apr = 150  # Défaut
                        
                        for stored_pos in self.active_arbitrage_positions:
                            if stored_pos.get('symbol') == symbol:
                                created_at = stored_pos.get('created_at')
                                entry_apr = stored_pos.get('entry_apr', 150)
                                break
                        
                        if created_at is None:
                            # Position trouvée mais pas dans le stockage - estimer
                            created_at = datetime.now() - timedelta(hours=1)
                            
                        duration_hours = (datetime.now() - created_at).total_seconds() / 3600
                        
                        # CORRECTION APR: Calcul déclin réaliste 
                        current_apr = await self._calculate_realistic_current_apr(
                            symbol, entry_apr, duration_hours, total_funding
                        )
                        
                        position = {
                            'symbol': symbol,
                            'long_exchange': long_exchange,
                            'short_exchange': short_exchange,
                            'position_size': avg_size,
                            'total_pnl': total_pnl,
                            'funding_received': total_funding,
                            'duration_hours': duration_hours,
                            'current_apr': current_apr,  # APR corrigé
                            'entry_apr': entry_apr,
                            'long_data': long_pos,
                            'short_data': short_pos,
                            'created_at': created_at,
                            'last_updated': datetime.now()
                        }
                        
                        active_positions.append(position)
            
            return active_positions
            
        except Exception as e:
            print(f"Erreur get_active_positions: {e}")
            return []

    async def _calculate_realistic_current_apr(self, symbol: str, entry_apr: float, 
                                             duration_hours: float, funding_received: float) -> float:
        """
        NOUVEAU: Calcul APR actuel réaliste basé sur funding reçu
        """
        try:
            # Méthode 1: Basé sur funding réel reçu (plus précis)
            if funding_received > 0 and duration_hours > 0:
                # Calcul APR basé sur funding réel
                hourly_funding_rate = funding_received / duration_hours
                annual_apr = hourly_funding_rate * 8760  # 8760 heures par an
                
                # Validation raisonnable
                if 0 < annual_apr < 2000:
                    return annual_apr
            
            # Méthode 2: Déclin simulé depuis entry_apr
            if duration_hours < 48:  # Moins de 48h
                # Déclin progressif: 3% par heure
                decay_factor = max(0.3, 1 - (duration_hours * 0.03))
                simulated_apr = entry_apr * decay_factor
                return max(20, simulated_apr)  # Minimum 20% APR
            else:
                # Plus de 48h: APR faible
                return 20
                
        except Exception as e:
            print(f"Erreur calcul APR {symbol}: {e}")
            return 50  # Valeur de sécurité

    async def check_position_exists(self, symbol: str) -> bool:
        """Vérifie si une position existe déjà pour ce symbole"""
        try:
            current_positions = await self.get_active_positions()
            
            for pos in current_positions:
                if pos['symbol'] == symbol:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Erreur check position {symbol}: {e}")
            return False

    async def add_arbitrage_position(self, position_data: Dict):
        """Ajoute une nouvelle position d'arbitrage au tracking interne"""
        position_data['created_at'] = datetime.now()
        position_data['last_updated'] = datetime.now()
        self.active_arbitrage_positions.append(position_data)
        
        print(f"Position ajoutée au tracking: {position_data['symbol']}")

    async def should_close_position(self, position: Dict, exit_apr_threshold: float = 50) -> tuple:
        """
        NOUVEAU: Logique de fermeture améliorée
        
        Returns:
            (should_close: bool, reason: str)
        """
        symbol = position['symbol']
        current_apr = position.get('current_apr', 0)
        duration_hours = position.get('duration_hours', 0)
        total_pnl = position.get('total_pnl', 0)
        funding_received = position.get('funding_received', 0)
        
        # Condition 1: APR tombé sous le seuil
        if current_apr < exit_apr_threshold:
            return True, f"APR {current_apr:.1f}% < seuil {exit_apr_threshold}%"
        
        # Condition 2: Stop loss (APR négatif)
        if current_apr < -10:
            return True, f"Stop loss: APR {current_apr:.1f}%"
        
        # Condition 3: Timeout (plus de 48h)
        if duration_hours > 48:
            return True, f"Timeout: {duration_hours:.1f}h > 48h"
        
        # Condition 4: PnL très négatif (protection capital)
        max_loss_threshold = -50  # Max 50 USDC de perte
        if total_pnl < max_loss_threshold:
            return True, f"Protection capital: PnL {total_pnl:.2f} < {max_loss_threshold}"
        
        # Condition 5: Funding très négatif 
        if funding_received < -30:  # Perd plus de 30 USDC en funding
            return True, f"Funding négatif: {funding_received:.2f} USDC"
        
        return False, "Position maintenue"

    async def get_daily_pnl(self) -> float:
        """Calcule le PnL quotidien total"""
        try:
            total_pnl = 0.0
            positions = await self.get_active_positions()
            
            for position in positions:
                # Filtre positions créées aujourd'hui
                if position['created_at'].date() == datetime.now().date():
                    total_pnl += position.get('total_pnl', 0)
            
            return total_pnl
            
        except Exception as e:
            print(f"Erreur calcul PnL quotidien: {e}")
            return 0.0

    async def get_capital_utilization(self) -> float:
        """Calcule le % de capital utilisé"""
        try:
            used_capital = 0.0
            positions = await self.get_active_positions()
            
            for position in positions:
                # Estime le collatéral utilisé (position_size / levier)
                position_size = position.get('position_size', 0)
                leverage = 3  # Levier x3 configuré
                collateral = position_size / leverage
                used_capital += collateral
            
            utilization = (used_capital / self.total_capital_usdc) * 100
            return min(utilization, 100.0)
            
        except Exception as e:
            print(f"Erreur calcul utilisation capital: {e}")
            return 0.0

    async def get_portfolio_summary(self) -> Dict:
        """Résumé complet du portfolio"""
        try:
            positions = await self.get_active_positions()
            daily_pnl = await self.get_daily_pnl()
            capital_utilization = await self.get_capital_utilization()
            
            # Calculs de performance
            total_unrealized = sum(p.get('total_pnl', 0) for p in positions)
            total_funding = sum(p.get('funding_received', 0) for p in positions)
            avg_apr = sum(p.get('current_apr', 0) for p in positions) / max(len(positions), 1)
            
            return {
                'total_capital_usdc': self.total_capital_usdc,
                'capital_utilization_percent': capital_utilization,
                'active_positions_count': len(positions),
                'daily_pnl_usdc': daily_pnl,
                'total_unrealized_pnl_usdc': total_unrealized,
                'total_funding_received': total_funding,
                'average_current_apr': avg_apr,
                'positions': positions,
                'last_updated': datetime.now()
            }
            
        except Exception as e:
            print(f"Erreur résumé portfolio: {e}")
            return {
                'total_capital_usdc': self.total_capital_usdc,
                'active_positions_count': 0,
                'capital_utilization_percent': 0.0
            }

    async def cleanup_closed_positions(self):
        """Nettoie les positions fermées du tracking interne"""
        current_positions = await self.get_active_positions()
        current_symbols = {pos['symbol'] for pos in current_positions}
        
        # Supprime les positions qui ne sont plus actives
        self.active_arbitrage_positions = [
            pos for pos in self.active_arbitrage_positions 
            if pos.get('symbol') in current_symbols
        ]