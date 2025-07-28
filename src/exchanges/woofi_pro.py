#  src/exchanges/woofi_pro.py - Correctif positions

import asyncio
import time
import json
import base64
import base58
from typing import Dict, List, Optional
from decimal import Decimal
import aiohttp
from dataclasses import asdict

# Import pour Ed25519 (Orderly utilise Ed25519, pas HMAC)
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    print(" Install cryptography: pip install cryptography")

from .base import BaseExchange, FundingRate, Position, Balance

class WooFiProExchange(BaseExchange):
    """
    🟢 Connecteur WooFi Pro (utilise Orderly Network) - VERSION CORRIGÉE
    """
    
    def __init__(self, config: Dict):
        super().__init__("woofi_pro", config)
        self.api_key = config['api_key']
        self.secret_key = config['secret_key']
        self.account_id = config.get('account_id', '')
        self.base_url = config.get('base_url', 'https://api.orderly.org')
        self.session = None
        
        # Orderly Network settings
        self.funding_frequency_hours = 8
        self.funding_times_utc = [0, 8, 16]

    async def authenticate(self) -> bool:
        """Authentification avec Orderly Network"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            endpoint = "/v1/client/holding"
            headers = self._generate_orderly_headers("GET", endpoint)
            
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                if response.status == 200:
                    self.authenticated = True
                    print(f" WooFi Pro (Orderly) authenticated")
                    return True
                else:
                    error_text = await response.text()
                    print(f" WooFi Pro auth failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f" WooFi Pro auth error: {e}")
            return False

    async def get_funding_rates(self, symbols: Optional[List[str]] = None) -> List[FundingRate]:
        """Récupère funding rates via bulk API"""
        if not self.authenticated:
            await self.authenticate()
            
        try:
            print(" WooFi: Début récupération funding rates...")
            
            endpoint = "/v1/public/funding_rates"
            start_time = time.time()
            
            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                if response.status != 200:
                    print(f" Failed to get funding rates: {response.status}")
                    return []
                
                data = await response.json()
                
            api_time = time.time() - start_time
            print(f"   API call time: {api_time:.1f}s")
            
            funding_rates = []
            rows = data.get('data', {}).get('rows', [])
            print(f"   Rows reçues: {len(rows)}")
            
            for item in rows:
                symbol = self._normalize_symbol(item['symbol'])
                
                if symbols and symbol not in symbols:
                    continue
                    
                rate = float(item.get('est_funding_rate', item.get('last_funding_rate', 0)))
                next_funding = int(item['next_funding_time'])
                
                # Calcul APR: 8h → annual (1095 periods) * 100 pour pourcentage
                apr = rate * 1095 * 100
                
                funding_rates.append(FundingRate(
                    symbol=symbol,
                    exchange=self.name,
                    rate=rate,
                    next_funding_time=next_funding,
                    apr=apr,
                    last_updated=int(time.time())
                ))
            
            print(f" WooFi: {len(funding_rates)} funding rates traités!")
            return funding_rates
            
        except Exception as e:
            print(f" Error getting WooFi funding rates: {e}")
            return []

    async def get_positions(self) -> List[Position]:
        """Récupère les positions ouvertes - CORRIGÉ"""
        if not self.authenticated:
            await self.authenticate()
            
        try:
            endpoint = "/v1/positions"
            headers = self._generate_orderly_headers("GET", endpoint)
            
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                positions = []
                
                rows = data.get('data', {}).get('rows', [])
                for pos in rows:
                    if float(pos['position_qty']) != 0:  # Position ouverte
                        
                        #  FIX: Gestion des champs manquants
                        unrealized_pnl = pos.get('unrealized_pnl', pos.get('unsettled_pnl', 0))
                        funding_fee = pos.get('funding_fee', pos.get('settled_pnl', 0))
                        
                        positions.append(Position(
                            symbol=self._normalize_symbol(pos['symbol']),
                            exchange=self.name,
                            side="long" if float(pos['position_qty']) > 0 else "short",
                            size=Decimal(abs(float(pos['position_qty']))),
                            entry_price=Decimal(pos.get('average_open_price', 0)),
                            unrealized_pnl=Decimal(str(unrealized_pnl)),
                            funding_received=Decimal(str(funding_fee))
                        ))
                
                return positions
                
        except Exception as e:
            print(f" Error getting WooFi positions: {e}")
            return []

    async def get_balances(self) -> List[Balance]:
        """Récupère les balances du compte WooFi Pro"""
        if not self.authenticated:
            await self.authenticate()
            
        try:
            endpoint = "/v1/client/holding"
            headers = self._generate_orderly_headers("GET", endpoint)
            
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                balances = []
                
                holding = data.get('data', {}).get('holding', [])
                for item in holding:
                    balances.append(Balance(
                        exchange=self.name,
                        asset=item['token'],
                        available=Decimal(item['holding']),
                        locked=Decimal(item['frozen']),
                        total=Decimal(item['holding']) + Decimal(item['frozen'])
                    ))
                
                return balances
                
        except Exception as e:
            print(f" Error getting WooFi balances: {e}")
            return []

    async def place_order(self, symbol: str, side: str, size: Decimal, 
                     order_type: str = "market", price: Optional[Decimal] = None) -> Dict:
        """Place un ordre sur WooFi Pro - SANS FORCER x1 (levier configuré séparément)"""
        if not self.authenticated:
            await self.authenticate()
            
        try:
            market_info = await self.get_market_info(symbol)
        
            if market_info:
                min_size = market_info.get('min_order_size', 1.0)
                tick_size = market_info.get('tick_size', 0.01)
                
                # Arrondir à la taille minimum
                if float(size) < min_size:
                    print(f" Taille trop petite {size} < {min_size}, ajustement à {min_size}")
                    size = Decimal(str(min_size))
                
                # Arrondir selon tick_size
                rounded_size = round(float(size) / tick_size) * tick_size
                size = Decimal(str(rounded_size))
                
                print(f"📏 Taille ajustée: {size} (min: {min_size}, tick: {tick_size})")

            endpoint = "/v1/order"
            
            order_side = "BUY" if side.lower() in ["buy", "long"] else "SELL"
            
            order_data = {
                "symbol": self._format_symbol_for_api(symbol),
                "client_order_id": f"arb_{int(time.time())}_{symbol.replace('-', '')}",
                "order_type": order_type.upper(),
                "side": order_side,
                "order_quantity": str(size),
                "order_price": str(price) if price else None,
                "leverage": 3 
            }
            
            order_data = {k: v for k, v in order_data.items() if v is not None}
            
            headers = self._generate_orderly_headers("POST", endpoint, json.dumps(order_data))
            
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=order_data
            ) as response:
                result = await response.json()
                if response.status in [200, 201]:
                    print(f" Ordre placé: {side} {size} {symbol}")
                    return {
                        "success": True,
                        "order_id": result.get('data', {}).get('order_id'),
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "status": result.get('data', {}).get('status')
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Order failed: {response.status} - {result}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Order error: {str(e)}"
            }

    async def close_position(self, symbol: str) -> bool:
        """Ferme une position existante sur WooFi Pro"""
        try:
            positions = await self.get_positions()
            target_position = None
            
            for pos in positions:
                if pos.symbol == symbol:
                    target_position = pos
                    break
            
            if not target_position:
                return True  # Déjà fermée
            
            close_side = "sell" if target_position.side == "long" else "buy"
            result = await self.place_order(
                symbol=symbol,
                side=close_side,
                size=target_position.size,
                order_type="market"
            )
            
            return result.get("success", False)
            
        except Exception as e:
            print(f" Error closing position {symbol}: {e}")
            return False

    async def get_market_info(self, symbol: str) -> Dict:
        """Infos sur un marché WooFi Pro"""
        try:
            endpoint = "/v1/public/info"
            
            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                if response.status != 200:
                    return {}
                
                data = await response.json()
                
                rows = data.get('data', {}).get('rows', [])
                for market in rows:
                    if self._normalize_symbol(market['symbol']) == symbol:
                        return {
                            "symbol": symbol,
                            "min_order_size": float(market['base_min']),
                            "tick_size": float(market['quote_tick']),
                            "max_leverage": float(market.get('max_leverage', 5)),
                            "funding_frequency": self.funding_frequency_hours
                        }
                
                return {}
                
        except Exception as e:
            print(f" Error getting market info for {symbol}: {e}")
            return {}

    def _generate_orderly_headers(self, method: str, endpoint: str, body: str = "") -> Dict[str, str]:
        """Génère les headers d'authentification Ed25519"""
        timestamp = int(time.time() * 1000)
        account_id = self.account_id
        signature_string = f"{timestamp}{method.upper()}{endpoint}{body}"
        
        try:
            private_key_bytes = base58.b58decode(self.secret_key)[:32]
            private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            data_bytes = signature_string.encode('utf-8')
            signature_bytes = private_key.sign(data_bytes)
            signature = base64.b64encode(signature_bytes).decode('utf-8')
            
        except Exception as e:
            print(f" Error generating signature: {e}")
            signature = ""
        
        return {
            "Content-Type": "application/json",
            "orderly-timestamp": str(timestamp),
            "orderly-account-id": account_id,
            "orderly-key": self.api_key,
            "orderly-signature": signature
        }

    def _normalize_symbol(self, api_symbol: str) -> str:
        """Normalise symbole API vers format standard"""
        if api_symbol.startswith('PERP_'):
            parts = api_symbol.split('_')
            if len(parts) >= 3:
                base = parts[1]
                return f"{base}-PERP"
        return api_symbol.replace("_", "-")
    
    def _format_symbol_for_api(self, symbol: str) -> str:
        """Formate symbole standard vers format API"""
        if symbol.endswith('-PERP'):
            base = symbol.replace('-PERP', '')
            return f"PERP_{base}_USDC"
        return symbol.replace("-", "_")

    async def close(self):
        """Ferme la session HTTP"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Configure le levier pour un symbole sur WooFi Pro (Orderly)"""
        try:
            if not self.authenticated:
                await self.authenticate()
                
            endpoint = "/v1/client/leverage"
            
            # WooFi Pro (Orderly) supporte jusqu'à 50x
            max_leverage = 5
            safe_leverage = min(leverage, max_leverage)
            
            leverage_data = {
                "symbol": self._format_symbol_for_api(symbol),
                "leverage": safe_leverage
            }
            
            headers = self._generate_orderly_headers("POST", endpoint, json.dumps(leverage_data))
            
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=leverage_data
            ) as response:
                
                if response.status in [200, 201]:
                    print(f" Levier x{safe_leverage} configuré pour {symbol} sur WooFi Pro")
                    return True
                else:
                    result = await response.json()
                    print(f" Échec config levier {symbol}: {result}")
                    return False
                    
        except Exception as e:
            print(f" Erreur configuration levier {symbol}: {e}")
            return False