import datetime
import os
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp


@dataclass(frozen=True)
class TradeNotification:
    title: str
    content: str


def format_trade_notification(
    market: str,
    action: str,
    symbol: str,
    message: str,
    success: bool = True,
) -> TradeNotification:
    status_icon = "✅" if success else "❌"
    status_text = "成功" if success else "失败"
    title = f"{status_icon} {market} {action}{status_text} · {symbol}"

    lines = [line.strip() for line in message.splitlines() if line.strip()]
    detail_lines = []
    quote_lines = []
    body_lines = lines[1:]
    if not success and len(lines) == 1:
        reason_parts = re.split(r"失败[：:]|跳过[：:]", lines[0], maxsplit=1)
        if len(reason_parts) == 2 and reason_parts[1].strip():
            body_lines = [f"原因:{reason_parts[1].strip()}"]
    for line in body_lines:
        if ":" in line or "：" in line:
            separator = ":" if ":" in line else "："
            label, value = line.split(separator, 1)
            detail_lines.append(f"- **{label.strip()}：** {value.strip()}")
        else:
            quote_lines.append(f"> {line}")

    content_parts = [
        f"# {status_icon} {market} · {action}{status_text}",
        "",
        f"## {symbol}",
        "",
    ]
    if detail_lines:
        content_parts.extend(detail_lines)
    if quote_lines:
        if detail_lines:
            content_parts.extend(["", "---", ""])
        content_parts.extend(quote_lines)
    if not success:
        content_parts.extend(
            [
                "",
                f"- **时间：** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "> 本次交易动作未完成，请检查账户、持仓及运行日志。",
            ]
        )

    return TradeNotification(title=title, content="\n".join(content_parts))


def classify_autobn_message(message: str) -> Optional[TradeNotification]:
    first_line = message.splitlines()[0].strip() if message.strip() else ""
    if "开仓" in first_line:
        action = "开仓"
    elif "平仓" in first_line:
        action = "平仓"
    else:
        return None

    success = "失败" not in first_line and "跳过" not in first_line
    symbol = first_line.split(action, 1)[0].strip()
    if symbol.lower() == "bn":
        symbol = first_line.split(action, 1)[1]
        symbol = re.split(r"失败|跳过|[：:]", symbol, maxsplit=1)[0].strip()
    symbol = symbol or "未知标的"
    return format_trade_notification("AUTOBN", action, symbol, message, success)


async def send_pushplus(
    session: aiohttp.ClientSession,
    notification: TradeNotification,
    token: Optional[str] = None,
) -> bool:
    target_token = token or os.getenv("PUSHPLUS_TOKEN")
    if not target_token:
        return False

    async with session.post(
        "https://www.pushplus.plus/send",
        json={
            "token": target_token,
            "title": notification.title,
            "content": notification.content,
            "template": "markdown",
        },
    ) as response:
        result = await response.json(content_type=None)
        if response.status != 200 or result.get("code") != 200:
            raise RuntimeError(
                f"PushPlus 推送失败，状态码:{response.status}，响应:{result}"
            )
    return True
