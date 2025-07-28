# 💱 src/trading/executor.py - LEVIER x3 + PROTECTION ANTI-DOUBLONNAGE

import asyncio
import time
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

class TradeExecutor:
    """
    💱 Exécuteur d'arbitrages funding rates - LEVIER x3 + PROTECTION ANTI-DOUBLONNAGE
    """
    
    def __init__(self, exchanges: Dict = None):
        self.exchanges = exchanges or {}
        self.leverage = 3  #  LEVIER x3 PERMANENT
        self.max_position_size_usdc = 500  # Augmenté pour levier
        self.max_slippage_percent = 0.5
        self.execution_timeout_seconds = 30
        
    def set_exchanges(self, exchanges: Dict):
        """Configure les exchanges disponibles"""
        self.exchanges = exchanges

    async def execute_arbitrage(self, opportunity: Dict) -> bool:
        """
        Exécute un arbitrage - AVEC LEVIER x3 + PROTECTION ANTI-DOUBLONNAGE
        """
        symbol = opportunity['symbol']
        long_exchange_name = opportunity['long_exchange']
        short_exchange_name = opportunity['short_exchange']
        estimated_apr = opportunity['apr']
        
        print(f"\n ===== EXÉCUTION ARBITRAGE {symbol} =====")
        print(f" APR: {estimated_apr:.1f}%")
        print(f" LONG sur {long_exchange_name} | SHORT sur {short_exchange_name}")
        print(f" LEVIER: x{self.leverage} (PERMANENT)")
        
        #  PROTECTION 1: Validation des exchanges
        if not self._validate_exchanges(long_exchange_name, short_exchange_name):
            print(f" Exchanges non disponibles")
            return False
        
        long_exchange = self.exchanges[long_exchange_name]
        short_exchange = self.exchanges[short_exchange_name]
        
        #  PROTECTION 2: Double vérification avant exécution
        print(f" Double vérification avant exécution...")
        
        if not await self._final_position_check(long_exchange, short_exchange, symbol):
            print(f" STOP: Position {symbol} déjà détectée lors de la vérification finale")
            return False
        
        print(f" Aucune position conflictuelle détectée - Procédure d'exécution")
        
        #  PROTECTION 3: Calcul de la taille de position AVEC LEVIER
        collateral_needed, position_size = await self._calculate_leveraged_position_size(opportunity)
        if position_size <= 0:
            return False
        
        
        #  PROTECTION 4: Pré-vérifications (sur le collatéral)
        if not await self._pre_execution_checks(long_exchange, short_exchange, symbol, collateral_needed):
            return False
        
        #  PROTECTION 5: Configuration du levier sur les deux exchanges
        await self._setup_leverage(long_exchange, short_exchange, symbol)
        
        # 6. Exécution simultanée des deux côtés
        execution_start = time.time()
        
        try:
            
            # Lancement des deux ordres en parallèle
            long_task = asyncio.create_task(
                self._place_long_position(long_exchange, symbol, position_size)
            )
            short_task = asyncio.create_task(
                self._place_short_position(short_exchange, symbol, position_size)
            )
            
            # Attente avec timeout
            long_result, short_result = await asyncio.wait_for(
                asyncio.gather(long_task, short_task, return_exceptions=True),
                timeout=self.execution_timeout_seconds
            )
            
            execution_time = time.time() - execution_start
            
            # Validation des résultats
            long_success = isinstance(long_result, dict) and long_result.get('success', False)
            short_success = isinstance(short_result, dict) and short_result.get('success', False)
            
            if long_success and short_success:
                print(f" ===== ARBITRAGE EXÉCUTÉ AVEC SUCCÈS! =====")
                print(f"   Long order: {long_result.get('order_id')}")
                print(f"   Short order: {short_result.get('order_id')}")
                print(f"    Profits funding multipliés par x{self.leverage}!")
                print(f"    Temps d'exécution: {execution_time:.2f}s")
                
                # Sauvegarde position
                await self._save_arbitrage_position({
                    'symbol': symbol,
                    'long_exchange': long_exchange_name,
                    'short_exchange': short_exchange_name,
                    'position_size': position_size,
                    'collateral_used': collateral_needed,
                    'leverage': self.leverage,
                    'entry_apr': estimated_apr,
                    'leveraged_apr': estimated_apr * self.leverage,  # APR effectif
                    'long_order_id': long_result.get('order_id'),
                    'short_order_id': short_result.get('order_id'),
                    'execution_time': execution_time,
                    'created_at': datetime.now()
                })
                
                return True
                
            else:
                # Rollback en cas d'échec partiel
                print(f" EXÉCUTION PARTIELLE - Rollback nécessaire")
                print(f"   Long success: {long_success}")
                print(f"   Short success: {short_success}")
                
                await self._rollback_partial_execution(
                    long_result if long_success else None,
                    short_result if short_success else None,
                    long_exchange, short_exchange, symbol
                )
                return False
                
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            print(f" Erreur exécution: {e}")
            return False

    async def _final_position_check(self, long_exchange, short_exchange, symbol: str) -> bool:
        """
         NOUVEAU: Vérification finale avant exécution pour éviter doublonnage
        """
        try:
            print(f" Vérification finale positions existantes pour {symbol}...")
            
            # Vérification positions sur long exchange
            long_positions = await long_exchange.get_positions()
            for pos in long_positions:
                if pos.symbol == symbol:
                    print(f" Position {symbol} déjà présente sur {long_exchange.name}")
                    print(f"   Side: {pos.side} | Size: {pos.size}")
                    return False
            
            # Vérification positions sur short exchange
            short_positions = await short_exchange.get_positions()
            for pos in short_positions:
                if pos.symbol == symbol:
                    print(f" Position {symbol} déjà présente sur {short_exchange.name}")
                    print(f"   Side: {pos.side} | Size: {pos.size}")
                    return False
            
            print(f" Aucune position {symbol} existante sur les exchanges")
            return True
            
        except Exception as e:
            print(f" Erreur vérification finale: {e}")
            return False

    async def _calculate_leveraged_position_size(self, opportunity: Dict) -> tuple:
        """
        Calcule la taille de position avec levier x3
        
        Returns:
            (collateral_needed, position_size)
        """
        available_capital = 580  # Capital réel
        apr = opportunity['apr']
        
        # Pourcentage du capital à utiliser en collatéral
        if apr >= 500:
            capital_percent = 0.25  # 25% pour très haut APR
        elif apr >= 300:
            capital_percent = 0.20  # 20% pour haut APR
        elif apr >= 150:
            capital_percent = 0.15  # 15% pour APR moyen
        else:
            capital_percent = 0.08  # 8% pour APR faible
        
        # Calcul collatéral
        collateral_needed = available_capital * capital_percent
        
        # Taille de position avec levier
        position_size = collateral_needed * self.leverage
        
        # Limites de sécurité
        min_collateral = 50   # Min 50 USDC de collatéral
        max_collateral = 150  # Max 150 USDC de collatéral
        
        collateral_needed = max(min_collateral, min(collateral_needed, max_collateral))
        position_size = collateral_needed * self.leverage

        collateral_needed = round(collateral_needed, 2)
        position_size = round(position_size, 2)
        
        
        return collateral_needed, position_size

    async def _setup_leverage(self, long_exchange, short_exchange, symbol: str):
        """ CRUCIAL : Configure le levier x3 sur les deux exchanges"""
        
        # Setup levier sur long exchange
        try:
            if hasattr(long_exchange, 'set_leverage'):
                await long_exchange.set_leverage(symbol, self.leverage)
            else:
                print(f"    {long_exchange.name} ne supporte pas set_leverage")
        except Exception as e:
            print(f"    Erreur levier {long_exchange.name}: {e}")
        
        # Setup levier sur short exchange
        try:
            if hasattr(short_exchange, 'set_leverage'):
                await short_exchange.set_leverage(symbol, self.leverage)
            else:
                print(f"    {short_exchange.name} ne supporte pas set_leverage")
        except Exception as e:
            print(f"    Erreur levier {short_exchange.name}: {e}")

    async def _place_long_position(self, exchange, symbol: str, size: float) -> Dict:
        """Place une position LONG avec levier x3"""
        try:
            print(f"    Ouverture LONG {symbol} (x{self.leverage}) sur {exchange.name}")
            
            result = await exchange.place_order(
                symbol=symbol,
                side="buy",
                size=Decimal(str(size)),
                order_type="market"
            )
            
            if result.get('success'):
                print(f"    LONG ouvert: {result.get('order_id')} - Levier x{self.leverage}")
            else:
                print(f"    Échec LONG: {result.get('error', 'Erreur inconnue')}")
            
            return result
        except Exception as e:
            print(f"    Erreur LONG: {e}")
            return {"success": False, "error": str(e)}

    async def _place_short_position(self, exchange, symbol: str, size: float) -> Dict:
        """Place une position SHORT avec levier x3"""
        try:
            print(f"    Ouverture SHORT {symbol} (x{self.leverage}) sur {exchange.name}")
            
            result = await exchange.place_order(
                symbol=symbol,
                side="sell",
                size=Decimal(str(size)),
                order_type="market"
            )
            
            if result.get('success'):
                print(f"    SHORT ouvert: {result.get('order_id')} - Levier x{self.leverage}")
            else:
                print(f"    Échec SHORT: {result.get('error', 'Erreur inconnue')}")
            
            return result
        except Exception as e:
            print(f"    Erreur SHORT: {e}")
            return {"success": False, "error": str(e)}

    def _validate_exchanges(self, long_exchange_name: str, short_exchange_name: str) -> bool:
        """Valide que les exchanges sont disponibles et authentifiés"""
        if long_exchange_name not in self.exchanges:
            print(f" Exchange {long_exchange_name} non disponible")
            return False
        
        if short_exchange_name not in self.exchanges:
            print(f" Exchange {short_exchange_name} non disponible")
            return False
        
        if not self.exchanges[long_exchange_name].authenticated:
            print(f" Exchange {long_exchange_name} non authentifié")
            return False
        
        if not self.exchanges[short_exchange_name].authenticated:
            print(f" Exchange {short_exchange_name} non authentifié")
            return False
        
        return True

    async def _pre_execution_checks(self, long_exchange, short_exchange, 
                                   symbol: str, collateral_needed: float) -> bool:
        """Vérifications avant exécution - sur le collatéral requis"""
        try:
            
            # Check balances pour le collatéral
            long_balances = await long_exchange.get_balances()
            short_balances = await short_exchange.get_balances()
            
            # Recherche USDC
            long_usdc = next((b for b in long_balances if b.asset == 'USDC'), None)
            short_usdc = next((b for b in short_balances if b.asset == 'USDC'), None)
            
            if not long_usdc or not short_usdc:
                print(f" USDC non trouvé sur un des exchanges")
                return False
            
            long_available = float(long_usdc.available) if long_usdc.available else 0.0
            short_available = float(short_usdc.available) if short_usdc.available else 0.0
            
            print(f"    {long_exchange.name}: {long_available:.2f} USDC disponible")
            print(f"    {short_exchange.name}: {short_available:.2f} USDC disponible")
            
            # Vérification collatéral suffisant
            if long_available < collateral_needed:
                print(f" Collatéral insuffisant sur {long_exchange.name}: {long_available:.2f} < {collateral_needed:.0f}")
                return False
                
            if short_available < collateral_needed:
                print(f" Collatéral insuffisant sur {short_exchange.name}: {short_available:.2f} < {collateral_needed:.0f}")
                return False
            
            print(f" Pré-vérifications réussies - Collatéral suffisant")
            return True
            
        except Exception as e:
            print(f" Erreur pré-vérifications: {e}")
            return False

    async def close_position(self, position: Dict) -> bool:
        """Ferme une position d'arbitrage avec levier"""
        symbol = position['symbol']
        long_exchange_name = position['long_exchange']
        short_exchange_name = position['short_exchange']
        
        print(f" Fermeture position {symbol} (levier x{self.leverage})")
        
        try:
            long_exchange = self.exchanges[long_exchange_name]
            short_exchange = self.exchanges[short_exchange_name]
            
            # Fermeture simultanée des deux côtés
            close_long_task = asyncio.create_task(
                long_exchange.close_position(symbol)
            )
            close_short_task = asyncio.create_task(
                short_exchange.close_position(symbol)
            )
            
            long_closed, short_closed = await asyncio.gather(
                close_long_task, close_short_task, return_exceptions=True
            )
            
            if long_closed and short_closed:
                print(f" Position {symbol} fermée avec succès")
                await self._update_position_status(position, 'closed')
                return True
            else:
                print(f" Fermeture partielle - Monitoring nécessaire")
                return False
                
        except Exception as e:
            print(f" Erreur fermeture position {symbol}: {e}")
            return False

    async def _rollback_partial_execution(self, long_result, short_result,
                                        long_exchange, short_exchange, symbol: str):
        """Rollback en cas d'exécution partielle"""
        print(" Tentative de rollback...")
        
        try:
            if long_result and long_result.get('success'):
                print(" Fermeture position long (rollback)")
                await long_exchange.close_position(symbol)
            
            if short_result and short_result.get('success'):
                print(" Fermeture position short (rollback)")
                await short_exchange.close_position(symbol)
                
            print(" Rollback terminé")
                
        except Exception as e:
            print(f" Erreur rollback: {e}")
            print(" INTERVENTION MANUELLE REQUISE")

    async def _save_arbitrage_position(self, position_data: Dict):
        """Sauvegarde position pour monitoring"""
        print(f" Position sauvegardée: {position_data['symbol']} (levier x{self.leverage})")
        print(f"   Collatéral: {position_data['collateral_used']:.0f} USDC")
        print(f"   Taille position: {position_data['position_size']:.0f} USDC")
        print(f"   APR effectif: {position_data['leveraged_apr']:.1f}%")

    async def _update_position_status(self, position: Dict, status: str):
        """Met à jour le statut d'une position"""
        print(f" Position {position['symbol']} -> {status}")