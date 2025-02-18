import asyncio
import json

import base58
from anchorpy import Program, Context, Provider, Wallet
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey

# 连接 Solana 主网节点
client = Client("https://api.mainnet-beta.solana.com")

# 查询账户余额
balance = client.get_balance(Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ")).value
print(balance)

# 从 Base58 编码的私钥字符串恢复密钥对
private_key_str = "5rY8jQzGze47J7wHj6Pp6vyWsvRjYVVoQ1X6XaTUB7WZ..."  # 你的私钥
private_key_bytes = base58.b58decode(private_key_str)  # Base58 解码为字节
keypair = Keypair.from_bytes(private_key_bytes)  # 构建密钥对


async def main():
    # 步骤 1: 连接 RPC
    rpc_url = "https://api.devnet.solana.com"
    conn = AsyncClient(rpc_url)
    provider = Provider(conn, Wallet(Keypair()))  # 需要签名者（发送交易的账户）

    # 步骤 2: 加载 IDL 和初始化 Program
    with open("idl.json", "r") as f:
        idl_data = json.load(f)

    program_id = Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ")  # 替换为实际的合约 Program ID
    program = Program(idl=idl_data, program_id=program_id, provider=provider)

    # 步骤 3: 准备调用参数
    # 假设合约方法需要以下参数：
    # - 一个计数器账户（Counter Account）
    # - 调用者的签名
    counter_account_pubkey = Pubkey("...")  # 实际计数器账户地址

    # 步骤 4: 调用合约方法
    try:
        tx_hash = await program.rpc["increment_counter"](  # 方法名与 IDL 中一致
            # 方法的参数（根据 IDL 定义，此处假设无须额外参数）
            ctx=Context(
                accounts={
                    "counter": counter_account_pubkey,
                    "user": provider.wallet.public_key,
                    "system_program": SYS_PROGRAM_ID,
                },
                # 可附加签名者（如需要多签）
                signers=[]
            )
        )
        print(f"交易成功，哈希: {tx_hash}")
    except Exception as e:
        print(f"调用失败: {e}")
    finally:
        await conn.close()


# 运行异步函数
asyncio.run(main())
