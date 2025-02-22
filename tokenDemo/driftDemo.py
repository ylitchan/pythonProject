import asyncio
import traceback

from anchorpy import Wallet
from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, WebsocketLogProviderConfig
from driftpy.events.types import WrappedEvent
from driftpy.types import PositionDirection, OrderParams, OrderType, MarketType  # 新增 MarketType 导入
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    url = 'https://api.mainnet-beta.solana.com'  # replace w/ any rpc
    connection = AsyncClient(url)
    with open('PRIVATE_KEY','r') as f:
        PRIVATE_KEY=f.read()
    wallet = Wallet(Keypair.from_base58_string(PRIVATE_KEY))
    drift_client = DriftClient(connection, wallet, "mainnet")
    # tx_sig = await drift_client.initialize_user(sub_account_id=0, name=None)
    # print(tx_sig)
    # 4. 订阅账户数据
    await drift_client.subscribe()
    # 获取当前用户账户
    drift_user = drift_client.get_user()
    # 配置事件订阅
    options = EventSubscriptionOptions(
        # event_types=('OrderActionRecord',),
        max_tx=4096,
        max_events_per_type=4096,
        order_by="blockchain",
        order_dir="asc",
        log_provider_config=WebsocketLogProviderConfig()
    )

    event_subscriber = EventSubscriber(connection, drift_client.program, options)
    event_subscriber.subscribe()

    # 获取用户公钥
    user_public_key = drift_user.user_public_key

    def liquidation_callback(event: WrappedEvent):
        """处理清算事件"""
        if event.event_type not in ["LiquidationRecord", "FundingPaymentRecord","FundingRateRecord"]:
            return
        print(event, '\n')
        if event.event_type not in ["LiquidationRecord"]:
            print(event)
        # 检查是否是自己的账户被清算
        # if event.data.user == user_public_key:
        #     print(f"我的仓位被强平！清算详情: {event.data}")
        #     # 提取更多信息，例如清算的市场和数量
        #     market_index = event.data.market_index
        #     liquidated_amount = event.data.base_asset_amount / 1e9  # 转换为可读单位
        #     print(f"市场索引: {market_index}, 清算数量: {liquidated_amount}")

    event_subscriber.event_emitter.new_event += liquidation_callback
    while True:
        await asyncio.sleep(1)

    async def deposit_usdc(drift_client, amount_usdc):
        try:
            # amount 是 USDC 的数量，精度为 10^6（1 USDC = 1_000_000）
            tx_sig = await drift_client.deposit(
                amount=int(amount_usdc * 1_000_000),  # 例如 100 USDC
                spot_market_index=0,  # USDC 市场通常是 0
                user_token_account=wallet.public_key
            )
            print(f"存款成功，交易签名: {tx_sig}")
        except Exception as e:
            print(f"存款失败: {str(e)}")

    async def deposit_sol_to_drift(drift_client, amount_sol, connection, wallet):
        try:
            # 执行存款
            tx_sig = await drift_client.deposit(
                amount=int(amount_sol * 1_000_000_000),  # SOL 精度为 10^9
                spot_market_index=1,  # SOL 的Spot市场，通常是 1
                user_token_account=wallet.public_key
            )
            print(f"SOL 存款成功，交易签名: {tx_sig}")
        except Exception as e:
            print(f"存款失败: {str(e)}")

    async def swap_sol_to_usdc(drift_client, amount_sol_to_swap):
        try:
            # 定义订单参数：卖 SOL 买 USDC
            order_params = OrderParams(
                order_type=OrderType.Market(),  # 市价单
                direction=PositionDirection.Short(),  # 卖出 SOL
                base_asset_amount=int(amount_sol_to_swap * BASE_PRECISION),  # 要卖的 SOL 数量
                market_index=1,  # SOL 市场
                market_type=MarketType.Spot(),
                reduce_only=False,
            )

            # 下单并执行交易
            tx_sig = await drift_client.place_and_take_spot_order(
                order_params=order_params,
            )
            print(f"成功将 SOL 转换为 USDC，交易签名: {tx_sig}")

            # 检查余额（可选）
            user = drift_client.get_user()
            sol_balance = user.get_spot_position(1).scaled_balance / 1_000_000_000  # SOL 余额
            usdc_balance = user.get_spot_position(0).scaled_balance / 1_000_000_000  # USDC 余额
            print(f"当前 SOL 余额: {sol_balance}")
            print(f"当前 USDC 余额: {usdc_balance}")

        except Exception as e:
            traceback.print_exc()
            print(f"转换失败: {str(e)}")

    # 5. 存款 1 SOL 到 Drift
    # await deposit_sol_to_drift(drift_client, 1, connection, wallet)
    # 6. 将 0.5 SOL 转换为 USDC
    # await swap_sol_to_usdc(drift_client, 0.1)
    # 5. 开仓参数
    market_index = 0  # SOL-PERP 市场，通常是 0，具体索引请参考 Drift 文档
    amount = 0.1 * BASE_PRECISION  # 开仓数量，例如 0.1 SOL (注意使用 BASE_PRECISION)
    direction = PositionDirection.Long()  # 开多仓，也可以是 PositionDirection.SHORT()
    # 在开仓前调用
    # await deposit_usdc(drift_client, 100)  # 存入 100 USDC
    # 6. 执行开仓操作
    try:
        tx_sig = await drift_client.open_position(
            direction=direction,
            amount=int(amount),
            market_index=market_index,
            # market_type=market_type  # 添加 market_type 参数
        )
        print(f"开仓成功，交易签名: {tx_sig}")

        # 7. (可选) 检查用户仓位
        drift_user = drift_client.get_user()
        positions = drift_user.get_user_position(0)
        print("当前仓位:", positions)

    except Exception as e:
        traceback.print_exc()
        print(f"开仓失败: {str(e)}")

    # 8. 清理
    await drift_client.unsubscribe()


# 运行异步函数
asyncio.run(main())
