from solana.rpc.api import Client
from solders.pubkey import Pubkey
# 连接 Solana 主网节点
client = Client("https://api.mainnet-beta.solana.com")

# 查询账户余额
balance = client.get_balance(Pubkey.from_string("J1zeHKeV5hYSXec1MzxzErzaKdtJbRBQ6Ggv1F4V8TdZ")).value
print(balance)