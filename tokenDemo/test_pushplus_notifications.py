import os
import unittest
from unittest.mock import AsyncMock, patch

from tokenDemo.pushplus_notifications import (
    classify_autobn_message,
    format_trade_notification,
    send_pushplus,
)


class AsyncResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload or {"code": 200, "msg": "执行成功"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def json(self, content_type=None):
        return self.payload


class Session:
    def __init__(self, response=None):
        self.response = response or AsyncResponse()
        self.post = unittest.mock.MagicMock(return_value=self.response)


class PushPlusNotificationTest(unittest.IsolatedAsyncioTestCase):
    def test_formats_markdown_trade_notification(self):
        notification = format_trade_notification(
            "AUTOBN",
            "开仓",
            "BTCUSDT",
            "BTCUSDT 开仓\n策略:N,DCA\n委托价格:64320.5\n杠杆:5x",
        )

        self.assertEqual(notification.title, "✅ AUTOBN 开仓成功 · BTCUSDT")
        self.assertIn("# ✅ AUTOBN · 开仓成功", notification.content)
        self.assertIn("## BTCUSDT", notification.content)
        self.assertIn("- **策略：** N,DCA", notification.content)
        self.assertIn("- **杠杆：** 5x", notification.content)
        self.assertNotIn("<", notification.content)

    def test_formats_failure_with_reason_and_time(self):
        notification = classify_autobn_message("BTCUSDT 开仓失败：可用余额为零")

        self.assertEqual(notification.title, "❌ AUTOBN 开仓失败 · BTCUSDT")
        self.assertIn("- **原因：** 可用余额为零", notification.content)
        self.assertIn("**时间：**", notification.content)
        self.assertIn("请检查账户、持仓及运行日志", notification.content)

    def test_classifies_legacy_close_failure_symbol(self):
        notification = classify_autobn_message("bn平仓BTCUSDT失败，当前价格:64000")

        self.assertEqual(notification.title, "❌ AUTOBN 平仓失败 · BTCUSDT")

    def test_classifies_close_skip_as_failure(self):
        notification = classify_autobn_message(
            "BTCUSDT 平仓跳过：查询持仓数量失败"
        )

        self.assertEqual(notification.title, "❌ AUTOBN 平仓失败 · BTCUSDT")

    def test_ignores_non_trade_message(self):
        self.assertIsNone(classify_autobn_message("市场分析任务超时"))

    async def test_missing_token_skips_request(self):
        session = Session()
        notification = format_trade_notification(
            "AUTOBN", "开仓", "BTCUSDT", "BTCUSDT 开仓"
        )

        with patch.dict(os.environ, {}, clear=True):
            sent = await send_pushplus(session, notification)

        self.assertFalse(sent)
        session.post.assert_not_called()

    async def test_sends_markdown_payload(self):
        session = Session()
        notification = format_trade_notification(
            "AUTOA", "平仓", "测试股票", "测试股票 平仓\n策略:BZ,N"
        )

        sent = await send_pushplus(session, notification, token="test-token")

        self.assertTrue(sent)
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["template"], "markdown")
        self.assertEqual(payload["title"], notification.title)
        self.assertEqual(payload["content"], notification.content)

    async def test_business_failure_raises_without_token_leak(self):
        session = Session(AsyncResponse(payload={"code": 500, "msg": "失败"}))
        notification = format_trade_notification(
            "AUTOBN", "开仓", "BTCUSDT", "BTCUSDT 开仓"
        )

        with self.assertRaisesRegex(RuntimeError, "PushPlus 推送失败") as caught:
            await send_pushplus(session, notification, token="secret-token")

        self.assertNotIn("secret-token", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
