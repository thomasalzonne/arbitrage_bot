import asyncio
from hyperliquid.info import Info
from hyperliquid.utils import constants

async def test():
    try:
        # Test direct du SDK
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        
        # Test avec ton wallet
        wallet = "0xd3dcdc7beac2f03f6e1509bafee2a092a6d3be9e"
        user_state = info.user_state(wallet)
        
        print("User state exists:", user_state is not None)
        if user_state:
            print("Account data:", user_state.get('marginSummary', {}))
        else:
            print("No account found - wallet may not be registered on Hyperliquid")
            
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
