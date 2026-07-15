import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
from perk_pushplus import PushPlusError

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
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    notification = format_trade_notification(
        "AUTOBN",
        "开仓",
        "BTCUSDT",
        "BTCUSDT 开仓\n策略:N,DCA\n持仓方向:LONG\n杠杆:5x\n委托数量:0.002\n委托价格:64320.50\n名义价值:128.64 USDT\n账户余额:1280.00\n仓位比例:10.05%\n收益率:2.77%",
    )
    try:
        sent = await send_pushplus(notification)
    except PushPlusError as exc:
        raise SystemExit(f"推送请求失败: {exc}") from exc
    if not sent:
        raise SystemExit("推送请求失败: .env 中未配置 PUSHPLUS_TOKEN")

    print(json.dumps({"code": 200, "msg": "SDK Markdown 推送成功"}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
