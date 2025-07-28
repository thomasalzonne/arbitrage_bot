import asyncio
from src.exchanges.woofi_pro import WooFiProExchange
from src.exchanges.hyperliquid import HyperliquidExchange
from src.utils.config import ConfigManager

async def test_both():
    config = ConfigManager()
    
    # Test WooFi Pro
    print('=== Testing WooFi Pro ===')
    woofi_config = config.get_exchange_config('woofi_pro')
    woofi = WooFiProExchange(woofi_config)
    woofi_auth = await woofi.authenticate()
    print('WooFi auth:', woofi_auth)
    
    if woofi_auth:
        woofi_rates = await woofi.get_funding_rates(['BTC-PERP', 'ETH-PERP'])
        print(f'WooFi rates: {len(woofi_rates)}')
        for rate in woofi_rates[:2]:
            print(f'  {rate.symbol}: {rate.apr:.1f}% APR')
    
    print()
    
    # Test Hyperliquid
    print('=== Testing Hyperliquid ===')
    hl_config = config.get_exchange_config('hyperliquid')
    hl = HyperliquidExchange(hl_config)
    hl_auth = await hl.authenticate()
    print('Hyperliquid auth:', hl_auth)
    
    if hl_auth:
        hl_rates = await hl.get_funding_rates(['BTC-PERP', 'ETH-PERP'])
        print(f'Hyperliquid rates: {len(hl_rates)}')
        for rate in hl_rates[:2]:
            print(f'  {rate.symbol}: {rate.apr:.1f}% APR')
    
    print()
    
    if woofi_auth and hl_auth:
        print('SUCCESS: Both exchanges connected!')
        print('Ready to launch the arbitrage bot!')
    
asyncio.run(test_both())
