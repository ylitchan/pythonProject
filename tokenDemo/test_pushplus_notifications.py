import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from perk_pushplus import Template

from tokenDemo.pushplus_notifications import (
    DailyPosition,
    _get_pushplus_client,
    classify_autobn_message,
    format_daily_positions_notification,
    format_trade_notification,
    send_pushplus,
)


class PushPlusNotificationTest(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        _get_pushplus_client.cache_clear()

    def test_formats_markdown_trade_notification(self):
        notification = format_trade_notification(
            "AUTOBN",
            "开仓",
            "BTCUSDT",
            "BTCUSDT 开仓\n策略:N,DCA\n委托价格:64320.5\n杠杆:5x",
        )

        self.assertEqual(notification.title, "BTCUSDT 开仓成功")
        self.assertIn("# ✅ AUTOBN · 开仓成功", notification.content)
        self.assertIn("## BTCUSDT", notification.content)
        self.assertIn("- **策略：** N,DCA", notification.content)
        self.assertIn("- **杠杆：** 5x", notification.content)
        self.assertNotIn("<", notification.content)

    def test_formats_daily_positions_notification(self):
        notification = format_daily_positions_notification(
            "AUTOBN",
            "账户余额",
            2406.50073781,
            "USDT",
            [
                DailyPosition(
                    name="IOSTUSDT",
                    strategy="BZ",
                    direction="LONG",
                    entry_price=0.0006219507703120751,
                    notional=234.59522,
                    unrealized_pnl=-7.86731186,
                    profit_rate=-0.0335,
                    take_profit=0.0007028113366718827,
                    stop_loss=0.0005691567398320147,
                    open_date=20260901,
                    currency="USDT",
                )
            ],
        )

        self.assertEqual(notification.title, "AUTOBN 每日持仓")
        self.assertIn("# 📊 AUTOBN · 每日持仓", notification.content)
        self.assertIn("## 账户概览", notification.content)
        self.assertIn("- **账户余额：** `2,406.50 USDT`", notification.content)
        self.assertIn("- **持仓数量：** `1`", notification.content)
        self.assertIn("## 1. IOSTUSDT · 🟢 LONG", notification.content)
        self.assertIn("**策略：** `BZ`", notification.content)
        self.assertIn(
            "- **开仓价格：** `0.00062195 USDT`", notification.content
        )
        self.assertIn("- **名义价值：** `234.60 USDT`", notification.content)
        self.assertIn(
            "- **持仓盈亏：** 🔴 **-7.87 USDT**", notification.content
        )
        self.assertIn("- **持仓收益：** 🔴 **-3.35%**", notification.content)
        self.assertIn(
            "- **止盈 / 止损：** `0.00070281` / `0.00056916`",
            notification.content,
        )
        self.assertIn("- **开仓日期：** `2026-09-01`", notification.content)
        self.assertNotIn("===", notification.content)

    def test_formats_empty_daily_positions_notification(self):
        notification = format_daily_positions_notification(
            "AUTOA", "总持仓金额", 0, "CNY", []
        )

        self.assertIn("- **总持仓金额：** `0.00 CNY`", notification.content)
        self.assertIn("- **持仓数量：** `0`", notification.content)
        self.assertIn("> 当前暂无持仓。", notification.content)

    def test_formats_failure_with_reason_and_time(self):
        notification = classify_autobn_message("BTCUSDT 开仓失败：可用余额为零")

        self.assertEqual(notification.title, "BTCUSDT 开仓失败")
        self.assertIn("- **原因：** 可用余额为零", notification.content)
        self.assertIn("**时间：**", notification.content)
        self.assertIn("请检查账户、持仓及运行日志", notification.content)

    def test_classifies_legacy_close_failure_symbol(self):
        notification = classify_autobn_message("bn平仓BTCUSDT失败，当前价格:64000")

        self.assertEqual(notification.title, "BTCUSDT 平仓失败")

    def test_classifies_close_skip_as_failure(self):
        notification = classify_autobn_message(
            "BTCUSDT 平仓跳过：查询持仓数量失败"
        )

        self.assertEqual(notification.title, "BTCUSDT 平仓失败")

    def test_ignores_non_trade_message(self):
        self.assertIsNone(classify_autobn_message("市场分析任务超时"))

    async def test_missing_token_skips_sdk(self):
        notification = format_trade_notification(
            "AUTOBN", "开仓", "BTCUSDT", "BTCUSDT 开仓"
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "tokenDemo.pushplus_notifications._send_pushplus_sync"
            ) as send_sync,
        ):
            sent = await send_pushplus(notification)

        self.assertFalse(sent)
        send_sync.assert_not_called()

    async def test_sends_markdown_with_sdk_in_worker_thread(self):
        notification = format_trade_notification(
            "AUTOA", "平仓", "测试股票", "测试股票 平仓\n策略:BZ,N"
        )
        self.assertEqual(notification.title, "测试股票 平仓成功")
        client = MagicMock()
        builder = MagicMock()
        builder.token.return_value = builder
        builder.secret_key.return_value = builder
        builder.build.return_value = client

        with (
            patch(
                "tokenDemo.pushplus_notifications.PushPlusClient.builder",
                return_value=builder,
            ),
            patch("asyncio.to_thread", wraps=asyncio.to_thread) as to_thread,
        ):
            sent = await send_pushplus(
                notification,
                token="test-token",
                secret_key="test-secret",
            )

        self.assertTrue(sent)
        to_thread.assert_awaited_once()
        builder.token.assert_called_once_with("test-token")
        builder.secret_key.assert_called_once_with("test-secret")
        request = client.send.call_args.args[0]
        self.assertEqual(request.title, notification.title)
        self.assertEqual(request.content, notification.content)
        self.assertEqual(request.template, Template.MARKDOWN)

    async def test_secret_key_is_optional_for_message_send(self):
        notification = format_trade_notification(
            "AUTOBN", "开仓", "BTCUSDT", "BTCUSDT 开仓"
        )
        client = MagicMock()
        builder = MagicMock()
        builder.token.return_value = builder
        builder.build.return_value = client

        with patch(
            "tokenDemo.pushplus_notifications.PushPlusClient.builder",
            return_value=builder,
        ):
            sent = await send_pushplus(
                notification,
                token="test-token",
                secret_key="",
            )

        self.assertTrue(sent)
        builder.secret_key.assert_not_called()
        client.send.assert_called_once()

    async def test_sdk_failure_does_not_leak_credentials(self):
        notification = format_trade_notification(
            "AUTOBN", "开仓", "BTCUSDT", "BTCUSDT 开仓"
        )
        client = MagicMock()
        client.send.side_effect = RuntimeError("PushPlus SDK 发送失败")
        builder = MagicMock()
        builder.token.return_value = builder
        builder.secret_key.return_value = builder
        builder.build.return_value = client

        with patch(
            "tokenDemo.pushplus_notifications.PushPlusClient.builder",
            return_value=builder,
        ):
            with self.assertRaisesRegex(RuntimeError, "PushPlus SDK 发送失败") as caught:
                await send_pushplus(
                    notification,
                    token="secret-token",
                    secret_key="secret-key",
                )

        self.assertNotIn("secret-token", str(caught.exception))
        self.assertNotIn("secret-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
