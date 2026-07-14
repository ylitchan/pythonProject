import argparse
import asyncio
import json

import aiohttp

try:
    from tokenDemo.pushplus_notifications import (
        format_trade_notification,
        send_pushplus,
    )
except ModuleNotFoundError:
    from pushplus_notifications import (
        format_trade_notification,
        send_pushplus,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="测试 PushPlus Markdown 消息推送")
    parser.add_argument("token", help="PushPlus token")
    args = parser.parse_args()

    notification = format_trade_notification(
        "AUTOBN",
        "开仓",
        "BTCUSDT",
        "BTCUSDT 开仓\n策略:N,DCA\n持仓方向:LONG\n杠杆:5x\n委托数量:0.002\n委托价格:64320.50\n名义价值:128.64 USDT\n账户余额:1280.00\n仓位比例:10.05%\n收益率:2.77%",
    )
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await send_pushplus(session, notification, token=args.token)
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
        raise SystemExit(f"推送请求失败: {exc}") from exc

    print(json.dumps({"code": 200, "msg": "Markdown 推送成功"}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
