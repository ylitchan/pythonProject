import asyncio
import json

from anchorpy import Program, Provider, Wallet, Idl
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

# 连接 Solana 主网节点
client = Client("https://api.mainnet-beta.solana.com")
client = Client('https://api.devnet.solana.com')
client = Client('https://api.testnet.solana.com')
# 查询账户余额
balance = client.get_balance(Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ")).value
print(balance)


async def main():
    # 步骤 1: 连接 RPC
    rpc_url = "https://api.devnet.solana.com"
    conn = AsyncClient(rpc_url)
    provider = Provider(conn, Wallet(Keypair()))  # 需要签名者（发送交易的账户）
    # 获取最新区块哈希
    latest_blockhash = (await conn.get_latest_blockhash()).value.blockhash
    sender_keypair = Keypair()
    sender_keypair = Keypair.from_json(
        '[54,150,182,115,231,14,218,194,93,32,95,124,201,27,186,1,47,80,128,52,65,82,130,94,7,133,74,17,78,159,223,3,164,39,76,242,27,98,175,102,195,101,45,53,66,235,203,156,26,103,56,232,79,87,31,34,252,241,120,75,218,75,224,135]')
    print(sender_keypair)
    receiver_address = Pubkey.from_string('J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ')
    # 转账金额（以 lamports 为单位，1 SOL = 1,000,000,000 lamports）
    amount_lamports = 100000000  # 0.1 SOL
    # 创建转账指令
    ixns = [transfer(
        TransferParams(
            from_pubkey=sender_keypair.pubkey(),
            to_pubkey=receiver_address,
            lamports=amount_lamports
        )
    )]
    msg = Message(ixns, sender_keypair.pubkey())
    txn_sig = await conn.send_transaction(Transaction([sender_keypair], msg, latest_blockhash, ))
    print(f"Transaction sent. Signature: {txn_sig.value}")
    # 步骤 2: 加载 IDL 和初始化 Program
    with open("driftIDL.json", "r") as f:
        idl_data = f.read()
    idl = Idl.from_json(idl_data)
    idl_name = [i['name'] for i in json.loads(idl_data)['instructions']]
    program_id = Pubkey.from_string('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH')  # 替换为实际的合约 Program ID
    program = Program(idl=idl, program_id=program_id, provider=provider)


# 运行异步函数
asyncio.run(main())
