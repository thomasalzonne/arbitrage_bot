# src/exchanges/hyperliquid.py - VERSION CORRIGÉE gestion sessions + erreurs

import asyncio
import time
from typing import Dict, List, Optional
from decimal import Decimal
import ccxt.async_support as ccxt
from .base import BaseExchange, FundingRate, Position, Balance

class HyperliquidExchange(BaseExchange):
    """
    Connecteur Hyperliquid via CCXT - SESSIONS CORRIGÉES
    """
    
    def __init__(self, config: Dict):
        super().__init__("hyperliquid", config)
        self.wallet_address = config['wallet_address']
        self.secret_key = config['secret_key']
        self.base_url = config.get('base_url', 'https://api.hyperliquid.xyz')
        
        # CCXT Exchange instance
        self.exchange = None
        self._connection_healthy = False
        
        # Hyperliquid settings
        self.funding_frequency_hours = 1  # Toutes les heures

    async def authenticate(self) -> bool:
        """Authentification via CCXT avec gestion d'erreurs améliorée"""
        try:
            # Fermer ancienne connexion si existe
            await self._ensure_closed()
            
            # Init CCXT Hyperliquid
            self.exchange = ccxt.hyperliquid({
                'walletAddress': self.wallet_address,
                'privateKey': self.secret_key,
                'sandbox': False,
                'enableRateLimit': True,
                'timeout': 30000,  # 30s timeout
                'options': {
                    'defaultType': 'swap',
                }
            })
            
            # Test connection avec retry
            for attempt in range(3):
                try:
                    await self.exchange.load_markets()
                    balance = await self.exchange.fetch_balance()
                    
                    self.authenticated = True
                    self._connection_healthy = True
                    print(f"Hyperliquid CCXT - Wallet: {self.wallet_address[:10]}...")
                    print(f"   Balance: {balance.get('USDC', {}).get('total', 0)} USDC")
                    return True
                    
                except Exception as retry_error:
                    print(f"Tentative {attempt + 1}/3 échouée: {retry_error}")
                    if attempt == 2:  # Dernière tentative
                        raise retry_error
                    await asyncio.sleep(2)  # Pause avant retry
            
            return False
            
        except Exception as e:
            print(f"Hyperliquid CCXT auth error: {e}")
            await self._ensure_closed()
            return False

    async def get_funding_rates(self, symbols: Optional[List[str]] = None) -> List[FundingRate]:
        """Récupère funding rates avec gestion d'erreurs robuste"""
        if not await self._ensure_connection():
            return []
            
        try:
            print("Hyperliquid: Récupération funding rates...")
            
            # Méthode bulk avec fallback
            try:
                all_funding_rates = await self.exchange.fetch_funding_rates()
                print(f"   Bulk funding rates: {len(all_funding_rates)}")
                
                funding_rates = []
                current_time = int(time.time())
                next_hour = (current_time // 3600 + 1) * 3600
                
                for symbol, funding_data in all_funding_rates.items():
                    if ':USDC' not in symbol:
                        continue
                    
                    normalized_symbol = self._normalize_symbol(symbol)
                    
                    if symbols and normalized_symbol not in symbols:
                        continue
                    
                    rate = float(funding_data.get('fundingRate', 0))
                    
                    # Calcul APR: hourly → annual (8760 hours)
                    apr = rate * 8760
                    
                    funding_rates.append(FundingRate(
                        symbol=normalized_symbol,
                        exchange=self.name,
                        rate=rate,
                        next_funding_time=next_hour,
                        apr=apr,
                        last_updated=current_time
                    ))
                
                print(f"Hyperliquid: {len(funding_rates)} funding rates!")
                return funding_rates
                
            except Exception as bulk_error:
                print(f"   Bulk method failed: {bulk_error}")
                return []  # Skip fallback pour éviter surcharge
            
        except Exception as e:
            print(f"Error getting Hyperliquid funding rates: {e}")
            self._connection_healthy = False
            return []

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalise symbole Hyperliquid vers format standard"""
        # GMX/USDC:USDC → GMX-PERP
        if '/USDC:USDC' in symbol:
            base = symbol.split('/')[0]
            return f"{base}-PERP"
        return symbol

    async def get_positions(self) -> List[Position]:
        """Récupère positions avec gestion d'erreurs"""
        if not await self._ensure_connection():
            return []
            
        try:
            positions_data = await self.exchange.fetch_positions()
            positions = []
            
            for pos in positions_data:
                if float(pos['contracts']) != 0:  # Position ouverte
                    positions.append(Position(
                        symbol=self._normalize_symbol(pos['symbol']),
                        exchange=self.name,
                        side="long" if float(pos['contracts']) > 0 else "short",
                        size=Decimal(abs(float(pos['contracts']))),
                        entry_price=Decimal(pos['entryPrice'] or 0),
                        unrealized_pnl=Decimal(pos['unrealizedPnl'] or 0),
                        funding_received=Decimal(pos.get('info', {}).get('cumFunding', 0))
                    ))
            
            return positions
            
        except Exception as e:
            print(f"Error getting Hyperliquid positions: {e}")
            self._connection_healthy = False
            return []

    async def get_balances(self) -> List[Balance]:
        """Récupère balances avec validation des types"""
        if not await self._ensure_connection():
            return []
            
        try:
            balance_data = await self.exchange.fetch_balance()
            balances = []
            
            for asset, data in balance_data.items():
                # Skip les clés meta de CCXT
                if asset in ['free', 'used', 'total', 'info']:
                    continue
                    
                # Validation du type de données
                if isinstance(data, dict):
                    # Format CCXT standard : {'free': X, 'used': Y, 'total': Z}
                    free_amount = data.get('free', 0)
                    used_amount = data.get('used', 0) 
                    total_amount = data.get('total', 0)
                elif isinstance(data, (int, float)):
                    # Format simplifié : juste un nombre
                    total_amount = data
                    free_amount = data
                    used_amount = 0
                else:
                    # Skip types inconnus
                    continue
                
                # Ne garde que les balances non-nulles
                if total_amount > 0:
                    balances.append(Balance(
                        exchange=self.name,
                        asset=asset,
                        available=Decimal(str(free_amount)),
                        locked=Decimal(str(used_amount)),
                        total=Decimal(str(total_amount))
                    ))
            
            return balances
            
        except Exception as e:
            print(f"Error getting Hyperliquid balances: {e}")
            self._connection_healthy = False
            return []

    async def place_order(self, symbol: str, side: str, size: Decimal, 
                     order_type: str = "market", price: Optional[Decimal] = None) -> Dict:
        """Place un ordre avec gestion d'erreurs robuste"""
        if not await self._ensure_connection():
            return {"success": False, "error": "Connexion indisponible"}
            
        try:
            # Convert normalized symbol back to CCXT format
            ccxt_symbol = self._denormalize_symbol(symbol)

            # Get current price for market orders
            if not price or order_type.lower() == "market":
                ticker = await self.exchange.fetch_ticker(ccxt_symbol)
                current_price = ticker['last']
                
                # Add slippage for market orders
                slippage = 0.002  # 0.2%
                if side.lower() in ["buy", "long"]:
                    price = current_price * (1 + slippage)
                else:
                    price = current_price * (1 - slippage)
            
            # Place order via CCXT
            order = await self.exchange.create_order(
                symbol=ccxt_symbol,
                type=order_type,
                side=side,
                amount=float(size),
                price=float(price) if price else None
            )
            
            print(f"Ordre placé: {side} {size} {symbol}")
            
            return {
                "success": True,
                "order_id": order['id'],
                "symbol": symbol,
                "side": side,
                "size": size,
                "price": price,
                "status": order.get('status', 'unknown')
            }
                
        except Exception as e:
            print(f"Erreur placement ordre {symbol}: {e}")
            self._connection_healthy = False
            return {
                "success": False,
                "error": f"Order error: {str(e)}"
            }

    def _denormalize_symbol(self, normalized_symbol: str) -> str:
        """Convertit symbole normalisé vers format CCXT"""
        # BTC-PERP → BTC/USDC:USDC
        if normalized_symbol.endswith('-PERP'):
            base = normalized_symbol.replace('-PERP', '')
            return f"{base}/USDC:USDC"
        return normalized_symbol

    async def close_position(self, symbol: str) -> bool:
        """Ferme une position via CCXT"""
        if not await self._ensure_connection():
            return False
            
        try:
            # Get current position
            positions = await self.get_positions()
            target_position = None
            
            for pos in positions:
                if pos.symbol == symbol:
                    target_position = pos
                    break
            
            if not target_position:
                return True  # Already closed
            
            # Close via market order (opposite side)
            close_side = "sell" if target_position.side == "long" else "buy"
            result = await self.place_order(
                symbol=symbol,
                side=close_side,
                size=target_position.size,
                order_type="market"
            )
            
            return result.get("success", False)
            
        except Exception as e:
            print(f"Error closing position {symbol}: {e}")
            return False

    async def get_market_info(self, symbol: str) -> Dict:
        """Infos marché via CCXT"""
        if not await self._ensure_connection():
            return {}
            
        try:
            ccxt_symbol = self._denormalize_symbol(symbol)
            market = self.exchange.market(ccxt_symbol)
            return {
                "symbol": symbol,
                "min_order_size": market.get('limits', {}).get('amount', {}).get('min', 0.001),
                "tick_size": market.get('precision', {}).get('price', 0.01),
                "max_leverage": market.get('info', {}).get('maxLeverage', 20),
                "funding_frequency": self.funding_frequency_hours
            }
            
        except Exception as e:
            print(f"Error getting market info for {symbol}: {e}")
            return {}

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Configure le levier pour un symbole sur Hyperliquid"""
        if not await self._ensure_connection():
            return False
            
        try:
            ccxt_symbol = self._denormalize_symbol(symbol)
            
            # Hyperliquid supporte jusqu'à 50x levier
            max_leverage = 5
            safe_leverage = min(leverage, max_leverage)
            
            # Configuration via CCXT
            await self.exchange.set_leverage(safe_leverage, ccxt_symbol)
            
            print(f"Levier x{safe_leverage} configuré pour {symbol} sur Hyperliquid")
            return True
            
        except Exception as e:
            print(f"Erreur configuration levier {symbol}: {e}")
            return False

    async def _ensure_connection(self) -> bool:
        """Assure que la connexion est saine"""
        if not self.exchange or not self._connection_healthy:
            print("Reconnexion Hyperliquid nécessaire...")
            return await self.authenticate()
        return True

    async def _ensure_closed(self):
        """Ferme proprement la connexion existante"""
        try:
            if self.exchange:
                await self.exchange.close()
                self.exchange = None
                self._connection_healthy = False
        except Exception as e:
            # Ignore les erreurs de fermeture
            pass
        finally:
            self.exchange = None
            self._connection_healthy = False

    async def close(self):
        """Ferme la connexion CCXT - CORRIGÉ"""
        await self._ensure_closed()
        print("Hyperliquid CCXT session fermée proprement")