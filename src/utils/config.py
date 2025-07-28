#  src/utils/config.py - Gestionnaire de configuration

import os
import json
from typing import Dict
from dotenv import load_dotenv

class ConfigManager:
    """
     Gestionnaire de configuration centralisé
    
    Features:
    - Chargement .env
    - Validation des clés API
    - Configuration exchanges
    - Paramètres de trading
    """
    
    def __init__(self, env_file: str = ".env"):
        load_dotenv(env_file)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Charge la configuration complète"""
        return {
            'database': {
                'url': os.getenv('DATABASE_URL'),
                'redis_url': os.getenv('REDIS_URL')
            },
            'exchanges': {
                'woofi_pro': {
                    'api_key': os.getenv('WOOFI_API_KEY'),
                    'secret_key': os.getenv('WOOFI_SECRET_KEY'),
                    'account_id': os.getenv('WOOFI_ACCOUNT_ID'),  # ← Ajoute cette ligne
                    'base_url': os.getenv('WOOFI_BASE_URL', 'https://api.orderly.org')
                },
                'hyperliquid': {
                    'wallet_address': os.getenv('HYPERLIQUID_WALLET_ADDRESS'),
                    'secret_key': os.getenv('HYPERLIQUID_SECRET_KEY'),
                    'base_url': os.getenv('HYPERLIQUID_BASE_URL', 'https://api.hyperliquid.xyz')
                }
            },
            'trading': {
                'min_entry_apr': float(os.getenv('MIN_ENTRY_APR', 80)),
                'exit_apr_threshold': float(os.getenv('EXIT_APR_THRESHOLD', 50)),
                'stop_loss_apr': float(os.getenv('STOP_LOSS_APR', -5)),
                'max_position_size_usdc': float(os.getenv('MAX_POSITION_SIZE_USDC', 10000)),
                'max_capital_per_opportunity_percent': float(os.getenv('MAX_CAPITAL_PER_OPPORTUNITY_PERCENT', 20)),
                'daily_loss_limit_usdc': float(os.getenv('DAILY_LOSS_LIMIT_USDC', 500)),
                'max_open_positions': int(os.getenv('MAX_OPEN_POSITIONS', 5)),
                'position_check_interval_seconds': int(os.getenv('POSITION_CHECK_INTERVAL_SECONDS', 1800))
            },
            'data_collection': {
                'funding_data_refresh_seconds': int(os.getenv('FUNDING_DATA_REFRESH_SECONDS', 300)),
                'ghz_scraping_url': os.getenv('GHZ_SCRAPING_URL', 'https://ghzperpdextools.vercel.app/funding-arbitrage.html')
            },
            'monitoring': {
                'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID'),
                'log_level': os.getenv('LOG_LEVEL', 'INFO')
            }
        }
    
    def get_exchange_config(self, exchange_name: str) -> Dict:
        """Récupère la config d'un exchange spécifique"""
        return self.config.get('exchanges', {}).get(exchange_name, {})
    
    def get_trading_config(self) -> Dict:
        """Récupère la config de trading"""
        return self.config.get('trading', {})
    
    def validate_config(self) -> bool:
        """Valide que la configuration est complète"""
        required_keys = [
            'exchanges.woofi_pro.api_key',
            'exchanges.woofi_pro.secret_key',
            'exchanges.hyperliquid.wallet_address',
            'exchanges.hyperliquid.secret_key'
        ]
        
        for key_path in required_keys:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                value = value.get(key)
                if value is None:
                    print(f" Configuration manquante: {key_path}")
                    return False
        
        print(" Configuration validée")
        return True