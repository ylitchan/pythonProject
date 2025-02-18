import asyncio
import json

from anchorpy import Program, Context, Provider, Wallet, Idl
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
# 查询账户余额
balance = client.get_balance(Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ")).value
print(balance)


# 示例：推导用户账户的PDA
def derive_user_pda(
        program_id: Pubkey,  # Drift程序ID
        authority: Pubkey,  # 用户钱包地址
        sub_account_id: int  # 子账户ID
) -> tuple[Pubkey, int]:
    # 构造种子数组
    seeds = [
        b"user",  # 账户类型标识
        bytes(authority),  # 用户权限地址
        sub_account_id.to_bytes(2, "little")  # 子账户ID（小端序）
    ]

    # 查找PDA
    return Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ").find_program_address(seeds, program_id)


a = Pubkey.find_program_address([b"aplomb", ], Pubkey.from_string('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'))


# 从 Base58 编码的私钥字符串恢复密钥对
# private_key_str = "5rY8jQzGze47J7wHj6Pp6vyWsvRjYVVoQ1X6XaTUB7WZ..."  # 你的私钥
# private_key_bytes = base58.b58decode(private_key_str)  # Base58 解码为字节
# keypair = Keypair.from_bytes(private_key_bytes)  # 构建密钥对
# Pubkey.from_string('J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ')
# 构建用户账户地址（示例用固定种子，实际需确认程序逻辑）
# def get_user_account_pda(authority, sub_account_id: int) -> Pubkey:
#     seeds = [
#         bytes("user", "utf-8"),
#         authority.public_key().to_bytes(),
#         sub_account_id.to_bytes(2, 'little')
#     ]
#     pda, bump = Pubkey.find_program_address(seeds, Pubkey.from_string('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'))
#     return pda
# get_user_account_pda(Keypair().pubkey(),123,)
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
    # # 创建并签名交易
    # txn = Transaction().add(transfer_instruction)
    # txn.sign(sender_keypair)
    #
    # # 发送交易
    # txn_sig = await conn.send_transaction(txn)

    print(f"Transaction sent. Signature: {txn_sig.value}")
    # 步骤 2: 加载 IDL 和初始化 Program
    with open("driftIDL.json", "r") as f:
        idl_data = f.read()
    idl = Idl.from_json(idl_data)
    idl_name = [i['name'] for i in json.loads(idl_data)['instructions']]
    program_id = Pubkey.from_string('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH')  # 替换为实际的合约 Program ID
    program = Program(idl=idl, program_id=program_id, provider=provider)

    # 步骤 3: 准备调用参数
    # 假设合约方法需要以下参数：
    # - 一个计数器账户（Counter Account）
    # - 调用者的签名
    # counter_account_pubkey = Pubkey("...")  # 实际计数器账户地址

    # 步骤 4: 调用合约方法
    try:
        # 调用指令
        # tx = await program.rpc["updateUserName"](
        #     sub_account_id=123,
        #     name=list("Alice".ljust(32, '\0')[:32].encode()),
        #     accounts={
        #         "user": Keypair().pubkey(),
        #         "authority": provider.wallet.public_key
        #     }
        # )
        # print(f"Transaction signature: {tx}")
        # 用户钱包（payer和authority）
        authority = sender_keypair  # 实际需要使用合法密钥对
        payer = authority

        # 生成账户地址（需要协议规则，此处为伪代码）
        # 通常user和userStats账户需要PDA推导
        [user_account, user_bump] = Pubkey.find_program_address([b"user", ], Pubkey.from_string(
            'dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'))
        [user_stats, user_stats_bump] = Pubkey.find_program_address([b"user_stats", ], Pubkey.from_string(
            'dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'))
        state_address = user_stats  # state账户地址
        # 调用参数
        sub_account_id = 0
        name = [0] * 32  # 32字节的名称

        # 构建交易
        tx = await program.rpc["initialize_user"](
            sub_account_id,
            name,
            ctx=Context(
                accounts={
                    "user": user_account,
                    "userStats": user_stats,
                    "state": state_address,
                    "authority": authority.pubkey(),
                    "payer": payer.pubkey(),
                    "rent": program_id,  # Sysvar Rent地址
                    "systemProgram": program_id
                },
                signers=[authority, payer],  # 签名者列表
                pre_instructions=[]  # 可能需要初始化账户的指令
            )
        )
        print("Tx hash:", tx)
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
