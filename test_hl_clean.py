import asyncio
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HLExchange
from hyperliquid.utils import constants
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
    secret_key = os.getenv('HYPERLIQUID_SECRET_KEY')
    
    print(f"Testing with wallet: {wallet_address}")
    
    info_client = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange_client = HLExchange(info_client, secret_key)
    
    user_state = info_client.user_state(wallet_address)
    print("Success:", user_state is not None)
    
asyncio.run(test())
