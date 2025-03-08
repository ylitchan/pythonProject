import asyncio
import traceback

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic.schema import datetime
from web3 import Web3

address_borrowed = []
LYBRA_ABI = [
    {"type": "function", "name": "getAssetPrice", "constant": False, "anonymous": False,
     "stateMutability": "nonpayable", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
]
LIQUITY_ABI = [
    {"type": "function", "name": "getTroveStatus", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getCurrentICR", "constant": False, "anonymous": False, "stateMutability": "view",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}},
                {"name": "_price", "type": "uint256", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "uint"}}], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "liquidate", "constant": False, "anonymous": False, "stateMutability": "nonpayable",
     "inputs": [{"name": "_borrower", "type": "address", "storage_location": "default", "offset": 0,
                 "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                 "simple_type": {"type": "address"}}], "outputs": []},
    {"type": "function", "name": "MINUTE_DECAY_FACTOR", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [], "outputs": [
        {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}]},
    {"type": "function", "name": "getTroveFromTroveOwnersArray", "constant": False, "anonymous": False,
     "stateMutability": "view", "inputs": [
        {"name": "_index", "type": "uint256", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "uint"}}], "outputs": [
        {"name": "", "type": "address", "storage_location": "default", "offset": 0,
         "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
         "simple_type": {"type": "address"}}]},
]
LYBRA_CONTRACT_ADDRESS = '0xa980d4c0C2E48d305b582AA439a3575e3de06f0E'  # ← 你的ERC20合约地址
LIQUITY_CONTRACT_ADDRESS = '0xA39739EF8b0231DbFA0DcdA07d7e29faAbCf4bb2'
NODE_URL = 'https://eth-mainnet.g.alchemy.com/v2/r8aq919e-3HfTzAPXTYPZxRBLu_kZw-A'
# NODE_URL = 'https://virtual.mainnet.rpc.tenderly.co/0bd09288-f95c-4d59-9d0c-8172952140f3'
# NODE_URL = 'https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0'
# NODE_URL = 'https://rpc.tenderly.co/fork/90dc85bc-f2f6-4816-adab-0e44465ec873'
# NODE_URL = 'https://mainnet.gateway.tenderly.co/7aTTDUXsphVy5fWhOnfor1'
w3 = Web3(Web3.HTTPProvider(NODE_URL))
w3.eth.account.enable_unaudited_hdwallet_features()
chainId = w3.eth.chain_id
with open('PRIVATE_MNEMONIC', 'r') as f:
    PRIVATE_MNEMONIC = f.read()
ACCOUNT = w3.eth.account.from_mnemonic(PRIVATE_MNEMONIC)  # .from_key(PRIVATE_KEY)
WALLET_ADDRESS = ACCOUNT.address
contract_lybra = w3.eth.contract(address=Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), abi=LYBRA_ABI)
contract_liquity = w3.eth.contract(address=Web3.to_checksum_address(LIQUITY_CONTRACT_ADDRESS), abi=LIQUITY_ABI)
badCollateralRatio = 110000000000000000000
session = requests.Session()
session.headers = {'Content-Type': 'application/json'}
for i in range(209):
    address_borrowed.append(contract_liquity.functions.getTroveFromTroveOwnersArray(i).call())
print(address_borrowed)


def send_msg(msg):
    try:
        print(msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
            json=json_msg)
    except:
        return


async def provider():
    print(datetime.now(), '开始扫描')
    target_address_set = set()

    async def onBehalfOfAddress(target_address):
        try:
            status = await asyncio.to_thread(contract_liquity.functions.getTroveStatus(target_address).call)
            if not status:
                return
            icr = await asyncio.to_thread(contract_liquity.functions.getCurrentICR(target_address, assetPrice).call)
            print(target_address, icr / 10e17)
            if icr >= badCollateralRatio:
                return
            target_address_set.add(target_address)
            send_msg(f'liquity V1清算地址:{target_address}')
        except:
            return

    def keeper(target_address):
        try:
            tx = contract_liquity.functions.liquidate(target_address)
            tx = tx.build_transaction({
                'chainId': chainId,  # 主网
                'gas': 1000000,
                'gasPrice': int(w3.eth.gas_price * 1.3),  # 根据网络情况调整
                'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            })
            # 签名交易
            signed_tx = ACCOUNT.sign_transaction(tx)
            # 发送交易
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"V1交易哈希: {tx_hash.hex()}")
            send_msg(f"V1清算哈希: {tx_hash.hex()}")
            if tx_hash:
                # 等待确认
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"Approve confirmed in block {receipt['blockNumber']}")
        except:
            traceback.print_exc()

    # address_borrowed = ['0x7E6601A0Cb2B5aE129c09661846a053ea07223Fb']
    while 1:
        try:
            assetPrice = contract_lybra.functions.getAssetPrice().call()
            overallCollateralRatio = contract_liquity.functions.getTCR(assetPrice)
            if overallCollateralRatio < badCollateralRatio:
                superLiquidation = True
            else:
                superLiquidation = False
            break
        except:
            await asyncio.sleep(300)
            continue
    await asyncio.gather(*[onBehalfOfAddress(target_address) for target_address in address_borrowed])
    for a in target_address_set:
        keeper(a)
        break


async def main():
    await provider()
    # 设置任务调度
    scheduler.add_job(provider, 'cron', hour='*', minute='*/59', second='00', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler.start()
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    asyncio.run(main())
