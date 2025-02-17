import traceback

from apscheduler.schedulers.blocking import BlockingScheduler
from pydantic.schema import datetime
from web3 import Web3


def get_excess_amount(token_contract_address, target_address):
    """通用代币余额查询"""
    try:
        # contract_steth = w3.eth.contract(
        #     address=Web3.to_checksum_address(token_contract_address),
        #     abi=ERC20_ABI
        # )

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


def send_transaction(steth_amount):
    # 构造交易
    tx = contract_lybra.functions.excessIncomeDistribution(
        steth_amount  # 单位：wei
    ).build_transaction({
        'chainId': chainId,
        'from': WALLET_ADDRESS,
        'nonce': nonce,
        'gasPrice': int((w3.eth.gas_price / 10e8 + 1) * 10e8),
        # 'gasPrice': w3.to_wei(int((w3.eth.gas_price / 10e8 + 1) * 10e8), 'gwei'),
        # 'maxPriorityFeePerGas': w3.eth.max_priority_fee,
        'gas': 1000000
        # 'value': Web3.to_wei(0.1, 'ether')  # 如果是payable函数
    })
    # 估算Gas（可选但推荐）
    # tx['gas'] = w3.eth.estimate_gas(tx)
    # 签名交易
    signed_tx = ACCOUNT.sign_transaction(tx)
    # 发送交易
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(datetime.now(), f"Transaction sent: {tx_hash.hex()}")
    if tx_hash:
        # 等待确认
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(datetime.now(), f"Transaction confirmed in block {receipt['blockNumber']}")


# 查询你的合约持有的stETH余额
if __name__ == "__main__":
    # 配置连接（使用Infura）
    # NODE_URL = 'https://eth-mainnet.g.alchemy.com/v2/r8aq919e-3HfTzAPXTYPZxRBLu_kZw-A'
    # NODE_URL = 'https://virtual.mainnet.rpc.tenderly.co/0bd09288-f95c-4d59-9d0c-8172952140f3'
    # NODE_URL = 'https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0'
    # NODE_URL = 'https://rpc.tenderly.co/fork/90dc85bc-f2f6-4816-adab-0e44465ec873'
    NODE_URL = 'https://mainnet.gateway.tenderly.co/7aTTDUXsphVy5fWhOnfor1'
    w3 = Web3(Web3.HTTPProvider(NODE_URL))
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
    # WALLET_ADDRESS = '0x802d78fd3045b64bf2680aaa9a5ae0f4f5241836'  # 要修改的钱包地址
    with open('PRIVATE_MNEMONIC', 'r') as f:
        PRIVATE_MNEMONIC = f.read()
    w3.eth.account.enable_unaudited_hdwallet_features()
    ACCOUNT = w3.eth.account.from_mnemonic(PRIVATE_MNEMONIC)  # .from_key(PRIVATE_KEY)
    WALLET_ADDRESS = ACCOUNT.address
    # approve_eusd(Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), 999)
    decimals_steth = contract_steth.functions.decimals().call()
    nonce = w3.eth.get_transaction_count(ACCOUNT.address)
    chainId = w3.eth.chain_id


    def job():
        print(datetime.now(), '开始')
        while 1:
            try:
                excessAmount = get_excess_amount(STETH_CONTRACT_ADDRESS, LYBRA_CONTRACT_ADDRESS)
                if excessAmount > 30000000000000000:
                    send_transaction(excessAmount)
                    print(datetime.now(), excessAmount, '完成')
                    break
            except:
                traceback.print_exc()
                continue


    scheduler = BlockingScheduler()
    scheduler.add_job(job, 'cron', hour=20, minute=19)
    # 启动调度器
    scheduler.start()
