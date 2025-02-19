import asyncio

from anchorpy import Wallet
from driftpy.drift_client import DriftClient
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    url = 'https://api.devnet.solana.com'  # replace w/ any rpc
    connection = AsyncClient(url)
    wallet = Wallet(Keypair.from_json(
        '[54,150,182,115,231,14,218,194,93,32,95,124,201,27,186,1,47,80,128,52,65,82,130,94,7,133,74,17,78,159,223,3,164,39,76,242,27,98,175,102,195,101,45,53,66,235,203,156,26,103,56,232,79,87,31,34,252,241,120,75,218,75,224,135]'))
    drift_client = DriftClient(connection, wallet, "devnet")
    tx_sig = await drift_client.initialize_user(sub_account_id=0, name=None)
    print(tx_sig)


# 运行异步函数
asyncio.run(main())
