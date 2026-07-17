import asyncio
import datetime
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from perk_pushplus import PushPlusClient, SendRequest, Template


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
    title = f"{symbol} {action}{status_text}"

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


@lru_cache(maxsize=4)
def _get_pushplus_client(token: str, secret_key: str) -> PushPlusClient:
    builder = PushPlusClient.builder().token(token)
    if secret_key:
        builder = builder.secret_key(secret_key)
    return builder.build()


def _send_pushplus_sync(
    notification: TradeNotification,
    token: str,
    secret_key: str,
) -> None:
    request = (
        SendRequest.builder()
        .title(notification.title)
        .content(notification.content)
        .template(Template.MARKDOWN)
        .build()
    )
    _get_pushplus_client(token, secret_key).send(request)


async def send_pushplus(
    notification: TradeNotification,
    token: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> bool:
    target_token = token or os.getenv("PUSHPLUS_TOKEN")
    if not target_token:
        return False

    target_secret_key = secret_key
    if target_secret_key is None:
        target_secret_key = os.getenv("PUSHPLUS_SECRET_KEY", "")
    await asyncio.to_thread(
        _send_pushplus_sync,
        notification,
        target_token,
        target_secret_key,
    )
    return True
