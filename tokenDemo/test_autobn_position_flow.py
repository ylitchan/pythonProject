import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tokenDemo import test_autoTrade_pm as fixtures
from tokenDemo.autoTrade_pm import CloseRecordManager, Position, PositionSide


class AutoBNPositionFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixtures = fixtures.AutoBNCharacterizationTest()

    async def test_regular_take_profit_persists_when_remaining_query_fails(self):
        for side, price, expected_target in (
            (PositionSide.LONG, 11, 14),
            (PositionSide.SHORT, 9, 6),
        ):
            with self.subTest(side=side):
                position = self.fixtures.make_position(
                    position_side=side,
                    take_profit=price,
                    stop_loss=9 if side == PositionSide.LONG else 12,
                    stop_guard_threshold=100,
                )
                position.tp_count = 1
                obj = self.fixtures.make_close_position_fixture(
                    position, [(30, 10), None]
                )
                with patch.object(
                    CloseRecordManager, "enqueue_close", new=MagicMock()
                ) as record:
                    await obj._close_triggered_position("BTCUSDT", position, 1, price)
                    stored = Position.model_validate(obj.alert_all["POSITIONS"]["BTCUSDT"])
                    self.assertEqual(stored.tp_count, 2)
                    self.assertEqual(stored.take_profit, expected_target)
                    self.assertFalse(await obj._close_triggered_position(
                        "BTCUSDT", stored, 1, price
                    ))

                obj._call_api.assert_awaited_once()
                record.assert_called_once()

    async def test_failed_take_profit_never_advances_count(self):
        for side in (PositionSide.LONG, PositionSide.SHORT):
            for tp_count in (0, 1, 2):
                with self.subTest(side=side, tp_count=tp_count):
                    position = self.fixtures.make_position(
                        position_side=side,
                        take_profit=11 if side == PositionSide.LONG else 9,
                        stop_loss=9 if side == PositionSide.LONG else 12,
                    )
                    position.tp_count = tp_count
                    obj = self.fixtures.make_close_position_fixture(position, [None])
                    original = position.model_dump()

                    await obj._close_triggered_position(
                        "BTCUSDT", position, 1, position.take_profit
                    )

                    self.assertEqual(position.tp_count, tp_count)
                    self.assertEqual(obj.alert_all["POSITIONS"]["BTCUSDT"], original)
                    obj._call_api.assert_not_awaited()

    async def test_completed_take_profit_state_is_saved_before_notification(self):
        for tp_count in (0, 1):
            with self.subTest(tp_count=tp_count):
                position = self.fixtures.make_position(take_profit=11, stop_loss=9)
                position.tp_count = tp_count
                obj = self.fixtures.make_close_position_fixture(
                    position, [(30, 10), (9, 10)]
                )
                notified_states = []

                async def capture_notification(_msg, *, channel=None):
                    if channel == "pushplus":
                        notified_states.append(obj.alert_all["POSITIONS"]["BTCUSDT"].copy())

                obj.send_msg = AsyncMock(side_effect=capture_notification)
                with patch.object(
                    CloseRecordManager, "enqueue_close", new=MagicMock()
                ):
                    await obj._close_triggered_position("BTCUSDT", position, 1, 11)

                self.assertEqual(len(notified_states), 1)
                self.assertEqual(notified_states[0]["tp_count"], tp_count + 1)
                self.assertGreater(notified_states[0]["take_profit"], 11)

    async def test_notification_cancellation_preserves_trade_state_and_record(self):
        position = self.fixtures.make_position(take_profit=11, stop_loss=9)
        position.tp_count = 1
        obj = self.fixtures.make_close_position_fixture(position, [(30, 10), (9, 10)])
        obj.send_msg = AsyncMock(side_effect=asyncio.CancelledError())

        with patch.object(
            CloseRecordManager, "enqueue_close", new=MagicMock()
        ) as record:
            with self.assertRaises(asyncio.CancelledError):
                await obj._close_triggered_position("BTCUSDT", position, 1, 11)

        self.assertEqual(obj.alert_all["POSITIONS"]["BTCUSDT"]["tp_count"], 2)
        self.assertEqual(obj.alert_all["POSITIONS"]["BTCUSDT"]["take_profit"], 14)
        record.assert_called_once()
        obj._call_api.assert_awaited_once()

    async def test_full_stop_query_failure_keeps_trigger_until_reconciled(self):
        position = self.fixtures.make_position(
            position_side=PositionSide.SHORT, take_profit=7, stop_loss=12
        )
        obj = self.fixtures.make_close_position_fixture(
            position, [(100, 10), None, (0, 0)]
        )
        obj.calculate_atr = MagicMock(return_value=1)
        obj.open_bn_position = AsyncMock()
        with patch.object(
            CloseRecordManager, "enqueue_close", new=MagicMock()
        ) as record:
            await obj._close_triggered_position("BTCUSDT", position, 1, 12)
            stored = Position.model_validate(obj.alert_all["POSITIONS"]["BTCUSDT"])
            self.assertEqual(stored.stop_loss, 12)
            self.assertEqual(stored.take_profit, 7)
            await obj._manage_position(
                "BTCUSDT", stored, self.fixtures.make_kline(12, 12), 12
            )

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        obj.open_bn_position.assert_not_awaited()
        obj._call_api.assert_awaited_once()
        record.assert_called_once()

    async def test_small_take_profit_full_close_does_not_retarget_on_query_failure(self):
        for side, price in ((PositionSide.LONG, 11), (PositionSide.SHORT, 9)):
            with self.subTest(side=side):
                position = self.fixtures.make_position(
                    position_side=side, take_profit=price,
                    stop_loss=9 if side == PositionSide.LONG else 12,
                )
                obj = self.fixtures.make_close_position_fixture(
                    position, [(1, 10), None, (0, 0)]
                )
                with patch.object(
                    CloseRecordManager, "enqueue_close", new=MagicMock()
                ) as record:
                    await obj._close_triggered_position("BTCUSDT", position, 1, price)
                    stored = Position.model_validate(obj.alert_all["POSITIONS"]["BTCUSDT"])
                    self.assertEqual(stored.take_profit, price)
                    self.assertEqual(stored.tp_count, 0)
                    await obj._close_triggered_position("BTCUSDT", stored, 1, price)

                self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
                self.assertEqual(record.call_args.kwargs["close_ratio"], 1)
                record.assert_called_once()
                obj._call_api.assert_awaited_once()

    async def test_existing_position_does_not_check_opposite_open_signal(self):
        for side in (PositionSide.LONG, PositionSide.SHORT):
            with self.subTest(side=side):
                position = self.fixtures.make_position(position_side=side)
                obj = self.fixtures.make_autobn()
                obj.check_side = AsyncMock()
                await self.fixtures.run_position(obj, position, self.fixtures.make_kline(10, 10))
                obj.check_side.assert_not_awaited()

    async def test_take_profit_decay_only_applies_on_next_scan(self):
        position = self.fixtures.make_position(take_profit=20, stop_loss=9)
        obj = self.fixtures.make_close_position_fixture(position, [])
        obj.calculate_atr = MagicMock(return_value=1)
        obj.close_bn_position = AsyncMock()
        kline = [[0, 10, 7, 5, 10.1, 100] for _ in range(30)]

        await obj._manage_position("BTCUSDT", position, kline, 10.1)

        obj.close_bn_position.assert_not_awaited()
        self.assertEqual(position.take_profit, 10)
        await obj._manage_position("BTCUSDT", position, kline, 10.1)
        obj.close_bn_position.assert_awaited_once()

    async def test_zero_atr_keeps_dynamic_rails_at_midprice(self):
        for side, target in ((PositionSide.LONG, 20), (PositionSide.SHORT, 1)):
            with self.subTest(side=side):
                position = self.fixtures.make_position(
                    position_side=side, take_profit=target,
                    stop_loss=5 if side == PositionSide.LONG else 15,
                )
                obj = self.fixtures.make_close_position_fixture(position, [])
                obj.calculate_atr = MagicMock(return_value=0)
                kline = self.fixtures.make_kline(10, 10)

                await obj._manage_position("BTCUSDT", position, kline, 10)

                self.assertEqual(position.take_profit, 10)
                obj._call_api.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
