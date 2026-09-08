import asyncio
import datetime
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from tokenDemo import test_autoTrade_pm as fixtures
from tokenDemo.autoTrade_pm import CloseRecordManager, Observation, OrderSide, Position, PositionSide


class AutoBNEfficiencyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixtures = fixtures.AutoBNCharacterizationTest()
        self.enterContext(patch.object(CloseRecordManager, "_pending_records", []))
        self.enterContext(patch.object(CloseRecordManager, "_batch_lock", None))
        self.enterContext(patch.object(CloseRecordManager, "_batch_lock_loop", None))

    async def test_invalid_open_parameters_do_not_fetch_account_or_price(self):
        for symbol, target, stop in (
            ("UNKNOWN", 12, 8), ("BTCUSDT", 12, 0),
            ("BTCUSDT", 0, 8), ("BTCUSDT", None, 8), ("BTCUSDT", 12, None),
        ):
            with self.subTest(symbol=symbol, target=target, stop=stop):
                obj, _ = self.fixtures.make_open_position_fixture()
                result = await obj.open_bn_position(
                    symbol, OrderSide.BUY.value, PositionSide.LONG.value,
                    target, stop, self.fixtures.make_position(),
                )

                self.assertIsNone(result)
                obj._call_api.assert_not_awaited()

    async def test_close_queues_record_and_notifies_without_waiting_for_disk(self):
        position = self.fixtures.make_position(take_profit=11, stop_loss=9)
        position.tp_count = 1
        obj = self.fixtures.make_close_position_fixture(position, [(30, 10), (9, 10)])
        observed = []

        async def notify(_msg, *, channel=None):
            if channel == "pushplus":
                observed.append((
                    len(CloseRecordManager._pending_records),
                    obj.alert_all["POSITIONS"]["BTCUSDT"]["tp_count"],
                    obj.get_amount_close.await_count,
                ))

        obj.send_msg = AsyncMock(side_effect=notify)
        with patch.object(CloseRecordManager, "flush_pending_records", new=AsyncMock()) as flush:
            await obj._close_triggered_position("BTCUSDT", position, 1, 11)

        self.assertEqual(observed, [(1, 2, 2)])
        self.assertEqual(CloseRecordManager._pending_records[0]["平仓依据"], "止盈")
        flush.assert_not_awaited()

    async def test_market_flushes_batch_on_success_error_timeout_and_cancellation(self):
        for error in (None, RuntimeError("scan failed"), TimeoutError(), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__):
                obj = self.fixtures.make_autobn()
                obj.send_msg = AsyncMock()

                async def scan(_market):
                    for symbol in ("BTCUSDT", "ETHUSDT"):
                        CloseRecordManager.enqueue_close("AUTOBN", symbol, "LONG", 10, 11, 1, 1, 0.1)
                    if error is not None:
                        raise error

                obj._rzq_market_impl = AsyncMock(side_effect=scan)
                with patch.object(CloseRecordManager, "_record_close_batch") as write:
                    if isinstance(error, asyncio.CancelledError):
                        with self.assertRaises(asyncio.CancelledError):
                            await obj.rzq_market("BN")
                    else:
                        await obj.rzq_market("BN")

                write.assert_called_once()
                self.assertEqual(len(write.call_args.args[0]), 2)
                self.assertEqual(CloseRecordManager._pending_records, [])

    async def test_failed_batch_write_retries_at_next_scan(self):
        obj = self.fixtures.make_autobn()
        obj.send_msg = AsyncMock()
        obj._rzq_market_impl = AsyncMock()
        CloseRecordManager.enqueue_close("AUTOBN", "BTCUSDT", "LONG", 10, 11, 1, 1, 0.1)
        with patch.object(
            CloseRecordManager, "_record_close_batch", side_effect=[OSError("busy"), None]
        ) as write:
            await obj.rzq_market("BN")
            self.assertEqual(len(CloseRecordManager._pending_records), 1)
            await obj.rzq_market("BN")

        self.assertEqual(write.call_count, 2)
        self.assertEqual(CloseRecordManager._pending_records, [])

    async def test_bd_rejects_local_volume_before_fetching_oi(self):
        for refresh in (False, True):
            with self.subTest(refresh=refresh):
                obj = self.fixtures.make_autobn()
                obj._get_bd_oi_windows = AsyncMock(return_value=([100] * 31, [100] * 30))
                passed = await obj._is_bd_observation(
                    "BTCUSDT", [10] * 29 + [12], [100] * 29 + [200], None,
                    refresh=refresh,
                )
                self.assertFalse(passed)
                obj._get_bd_oi_windows.assert_not_awaited()

    async def test_bd_reuses_successful_or_failed_window_only_within_one_scan(self):
        window = fixtures.AutoBNShortSignalTest.make_oi_window()
        for oi_result in ((None, None), (window, window[:-1])):
            with self.subTest(oi_result=oi_result):
                obj = self.fixtures.make_autobn()
                now = datetime.datetime(2026, 9, 8, 10)
                observation = Observation(
                    price=10, timestamp=now.timestamp() - 60,
                    side=OrderSide.SELL, strategy=[PositionSide.BD], name="BTCUSDT",
                )
                obj.alert_all = {"POSITIONS": {}, "OBSERVATIONS": {"BTCUSDT": observation.model_dump()}}
                bars = self.fixtures.make_kline(12, 12)
                bars[-6][5] = 999
                bars[-1][5] = 50
                obj.get_kline = AsyncMock(return_value=bars)
                obj._get_bd_oi_windows = AsyncMock(return_value=oi_result)
                for expected_queries in (1, 2):
                    await obj.rzq_token(asyncio.Semaphore(1), "BTCUSDT", set(), now)
                    self.assertEqual(obj._get_bd_oi_windows.await_count, expected_queries)
                self.assertEqual(obj.alert_all["POSITIONS"], {})

    def test_existing_position_is_parsed_once_and_retains_strategy_fields(self):
        obj = self.fixtures.make_autobn()
        original = self.fixtures.make_position(stop_guard_threshold=100)
        original.tp_count = 2
        obj.alert_all = {"POSITIONS": {"BTCUSDT": original.model_dump()}, "OBSERVATIONS": {}}
        risk = [{
            "symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "10",
            "entryPrice": "10.5", "notional": "110", "unRealizedProfit": "5",
        }]
        with patch.object(Position, "model_validate", wraps=Position.model_validate) as parse:
            positions = obj.get_position_risk(risk)

        parse.assert_called_once()
        self.assertEqual(positions[0].entry_price, 10.5)
        expected = original.model_dump()
        expected["entry_price"] = 10.5
        self.assertEqual(obj.alert_all["POSITIONS"]["BTCUSDT"], expected)

    def test_exchange_symbols_are_filtered_before_precision_and_traversed_once(self):
        class Rows(list):
            traversals = 0

            def __iter__(self):
                self.traversals += 1
                return super().__iter__()

        # 被过滤的交易对不需要解析精度字段。
        rows = Rows([
            {"symbol": "BTCBTC", "quoteAsset": "BTC", "status": "TRADING"},
            {"symbol": "OLDUSDT", "quoteAsset": "USDT", "status": "BREAK"},
            {"symbol": "BTCUSDT", "quoteAsset": "USDT", "status": "TRADING",
             "quotePrecision": 2, "quantityPrecision": 3},
        ])
        obj = self.fixtures.make_autobn()
        obj.get_symbols_info({"symbols": rows})

        self.assertEqual(rows.traversals, 1)
        self.assertEqual(obj.symbols_info, {"BTCUSDT": {
            "quotePrecision": 2, "quantityPrecision": Decimal("0.111"),
        }})
