import asyncio
import traceback
from datetime import datetime

import requests
from curl_cffi import requests
from web3 import Web3

eUSD_3CRV_LP_Staking_ABI = [
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "balanceOf",
     "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view",
     "type": "function"},
    {"inputs": [{"internalType": "address", "name": "_account", "type": "address"}], "name": "earned",
     "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view",
     "type": "function"}
]
eUSD_3CRV_LP_Staking_CONTRACT_ADDRESS = '0x19d7cB89E1F92f21d71dB34BeF4944b9f3344d6E'  # ← 你的ERC20合约地址
NODE_URL = 'https://eth-mainnet.g.alchemy.com/v2/r8aq919e-3HfTzAPXTYPZxRBLu_kZw-A'
# NODE_URL = 'https://virtual.mainnet.rpc.tenderly.co/0bd09288-f95c-4d59-9d0c-8172952140f3'
# NODE_URL = 'https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0'
# NODE_URL = 'https://rpc.tenderly.co/fork/90dc85bc-f2f6-4816-adab-0e44465ec873'
# NODE_URL = 'https://mainnet.gateway.tenderly.co/7aTTDUXsphVy5fWhOnfor1'
w3 = Web3(Web3.HTTPProvider(NODE_URL))
contract_eUSD_3CRV_LP_Staking = w3.eth.contract(address=Web3.to_checksum_address(eUSD_3CRV_LP_Staking_CONTRACT_ADDRESS),
                                                abi=eUSD_3CRV_LP_Staking_ABI)
session = requests.Session()
session.headers = {'Content-Type': 'application/json'}


def send_msg(msg):
    try:
        print(datetime.now(), msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
            json=json_msg)
    except:
        return


def get_close():
    current_time = int(datetime.now().timestamp())
    response = requests.get("https://prices.curve.fi/v1/ohlc/ethereum/0x2673099769201c08E9A5e63b25FBaF25541A6557",
                            params={
                                'main_token': "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                'reference_token': "0xdf3ac4F479375802A821f7b7b46Cd7EB5E4262cC",
                                'agg_number': "15",
                                'agg_units': "minute",
                                'start': current_time - 15 * 60,
                                'end': current_time
                            })
    response = requests.post(
        'https://prod.ave-api.com/v2/tokens/price',
        headers={
            'X-API-KEY': 'ufzEUWscHCQLXkncSTe4eIAFyafdZNrnXYK9pfJAuNWSDjFmip50yxN5avvT4Rv4',
        }, json={'token_ids': ['0x97de57ec338ab5d51557da3434828c5dbfada371-eth',
                               '0xdf3ac4f479375802a821f7b7b46cd7eb5e4262cc-eth'], 'tvl_min': 0,
                 'tx_24h_volume_min': 0}
    )
    price_close = response.json()['data'][-1]['close']
    response2 = requests.get("https://prices.curve.fi/v1/ohlc/ethereum/0x880F2fB3704f1875361DE6ee59629c6c6497a5E3",
                             params={
                                 'main_token': "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                 'reference_token': "0x97de57eC338AB5d51557DA3434828C5DbFaDA371",
                                 'agg_number': "15",
                                 'agg_units': "minute",
                                 'start': current_time - 15 * 60,
                                 'end': current_time
                             })
    price_close2 = response2.json()['data'][-1]['close']
    send_msg(f'V2:\n{round(price_close, 2)}\nV1:\n{round(price_close2, 2)}')


def get_user_data():
    earned = contract_eUSD_3CRV_LP_Staking.functions.earned('0x2EC65B1C8Ddd841b025Ee3D134015Ae907ba1A73').call()
    balance = contract_eUSD_3CRV_LP_Staking.functions.balanceOf('0x2EC65B1C8Ddd841b025Ee3D134015Ae907ba1A73').call()
    msg = f"earned:\n{int(earned / 1e18)}esLBR\n-------\nbalance:\n{int(balance / 1e18)}eUSD/3CRV"
    send_msg(msg)


async def main():
    while True:
        try:
            get_user_data()
            get_close()
        except:
            traceback.print_exc()
        await asyncio.sleep(300)


asyncio.run(main())
