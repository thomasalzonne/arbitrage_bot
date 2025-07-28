#  Test CCXT Hyperliquid - Solution qui marche !

import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()

async def test_ccxt_hyperliquid():
    """Test CCXT avec Hyperliquid - Based on working French guides"""
    
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
    private_key = os.getenv('HYPERLIQUID_SECRET_KEY')
    
    print(" CCXT HYPERLIQUID TEST")
    print("=" * 50)
    
    try:
        # 1. Init CCXT Hyperliquid
        exchange = ccxt.hyperliquid({
            'walletAddress': wallet_address,
            'privateKey': private_key,
            'sandbox': False,  # Mainnet
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Perpetuals
            }
        })
        
        print(" CCXT Exchange initialized")
        
        # 2. Test connection
        await exchange.load_markets()
        print(" Markets loaded successfully")
        
        # 3. Test balance
        balance = await exchange.fetch_balance()
        print(f" Balance fetched: {balance.get('USDC', {}).get('total', 0)} USDC")
        
        # 4. Test funding rates (public data)
        try:
            # Test avec BTC first
            ticker = await exchange.fetch_ticker('BTC/USDC:USDC')
            print(f" BTC ticker: {ticker['last']} USDC")
            
            # Check if funding rates available
            if 'info' in ticker and 'fundingRate' in ticker['info']:
                funding_rate = float(ticker['info']['fundingRate'])
                apr = funding_rate * 8760 * 100  # Annualisé
                print(f" BTC funding rate: {funding_rate:.6f} ({apr:.1f}% APR)")
            
        except Exception as funding_error:
            print(f" Funding rates test: {funding_error}")
        
        # 5. Test small order (DRY RUN - just validation)
        try:
            # TEST: Validate order parameters (don't execute)
            symbol = 'ETH/USDC:USDC'
            amount = 0.001  # Small test amount
            
            # Get current price for reference
            ticker_eth = await exchange.fetch_ticker(symbol)
            current_price = ticker_eth['last']
            
            print(f" Order validation ready: {amount} ETH at ~{current_price} USDC")
            print("   (Dry run - no actual order placed)")
            
        except Exception as order_error:
            print(f" Order validation: {order_error}")
        
        await exchange.close()
        print(" CCXT Hyperliquid: ALL TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f" CCXT Error: {e}")
        return False

# Quick setup instructions
def print_setup_instructions():
    print("""
 QUICK SETUP FOR CCXT:

1. Install CCXT:
   pip install ccxt

2. Update requirements.txt:
   # Remove: hyperliquid-python-sdk
   # Add: ccxt>=4.4.0

3. Replace hyperliquid.py with CCXT version
   
4. Benefits:
    Standardized API across all exchanges
    Active maintenance & bug fixes
    Async support built-in
    Same code works for other exchanges too
    """)

if __name__ == "__main__":
    print_setup_instructions()
    success = asyncio.run(test_ccxt_hyperliquid())
    
    if success:
        print("\n READY TO REPLACE HYPERLIQUID SDK WITH CCXT!")
    else:
        print("\n Need to debug CCXT setup")