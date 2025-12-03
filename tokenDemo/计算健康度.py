import asyncio
from datetime import datetime

import pandas as pd
from web3 import Web3

# 读取 Excel 文件并从 F 列提取地址
excel_file_path = r"C:\Users\颜立全\Documents\lybra存款统计.xlsx"
df = pd.read_excel(excel_file_path)

# 读取 F 列数据(索引从 0 开始,F 列是第 5 列)
raw_addresses = df.iloc[:, 5].dropna().astype(str).values

# 转换为校验和格式的地址,并过滤无效地址
address_borrowed = set()
for addr in raw_addresses:
    addr = addr.strip().lower()
    # 过滤空地址和无效地址
    if (
        addr
        and addr != "0x0000000000000000000000000000000000000000"
        and len(addr) == 42
    ):
        try:
            # 转换为校验和格式
            checksum_addr = Web3.to_checksum_address(addr)
            address_borrowed.add(checksum_addr)
        except Exception as e:
            print(f"跳过无效地址: {addr} - {e}")

print(f"成功加载 {len(address_borrowed)} 个有效地址\n")

LYBRA_ABI = [
    {
        "type": "function",
        "name": "depositedAsset",
        "constant": False,
        "anonymous": False,
        "stateMutability": "view",
        "inputs": [
            {
                "name": "",
                "type": "address",
                "storage_location": "default",
                "offset": 0,
                "index": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "indexed": False,
                "simple_type": {"type": "address"},
            }
        ],
        "outputs": [
            {
                "name": "",
                "type": "uint256",
                "storage_location": "default",
                "offset": 0,
                "index": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "indexed": False,
                "simple_type": {"type": "uint"},
            }
        ],
    },
    {
        "type": "function",
        "name": "getBorrowedOf",
        "constant": False,
        "anonymous": False,
        "stateMutability": "view",
        "inputs": [
            {
                "name": "user",
                "type": "address",
                "storage_location": "default",
                "offset": 0,
                "index": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "indexed": False,
                "simple_type": {"type": "address"},
            }
        ],
        "outputs": [
            {
                "name": "",
                "type": "uint256",
                "storage_location": "default",
                "offset": 0,
                "index": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "indexed": False,
                "simple_type": {"type": "uint"},
            }
        ],
    },
    {
        "type": "function",
        "name": "getAssetPrice",
        "constant": False,
        "anonymous": False,
        "stateMutability": "nonpayable",
        "inputs": [],
        "outputs": [
            {
                "name": "",
                "type": "uint256",
                "storage_location": "default",
                "offset": 0,
                "index": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "indexed": False,
                "simple_type": {"type": "uint"},
            }
        ],
    },
]

LYBRA_CONTRACT_ADDRESS = "0xa980d4c0C2E48d305b582AA439a3575e3de06f0E"
NODE_URL = "https://mainnet.infura.io/v3/42d116ef28d84f0c99f9873f4eb0d7c0"

# 初始化 Web3
w3 = Web3(Web3.HTTPProvider(NODE_URL))
w3.eth.account.enable_unaudited_hdwallet_features()
contract_lybra = w3.eth.contract(
    address=Web3.to_checksum_address(LYBRA_CONTRACT_ADDRESS), abi=LYBRA_ABI
)

# 常量
badCollateralRatio = 150000000000000000000


async def onBehalfOfAddress(target_address, assetPrice):
    """
    检查指定地址的抵押率和资产价值

    参数:
        target_address: 要检查的地址
        assetPrice: 当前资产价格

    返回:
        tuple: (target_address, onBehalfOfCollateralRatio, depositedAsset) 如果符合条件
        None: 如果不符合条件
    """
    try:
        # 获取借款金额
        borrowed = await asyncio.to_thread(
            contract_lybra.functions.getBorrowedOf(target_address).call
        )
        if not borrowed:
            print(f"地址 {target_address} 没有借款")
            return None

        # 获取存款资产
        depositedAsset = await asyncio.to_thread(
            contract_lybra.functions.depositedAsset(target_address).call
        )

        # 计算资产价值和抵押率
        assetValue = depositedAsset * assetPrice
        onBehalfOfCollateralRatio = (assetValue * 100) / borrowed

        print(
            f"地址: {target_address}\n"
            f"  抵押率: {onBehalfOfCollateralRatio / 10e19:.2f}\n"
            f"  资产价值: {assetValue / 10e35:.2f}"
        )

        # 检查是否符合条件
        if (
            onBehalfOfCollateralRatio <= 10e19
            or onBehalfOfCollateralRatio >= badCollateralRatio
            or assetValue * 0.1 / 10e27 <= w3.eth.gas_price * 1.3
        ):
            print("  ❌ 不符合条件\n")
            return None

        print("  ✅ 符合条件!\n")
        return (target_address, onBehalfOfCollateralRatio, depositedAsset)

    except Exception as e:
        print(f"处理地址 {target_address} 时出错: {e}")
        return None


async def main():
    """主函数:扫描所有地址"""
    print(f"{datetime.now()} 开始扫描")
    print(f"总共需要检查 {len(address_borrowed)} 个地址\n")

    # 获取当前资产价格
    try:
        assetPrice = contract_lybra.functions.getAssetPrice().call()
        print(f"当前资产价格: {assetPrice}\n")
    except Exception as e:
        print(f"获取资产价格失败: {e}")
        return

    # 并发检查所有地址
    results = await asyncio.gather(
        *[onBehalfOfAddress(addr, assetPrice) for addr in address_borrowed]
    )

    # 过滤出符合条件的地址
    valid_results = [r for r in results if r is not None]

    # 按资产金额排序
    valid_results.sort(key=lambda x: x[-1], reverse=True)

    print(f"\n{'=' * 60}")
    print("扫描完成!")
    print(f"符合条件的地址数量: {len(valid_results)}")
    print(f"{'=' * 60}\n")

    if valid_results:
        print("符合条件的地址列表(按资产金额排序):")
        for i, (addr, ratio, asset) in enumerate(valid_results, 1):
            print(f"{i}. {addr}")
            print(f"   抵押率: {ratio / 10e19:.2f}")
            print(f"   资产: {asset / 10e17:.2f}\n")


if __name__ == "__main__":
    asyncio.run(main())
