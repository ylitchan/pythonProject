import traceback
from datetime import datetime
from threading import Thread

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from web3 import Web3

session = requests.Session()
session.headers = {'Content-Type': 'application/json'}


def send_msg(msg):
    try:
        print(msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)
    except:
        return


def get_excess_amount(target_address):
    """通用代币余额查询"""
    try:
        # 获取代币精度
        # decimals = contract_steth.functions.decimals().call()
        # 查询余额
        balance = contract_steth.functions.balanceOf(
            Web3.to_checksum_address(target_address)
        ).call()
        # Decimal(balance) / Decimal(10 ** decimals)
        return balance - contract_lybra.functions.totalDepositedAsset().call()

    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def approve_eusd(spender_address, amount_eusd):
    decimals = contract_eusd.functions.decimals().call()
    # 构造交易
    nonce = w3.eth.get_transaction_count(ACCOUNT.address)
    gas_limit = int(contract_eusd.functions.approve(spender_address, amount_eusd * decimals).estimate_gas(
        {'from': Web3.to_checksum_address(ACCOUNT.address)}) * 1.2)  # 预估 Gas（可调整）
    tx = contract_eusd.functions.approve(
        spender_address,
        max(amount_eusd * decimals, 115792089237316195423570985008687907853269984665640564039457584007913129639935)
    ).build_transaction({
        'chainId': w3.eth.chain_id,  # 主网
        'gas': gas_limit,
        'gasPrice': w3.to_wei('2', 'gwei'),  # 根据网络情况调整
        'nonce': nonce,
    })
    # 签名交易
    signed_tx = ACCOUNT.sign_transaction(tx)
    # 发送交易
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"交易哈希: {tx_hash.hex()}")
    if tx_hash:
        # 等待确认
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Approve confirmed in block {receipt['blockNumber']}")
    allowance = contract_eusd.functions.allowance(
        ACCOUNT.address,
        spender_address
    ).call()
    print(f"已授权额度: {allowance / decimals} EUSD")


def send_transaction(steth_amount, nonce, gas_price):
    # 构造交易
    tx = contract_lybra.functions.excessIncomeDistribution(
        steth_amount  # 单位：wei
    ).build_transaction({
        'chainId': chainId,
        'from': WALLET_ADDRESS,
        'nonce': nonce,
        # 'gasPrice': gas_price,
        'maxFeePerGas': gas_price,
        'maxPriorityFeePerGas': gas_price,
        'gas': 2000000
        # 'value': Web3.to_wei(0.1, 'ether')  # 如果是payable函数
    })
    # 估算Gas（可选但推荐）
    # tx['gas'] = w3.eth.estimate_gas(tx)
    # 签名交易
    signed_tx = ACCOUNT.sign_transaction(tx)
    # 构造 Flashbots Bundle
    # target_block = w3.eth.block_number + 1  # 目标为下一个区块
    # bundle = {
    #     "jsonrpc": "2.0",
    #     "id": 1,
    #     "method": "eth_sendBundle",
    #     "params": [{
    #         "txs": [signed_tx.rawTransaction.hex()],  # 签名后的交易列表
    #         "blockNumber": hex(target_block),  # 目标区块号（十六进制）
    #         # 可选参数
    #         "minTimestamp": 0,  # 最早执行时间戳
    #         "maxTimestamp": int(w3.eth.get_block('latest')['timestamp']) + 24  # 最晚执行时间戳（10分钟后）
    #     }]
    # }
    # bundle = {
    #     "jsonrpc": "2.0",
    #     "id": 1,
    #     "method": "flashbots_getUserStats",
    #     "params": [
    #         hex(target_block),
    #     ]
    # }
    # 发送 Bundle 到 Flashbots Relay
    # message = messages.encode_defunct(text=Web3.keccak(text=json.dumps(bundle)).hex())
    # signature = WALLET_ADDRESS + ':' + ACCOUNT.sign_message(message).signature.hex()
    # headers = {
    #     "Content-Type": "application/json",
    #     "X-Flashbots-Signature": signature
    # }
    # response = requests.post(relay_url, json=bundle, headers=headers)
    # # 检查响应
    # if response.status_code == 200:
    #     print("Bundle 发送成功:", response.json())
    #     send_msg(f"Bundle sent:{response.json()['result']['bundleHash']}")
    # else:
    #     print("Bundle 发送失败:", response.status_code, response.text)
    # 发送交易
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(datetime.now(), f"Transaction sent: {tx_hash.hex()}", gas_price)
    send_msg(f"Transaction sent: {tx_hash.hex()}")
    if tx_hash:
        # 等待确认
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(datetime.now(), f"Transaction confirmed in block {receipt['blockNumber']}")


# 查询你的合约持有的stETH余额
if __name__ == "__main__":
    relay_url = "https://relay.flashbots.net"
    # 配置连接（使用Infura）
    NODE_URL = 'https://eth-mainnet.g.alchemy.com/v2/r8aq919e-3HfTzAPXTYPZxRBLu_kZw-A'
    # NODE_URL = 'https://virtual.mainnet.rpc.tenderly.co/0bd09288-f95c-4d59-9d0c-8172952140f3'
    # NODE_URL = 'https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0'
    # NODE_URL = 'https://rpc.tenderly.co/fork/1ee0c23c-78d2-4126-9b2b-6267485ab8df'
    # NODE_URL = 'https://mainnet.gateway.tenderly.co/7aTTDUXsphVy5fWhOnfor1'
    w3 = Web3(Web3.HTTPProvider(NODE_URL))
    w3.eth.account.enable_unaudited_hdwallet_features()
    # WALLET_ADDRESS = '0x802d78fd3045b64bf2680aaa9a5ae0f4f5241836'  # 要修改的钱包地址
    with open('PRIVATE_MNEMONIC', 'r') as f:
        PRIVATE_MNEMONIC = f.read()
    ACCOUNT = w3.eth.account.from_mnemonic(PRIVATE_MNEMONIC)  # .from_key(PRIVATE_KEY)
    WALLET_ADDRESS = ACCOUNT.address
    # 合约地址配置
    LYBRA_CONTRACT_ADDRESS = '0xa980d4c0C2E48d305b582AA439a3575e3de06f0E'  # ← 你的ERC20合约地址
    STETH_CONTRACT_ADDRESS = '0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84'  # stETH官方合约
    EUSD_CONTRACT_ADDRESS = '0xdf3ac4F479375802A821f7b7b46Cd7EB5E4262cC'
    LYBRA_ABI = [
        {"type": "function", "name": "excessIncomeDistribution", "constant": False, "anonymous": False,
         "stateMutability": "nonpayable", "inputs": [
            {"name": "stETHAmount", "type": "uint256", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "uint"}}], "outputs": []},
        {"type": "function", "name": "totalDepositedAsset", "constant": False, "anonymous": False,
         "stateMutability": "view", "inputs": [], "outputs": [
            {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "uint"}}]}]
    contract_lybra = w3.eth.contract(address=Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), abi=LYBRA_ABI)
    # stETH的ERC20 ABI（精简版）
    STETH_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        }
    ]
    contract_steth = w3.eth.contract(
        address=Web3.to_checksum_address(STETH_CONTRACT_ADDRESS),
        abi=STETH_ABI
    )
    EUSD_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {"type": "function", "name": "allowance", "constant": False, "anonymous": False, "stateMutability": "view",
         "inputs": [{"name": "_owner", "type": "address", "storage_location": "default", "offset": 0,
                     "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                     "simple_type": {"type": "address"}},
                    {"name": "_spender", "type": "address", "storage_location": "default", "offset": 0,
                     "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
                     "simple_type": {"type": "address"}}], "outputs": [
            {"name": "", "type": "uint256", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "uint"}}]},
        {"type": "function", "name": "decimals", "constant": False, "anonymous": False,
         "stateMutability": "pure", "inputs": [], "outputs": [
            {"name": "", "type": "uint8", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "uint"}}]},
        {"type": "function", "name": "approve", "constant": False, "anonymous": False,
         "stateMutability": "nonpayable", "inputs": [
            {"name": "_spender", "type": "address", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "address"}},
            {"name": "_amount", "type": "uint256", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "uint"}}], "outputs": [
            {"name": "", "type": "bool", "storage_location": "default", "offset": 0,
             "index": "0x0000000000000000000000000000000000000000000000000000000000000000", "indexed": False,
             "simple_type": {"type": "bool"}}]}]
    contract_eusd = w3.eth.contract(
        address=Web3.to_checksum_address(EUSD_CONTRACT_ADDRESS),
        abi=EUSD_ABI
    )
    # approve_eusd(Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), 999)
    decimals_steth = contract_steth.functions.decimals().call()
    chainId = w3.eth.chain_id
    print('准备完成')
    send_msg('excessIncomeDistribution准备完成')


    def job():
        nonce = w3.eth.get_transaction_count(ACCOUNT.address)
        # print(datetime.now(), '开始', nonce)
        send_msg('excessIncomeDistribution开始')

        def job2():
            print('监听线程开始', nonce)
            while datetime.now().minute <= 30:
                try:
                    for tx in w3.eth.filter('pending').get_new_entries():
                        try:
                            tx = w3.eth.get_transaction(tx)
                            print(datetime.now(), '找到交易', tx)
                        except:
                            traceback.print_exc()
                            print(datetime.now(), '没找到交易，继续读取', tx)
                            continue
                        if tx['from'] != WALLET_ADDRESS and '0x6bef22ee' in tx['input']:
                            gas_price = tx['gasPrice'] + int(w3.eth.gas_price * 0.1)
                            send_transaction(int(tx['input'][11:], 16), nonce, gas_price)
                            print(datetime.now(), 'gas修改抢跑', gas_price, tx)
                            send_msg(f'gas修改抢跑{tx}')
                            break
                except:
                    continue

        t = Thread(target=job2)
        # t.start()
        while datetime.now().minute <= 59:
            try:
                excessAmount = get_excess_amount(LYBRA_CONTRACT_ADDRESS) - 11
                print(datetime.now(), excessAmount)
                if excessAmount >= 30000000000000000:
                    send_transaction(excessAmount, nonce, int((w3.eth.get_block('latest')[
                                                                   'baseFeePerGas'] + w3.eth.max_priority_fee * 10e2) * 1.3))
                    print(datetime.now(), excessAmount, '完成')
                    break
            except:
                traceback.print_exc()
                continue
        # t.join()


    # job()
    scheduler = BlockingScheduler()
    scheduler.add_job(job, 'cron', hour=4, minute=00)
    # 启动调度器
    scheduler.start()
