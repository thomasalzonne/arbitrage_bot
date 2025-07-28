from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class FundingRate:
    """Structure standardisée pour les taux de financement"""
    symbol: str          # Ex: "BTC-PERP"
    exchange: str        # Ex: "woofi_pro"
    rate: float         # Taux funding (-0.01 = -1%)
    next_funding_time: int  # Timestamp prochain funding
    apr: float          # APR extrapolé
    last_updated: int   # Timestamp dernière MAJ

@dataclass
class Position:
    """Structure standardisée pour les positions"""
    symbol: str
    exchange: str
    side: str           # "long" ou "short"
    size: Decimal
    entry_price: Decimal
    unrealized_pnl: Decimal
    funding_received: Decimal

@dataclass
class Balance:
    """Structure standardisée pour les balances"""
    exchange: str
    asset: str          # "USDC", "BTC", etc.
    available: Decimal
    locked: Decimal
    total: Decimal

class BaseExchange(ABC):
    """
    Interface abstraite pour tous les exchanges
    Standardise les méthodes nécessaires pour l'arbitrage
    """
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authentification avec l'exchange"""
        pass
    
    @abstractmethod
    async def get_funding_rates(self, symbols: Optional[List[str]] = None) -> List[FundingRate]:
        """
        Récupère les taux de financement
        
        Args:
            symbols: Liste des symboles (None = tous)
            
        Returns:
            Liste des taux de financement actuels
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Récupère toutes les positions ouvertes"""
        pass
    
    @abstractmethod
    async def get_balances(self) -> List[Balance]:
        """Récupère tous les balances du compte"""
        pass
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, size: Decimal, 
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict:
        """
        Place un ordre
        
        Args:
            symbol: Paire à trader
            side: "buy" ou "sell"
            size: Taille position en USDC
            order_type: "market" ou "limit"
            price: Prix limit (si applicable)
            
        Returns:
            Infos sur l'ordre placé
        """
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> bool:
        """Ferme une position existante"""
        pass
    
    @abstractmethod
    async def get_market_info(self, symbol: str) -> Dict:
        """Infos sur un marché (taille min, tick size, etc.)"""
        pass
    
    # Méthodes utilitaires communes
    async def is_healthy(self) -> bool:
        """Vérifie si la connexion exchange est stable"""
        try:
            await self.get_balances()
            return True
        except:
            return False
    
    def calculate_position_size(self, capital_usdc: Decimal, leverage: int = 1) -> Decimal:
        """Calcule la taille de position optimale"""
        return capital_usdc * leverage
    
    def format_symbol(self, base: str, quote: str = "USDC") -> str:
        """Formate un symbole selon les conventions de l'exchange"""
        # Implémentation par défaut - à override par exchange
        return f"{base}-{quote}"