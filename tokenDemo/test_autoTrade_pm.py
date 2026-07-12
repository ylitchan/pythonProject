import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from tokenDemo.autoTrade_pm import (
    AUTOA,
    AUTOBN,
    CloseRecordManager,
    Observation,
    OrderSide,
    Position,
    PositionSide,
)


class ObservationTest(unittest.TestCase):
    def test_bz_reference_high_is_optional(self):
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="测试股票",
        )

        self.assertIsNone(observation.bz_reference_high)


class AutoABzReferenceHighTest(unittest.TestCase):
    @staticmethod
    def make_hist(yesterday_low=9.9, yesterday_high=11, today_open=11.1):
        return pd.DataFrame(
            [
                {"open": 10, "high": yesterday_high, "low": yesterday_low, "close": 10.5},
                {"open": today_open, "high": 12, "low": 11, "close": 11.5},
            ]
        )

    def test_passes_on_pullback_and_gap_up(self):
        hist = self.make_hist()

        self.assertTrue(AUTOA.check_gap_up_after_bz_reference(hist, 10))

    def test_rejects_low_equal_to_reference(self):
        hist = self.make_hist(yesterday_low=10)

        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, 10))

    def test_rejects_open_equal_to_yesterday_high(self):
        hist = self.make_hist(today_open=11)

        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, 10))

    def test_rejects_missing_or_invalid_reference(self):
        hist = self.make_hist()

        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, None))
        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, 0))
        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, -1))

    def test_rejects_insufficient_history(self):
        hist = self.make_hist().tail(1)

        self.assertFalse(AUTOA.check_gap_up_after_bz_reference(hist, 10))


class AutoADailyPositionValuationTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_position(name="测试股票", strategies=None):
        return Position(
            take_profit=12,
            stop_loss=8,
            close_side=OrderSide.SELL,
            position_side=PositionSide.LONG,
            entry_price=10,
            name=name,
            date=20260701,
            strategy=strategies or [PositionSide.BZ, PositionSide.DCA],
        )

    def test_calculates_position_valuation(self):
        position = self.make_position()

        shares, notional, pnl, rate = AUTOA._calculate_position_valuation(
            position, 10.5
        )

        self.assertEqual(shares, 200)
        self.assertEqual(notional, 2100)
        self.assertEqual(pnl, 100)
        self.assertEqual(rate, 0.05)

    async def test_second_dca_uses_quarter_atr_take_profit_distance(self):
        position = self.make_position(
            strategies=[PositionSide.BZ, PositionSide.DCA]
        )
        position.entry_price = 12
        position.take_profit = 20
        hist = pd.DataFrame([
            {"high": 10, "low": 8, "close": 9, "volume": 100},
            {"high": 10, "low": 8, "close": 9, "volume": 100},
        ])
        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {"000001": position.model_dump()},
                "OBSERVATIONS": {},
            }),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(AUTOA, "calculate_atr", return_value=2),
            patch.object(AUTOA, "send_msg", new=AsyncMock()),
        ):
            await AUTOA.on_positions(
                "000001",
                ["20260711", "20260710"],
                position.model_dump(),
                pd.Timestamp("2026-07-11").to_pydatetime(),
            )
            stored = Position.model_validate(
                AUTOA.alert_all["POSITIONS"]["000001"]
            )

        self.assertEqual(stored.entry_price, 11)
        self.assertEqual(stored.take_profit, 11.5)

    async def test_existing_dca_recalculates_take_profit_with_current_atr(self):
        position = self.make_position(strategies=[PositionSide.BZ, PositionSide.DCA])
        position.take_profit = 20
        hist = pd.DataFrame([
            {"high": 12, "low": 10, "close": 11, "volume": 100},
            {"high": 12, "low": 10, "close": 11, "volume": 100},
        ])
        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {"000001": position.model_dump()},
                "OBSERVATIONS": {},
            }),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(AUTOA, "calculate_atr", return_value=2),
        ):
            await AUTOA.on_positions(
                "000001",
                ["20260711", "20260710"],
                position.model_dump(),
                pd.Timestamp("2026-07-11").to_pydatetime(),
            )
            stored = Position.model_validate(
                AUTOA.alert_all["POSITIONS"]["000001"]
            )

        self.assertEqual(stored.take_profit, 11)

    async def test_pushes_zero_total_when_no_positions(self):
        with (
            patch.object(AUTOA, "alert_all", {"POSITIONS": {}}),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send_msg,
        ):
            await AUTOA.push_daily_positions()

        send_msg.assert_awaited_once_with(
            "总持仓金额:\n0.00 CNY\n持仓信息:\n暂无持仓"
        )

    async def test_sums_successful_positions_and_marks_failed_quote(self):
        positions = {
            "000001": self.make_position("成功股票").model_dump(),
            "000002": self.make_position("失败股票", [PositionSide.BZ]).model_dump(),
        }

        async def get_price(code, trading_days):
            return 10.5 if code == "000001" else None

        with (
            patch.object(AUTOA, "alert_all", {"POSITIONS": positions}),
            patch.object(AUTOA, "_get_auction_price", side_effect=get_price),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send_msg,
        ):
            await AUTOA.push_daily_positions()

        message = send_msg.await_args.args[0]
        self.assertIn("总持仓金额:\n2100.00 CNY", message)
        self.assertIn("策略持仓股数:200", message)
        self.assertIn("名义价值:2100.00 CNY", message)
        self.assertIn("持仓盈亏:100.00 CNY", message)
        self.assertIn("持仓收益:5.00%", message)
        self.assertIn("失败股票(000002)", message)
        self.assertIn("行情获取失败，暂不可估值（未计入总持仓金额）", message)
        self.assertNotIn("账户余额", message)
        self.assertNotIn("N/A", message)

    async def test_pushes_failed_details_when_all_quotes_fail(self):
        positions = {"000001": self.make_position().model_dump()}
        with (
            patch.object(AUTOA, "alert_all", {"POSITIONS": positions}),
            patch.object(AUTOA, "_get_auction_price", new=AsyncMock(return_value=None)),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send_msg,
        ):
            await AUTOA.push_daily_positions()

        message = send_msg.await_args.args[0]
        self.assertIn("总持仓金额:\n0.00 CNY", message)
        self.assertIn("行情获取失败", message)
        self.assertNotIn("名义价值:0.00", message)
        self.assertNotIn("持仓盈亏:0.00", message)
        self.assertNotIn("持仓收益:0.00%", message)

    async def test_daily_positions_reuses_one_trading_calendar_snapshot(self):
        positions = {
            "000001": self.make_position("股票一").model_dump(),
            "000002": self.make_position("股票二").model_dump(),
        }
        trading_days = ["20260711", "20260710"]

        async def get_price(code, supplied_days):
            self.assertIs(supplied_days, trading_days)
            return 10.5

        with (
            patch.object(AUTOA, "alert_all", {"POSITIONS": positions}),
            patch.object(AUTOA, "zt_dates", []),
            patch.object(
                AUTOA,
                "get_last_trading_days",
                new=AsyncMock(return_value=trading_days),
            ) as get_days,
            patch.object(AUTOA, "_get_auction_price", side_effect=get_price) as get_price_mock,
            patch.object(AUTOA, "send_msg", new=AsyncMock()),
        ):
            await AUTOA.push_daily_positions()

        get_days.assert_awaited_once()
        self.assertEqual(get_price_mock.await_count, 2)

    async def test_auction_prices_still_fetch_each_stock_independently(self):
        trading_days = ["20260711", "20260710"]
        hist = pd.DataFrame([{"close": 10.5}])
        with patch.object(
            AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)
        ) as stock_hist:
            first = await AUTOA._get_auction_price("000001", trading_days)
            second = await AUTOA._get_auction_price("000002", trading_days)

        self.assertEqual(first, 10.5)
        self.assertEqual(second, 10.5)
        self.assertEqual(stock_hist.await_count, 2)
        self.assertEqual(
            [call.args[0] for call in stock_hist.await_args_list],
            ["000001", "000002"],
        )


class CloseRecordManagerCharacterizationTest(unittest.IsolatedAsyncioTestCase):
    def test_record_close_preserves_other_sheet_and_formats_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_file = Path(temp_dir) / "records.xlsx"
            other = pd.DataFrame([{"保留字段": "保留值"}])
            with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
                other.to_excel(writer, sheet_name="其他", index=False)

            record = {
                "source": "AUTOA",
                "平仓时间": "2026-07-11 10:00:00",
                "交易品种": "000001",
                "持仓方向": "LONG",
                "开仓价格": 10,
                "平仓价格": 11,
                "平仓数量": 100,
                "平仓盈亏(USDT/CNY)": 100,
                "平仓收益率": "10.00%",
                "平仓比例": "70.00%",
                "策略标签": "BZ",
                "平仓依据": "止盈",
                "多空比": "",
                "基差率": "",
            }
            with patch.object(CloseRecordManager, "_excel_file", str(excel_file)):
                CloseRecordManager._record_close_batch([record])

            sheets = pd.read_excel(excel_file, sheet_name=None)
            self.assertEqual(sheets["其他"].to_dict("records"), [{"保留字段": "保留值"}])
            record = sheets[CloseRecordManager.SHEET_NAMES["AUTOA"]].iloc[0]
            self.assertEqual(record["交易品种"], 1)
            self.assertEqual(record["平仓收益率"], "10.00%")
            self.assertEqual(record["平仓比例"], "70.00%")
            self.assertEqual(record["策略标签"], "BZ")
            self.assertEqual(record["平仓依据"], "止盈")
    def test_batch_groups_records_by_sheet_with_one_concat_each(self):
        records = [
            {"source": "AUTOA", "交易品种": "000001"},
            {"source": "AUTOBN", "交易品种": "BTCUSDT"},
            {"source": "AUTOA", "交易品种": "000002"},
        ]
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(
                CloseRecordManager,
                "_excel_file",
                str(Path(temp_dir) / "records.xlsx"),
            ),
            patch("tokenDemo.autoTrade_pm.pd.concat", wraps=pd.concat) as concat,
        ):
            CloseRecordManager._record_close_batch(records)
            sheets = pd.read_excel(CloseRecordManager._excel_file, sheet_name=None)

        self.assertEqual(concat.call_count, 2)
        self.assertEqual(
            sheets[CloseRecordManager.SHEET_NAMES["AUTOA"]]["交易品种"].tolist(),
            [1, 2],
        )
        self.assertEqual(
            sheets[CloseRecordManager.SHEET_NAMES["AUTOBN"]]["交易品种"].tolist(),
            ["BTCUSDT"],
        )

    async def test_async_records_in_same_loop_are_written_as_one_batch(self):
        records = []

        def capture_batch(batch):
            records.append(batch)

        with (
            patch.object(CloseRecordManager, "_pending_records", []),
            patch.object(CloseRecordManager, "_batch_lock", None),
            patch.object(CloseRecordManager, "_record_close_batch", side_effect=capture_batch),
        ):
            await __import__("asyncio").gather(
                CloseRecordManager.record_close_async(
                    "AUTOA", "000001", "LONG", 10, 11, 100, 100, 0.1
                ),
                CloseRecordManager.record_close_async(
                    "AUTOBN", "BTCUSDT", "SHORT", 100, 90, 1, 10, 0.1
                ),
            )

        self.assertEqual(len(records), 1)
        self.assertEqual([item["交易品种"] for item in records[0]], ["000001", "BTCUSDT"])

    async def test_async_write_failure_is_retained_without_raising(self):
        with (
            patch.object(CloseRecordManager, "_pending_records", []),
            patch.object(CloseRecordManager, "_batch_lock", None),
            patch.object(CloseRecordManager, "_batch_lock_loop", None),
            patch.object(
                CloseRecordManager,
                "_record_close_batch",
                side_effect=OSError("文件被占用"),
            ),
        ):
            await CloseRecordManager.record_close_async(
                "AUTOBN", "BTCUSDT", "LONG", 100, 101, 1, 1, 0.01
            )

            self.assertEqual(len(CloseRecordManager._pending_records), 1)
            self.assertEqual(
                CloseRecordManager._pending_records[0]["交易品种"], "BTCUSDT"
            )

    async def test_batch_lock_is_recreated_for_a_new_event_loop(self):
        old_loop = object()
        old_lock = MagicMock()
        with (
            patch.object(CloseRecordManager, "_pending_records", []),
            patch.object(CloseRecordManager, "_batch_lock", old_lock),
            patch.object(CloseRecordManager, "_batch_lock_loop", old_loop),
            patch.object(CloseRecordManager, "_record_close_batch"),
        ):
            await CloseRecordManager.record_close_async(
                "AUTOA", "000001", "LONG", 10, 11, 100, 100, 0.1
            )

            self.assertIsNot(CloseRecordManager._batch_lock, old_lock)
            self.assertIsNot(CloseRecordManager._batch_lock_loop, old_loop)

    async def test_flush_pending_records_writes_remaining_batch(self):
        pending = [{"source": "AUTOA", "交易品种": "000001"}]
        expected = pending[:]
        with (
            patch.object(CloseRecordManager, "_pending_records", pending),
            patch.object(CloseRecordManager, "_batch_lock", None),
            patch.object(CloseRecordManager, "_batch_lock_loop", None),
            patch.object(CloseRecordManager, "_record_close_batch") as write_batch,
        ):
            await CloseRecordManager.flush_pending_records()

            write_batch.assert_called_once_with(expected)
            self.assertEqual(CloseRecordManager._pending_records, [])


class AutoAProcessingCharacterizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_position_takes_priority_over_observation(self):
        position = AutoADailyPositionValuationTest.make_position().model_dump()
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.BUY,
            strategy=[],
            name="测试股票",
        ).model_dump()
        fixed_now = pd.Timestamp("2026-07-13 10:00:00").to_pydatetime()

        class FixedDateTime:
            @classmethod
            def today(cls):
                return fixed_now

        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {"000001": position},
                "OBSERVATIONS": {"000001": observation},
            }),
            patch.object(AUTOA, "zt_dates", ["2026-07-13"]),
            patch.object(AUTOA, "_batch_window_id", None),
            patch.object(AUTOA, "on_positions", new=AsyncMock()) as on_positions,
            patch.object(AUTOA, "on_observations", new=AsyncMock()) as on_observations,
            patch("tokenDemo.autoTrade_pm.datetime.datetime", FixedDateTime),
        ):
            await AUTOA.filter_stocks()

        on_positions.assert_awaited_once()
        on_observations.assert_not_awaited()


class AutoBNCharacterizationTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_autobn():
        obj = AUTOBN.__new__(AUTOBN)
        obj._long_short_ratio_cache = {}
        obj.logger = MagicMock()
        obj.market_client = SimpleNamespace(
            rest_api=SimpleNamespace(
                long_short_ratio=MagicMock(),
                exchange_information=MagicMock(),
            )
        )
        obj.papi_client = SimpleNamespace(
            rest_api=SimpleNamespace(query_um_position_information=MagicMock())
        )
        obj.alert_all = {"POSITIONS": {}}
        obj.symbols_info = {}
        obj._exchange_info_cache = None
        obj._exchange_info_cache_timestamp = 0.0
        obj._http_session = None
        return obj

    @staticmethod
    def make_position(
        position_side=PositionSide.LONG,
        entry_price=10,
        take_profit=20,
        stop_loss=5,
        stop_guard_threshold=0,
    ):
        return Position(
            take_profit=take_profit,
            stop_loss=stop_loss,
            close_side=(
                OrderSide.SELL
                if position_side == PositionSide.LONG
                else OrderSide.BUY
            ),
            position_side=position_side,
            entry_price=entry_price,
            name="BTCUSDT",
            date=20260701,
            strategy=[PositionSide.BZ],
            stop_guard_threshold=stop_guard_threshold,
        )

    @staticmethod
    def make_kline(previous_close, current_close):
        return [
            [0, 10, 11, 9, 10, 100],
            [0, 10, 11, 9, 10, 100],
            [0, 10, 11, 9, previous_close, 100],
            [0, 10, 11, 9, current_close, 100],
        ]

    async def run_position(self, obj, position, kline):
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {},
        }
        obj.get_kline = AsyncMock(return_value=kline)
        obj.calculate_atr = MagicMock(return_value=1)
        obj.close_bn_position = AsyncMock()
        obj.get_long_short_ratio = AsyncMock(return_value=[])
        obj._get_oi_5m_data = AsyncMock(return_value=[])
        obj.open_bn_position = AsyncMock(return_value=False)
        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

    async def test_long_stop_loss_uses_current_price_directly(self):
        obj = self.make_autobn()
        position = self.make_position(stop_loss=10)

        await self.run_position(obj, position, self.make_kline(11, 9))

        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(obj.close_bn_position.await_args.args[-1], 1)
        obj.get_long_short_ratio.assert_not_awaited()

    async def test_short_stop_loss_uses_current_price_directly(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            take_profit=5,
            stop_loss=10,
        )

        await self.run_position(obj, position, self.make_kline(9, 11))

        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(obj.close_bn_position.await_args.args[-1], 1)
        obj.get_long_short_ratio.assert_not_awaited()

    async def test_long_oi_stop_uses_ratio_over_one_even_when_losing(self):
        obj = self.make_autobn()
        position = self.make_position(
            entry_price=12,
            stop_guard_threshold=100,
        )
        await self.run_position(obj, position, self.make_kline(10, 11))
        obj.get_long_short_ratio.reset_mock()
        obj._get_oi_5m_data.reset_mock()
        obj.close_bn_position.reset_mock()
        obj.get_long_short_ratio.return_value = [{"longShortRatio": "1.1"}]
        obj._get_oi_5m_data.return_value = [{"sumOpenInterest": "90"}]

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.get_long_short_ratio.assert_awaited_once_with("BTCUSDT")
        obj._get_oi_5m_data.assert_awaited_once_with("BTCUSDT")
        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(obj.close_bn_position.await_args.args[1].close_reason, "OI止损")

    async def test_long_oi_stop_skips_oi_when_ratio_not_over_one(self):
        obj = self.make_autobn()
        position = self.make_position(stop_guard_threshold=100)
        await self.run_position(obj, position, self.make_kline(10, 10))
        obj.get_long_short_ratio.reset_mock()
        obj._get_oi_5m_data.reset_mock()
        obj.close_bn_position.reset_mock()
        obj.get_long_short_ratio.return_value = [{"longShortRatio": "1.0"}]

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.get_long_short_ratio.assert_awaited_once_with("BTCUSDT")
        obj._get_oi_5m_data.assert_not_awaited()

    async def test_take_profit_skips_ratio_oi_and_position_management(self):
        obj = self.make_autobn()
        position = self.make_position(take_profit=11, stop_loss=5)

        await self.run_position(obj, position, self.make_kline(10, 11))

        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(obj.close_bn_position.await_args.args[-1], obj.PARTIAL_CLOSE_RATIO)
        obj.get_long_short_ratio.assert_not_awaited()
        obj._get_oi_5m_data.assert_not_awaited()
        obj.open_bn_position.assert_not_awaited()

    async def test_oi_stop_keeps_priority_over_long_short_ratio_stop(self):
        obj = self.make_autobn()
        position = self.make_position(stop_guard_threshold=100)
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {},
        }
        obj.get_kline = AsyncMock(return_value=self.make_kline(10, 10))
        obj.calculate_atr = MagicMock(return_value=1)
        obj.close_bn_position = AsyncMock()
        obj.get_long_short_ratio = AsyncMock(
            return_value=[{"longShortRatio": "9.0"}]
        )
        obj._get_oi_5m_data = AsyncMock(
            return_value=[{"sumOpenInterest": "90"}]
        )
        obj.open_bn_position = AsyncMock(return_value=False)

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(obj.close_bn_position.await_args.args[1].close_reason, "OI止损")
        obj.open_bn_position.assert_not_awaited()

    async def test_failed_long_dca_removes_appended_strategy_and_writes_back(self):
        obj = self.make_autobn()
        position = self.make_position(entry_price=12, take_profit=20, stop_loss=5)

        await self.run_position(obj, position, self.make_kline(10, 10))

        obj.open_bn_position.assert_awaited_once()
        stored = Position.model_validate(obj.alert_all["POSITIONS"]["BTCUSDT"])
        self.assertEqual(stored.strategy, [PositionSide.BZ])

    async def test_failed_short_dca_removes_appended_strategy_and_writes_back(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=8,
            take_profit=5,
            stop_loss=15,
        )

        await self.run_position(obj, position, self.make_kline(10, 10))

        obj.open_bn_position.assert_awaited_once()
        stored = Position.model_validate(obj.alert_all["POSITIONS"]["BTCUSDT"])
        self.assertEqual(stored.strategy, [PositionSide.BZ])

    async def test_second_long_dca_uses_quarter_atr_take_profit_distance(self):
        obj = self.make_autobn()
        position = self.make_position(entry_price=12, take_profit=20, stop_loss=5)
        position.strategy.append(PositionSide.DCA)
        obj.open_bn_position = AsyncMock(return_value=True)
        obj.get_amount_close = AsyncMock(return_value=(1, 10))
        obj.send_msg = AsyncMock()

        await obj._manage_long_position(position.name, position, 2, 8, 20, 5, 1)

        self.assertEqual(position.entry_price, 10)
        self.assertEqual(position.take_profit, 10.5)

    async def test_second_short_dca_uses_quarter_atr_take_profit_distance(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=8,
            take_profit=5,
            stop_loss=15,
        )
        position.strategy.append(PositionSide.DCA)
        obj.open_bn_position = AsyncMock(return_value=True)
        obj.get_amount_close = AsyncMock(return_value=(1, 10))
        obj.send_msg = AsyncMock()

        await obj._manage_short_position(position.name, position, 2, 12, 20, 5, 1)

        self.assertEqual(position.entry_price, 10)
        self.assertEqual(position.take_profit, 9.5)

    async def test_existing_long_dca_recalculates_take_profit_with_current_atr(self):
        obj = self.make_autobn()
        position = self.make_position(entry_price=10, take_profit=20, stop_loss=5)
        position.strategy.extend([PositionSide.DCA, PositionSide.DCA])

        await obj._manage_long_position(position.name, position, 2, 10, 30, 5, 1)

        self.assertEqual(position.take_profit, 10.5)

    async def test_existing_short_dca_recalculates_take_profit_with_current_atr(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=10,
            take_profit=1,
            stop_loss=15,
        )
        position.strategy.extend([PositionSide.DCA, PositionSide.DCA])

        await obj._manage_short_position(position.name, position, 2, 10, 20, 0, 1)

        self.assertEqual(position.take_profit, 9.5)

    async def test_long_without_dca_keeps_original_dynamic_take_profit(self):
        obj = self.make_autobn()
        position = self.make_position(entry_price=10, take_profit=20, stop_loss=5)

        await obj._manage_long_position(position.name, position, 2, 10, 30, 5, 1)

        self.assertEqual(position.take_profit, 19.999)

    async def test_short_without_dca_keeps_original_dynamic_take_profit(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=10,
            take_profit=1,
            stop_loss=15,
        )

        await obj._manage_short_position(position.name, position, 2, 10, 20, 0, 1)

        self.assertEqual(position.take_profit, 1.0009)

    async def test_cached_hour_ratio_still_requests_five_minute_ratio(self):
        obj = self.make_autobn()
        obj._long_short_ratio_cache["BTCUSDT"] = {
            "data": [{"longShortRatio": "1.1"}],
            "timestamp": 100,
        }
        obj._call_api = AsyncMock(
            return_value=[{"longShortRatio": "1.2", "timestamp": 101}]
        )

        with patch("tokenDemo.autoTrade_pm.time.time", return_value=101):
            result = await obj.get_long_short_ratio("BTCUSDT")

        obj._call_api.assert_awaited_once_with(
            obj.market_client.rest_api.long_short_ratio,
            symbol="BTCUSDT",
            period="5m",
            limit=1,
        )
        self.assertEqual(len(result), 2)

    async def test_five_minute_ratio_rejects_data_older_than_five_minutes(self):
        obj = self.make_autobn()
        obj._call_api = AsyncMock(
            side_effect=[
                [{"longShortRatio": "1.1"}],
                [{"longShortRatio": "1.2", "timestamp": 699}],
            ]
        )

        with patch("tokenDemo.autoTrade_pm.time.time", return_value=1000):
            result = await obj.get_long_short_ratio("BTCUSDT", force_refresh=True)

        self.assertEqual(result, [{"longShortRatio": "1.1"}])
        self.assertEqual(obj._call_api.await_count, 2)

    async def test_five_minute_ratio_accepts_exact_boundary(self):
        obj = self.make_autobn()
        obj._call_api = AsyncMock(
            side_effect=[
                [{"longShortRatio": "1.1"}],
                [{"longShortRatio": "1.2", "timestamp": 700}],
            ]
        )

        with patch("tokenDemo.autoTrade_pm.time.time", return_value=1000):
            result = await obj.get_long_short_ratio("BTCUSDT", force_refresh=True)

        self.assertEqual(len(result), 2)

    async def test_five_minute_ratio_uses_time_after_requests(self):
        obj = self.make_autobn()
        obj._call_api = AsyncMock(
            side_effect=[
                [{"longShortRatio": "1.1"}],
                [
                    {
                        "longShortRatio": "1.2",
                        "timestamp": 1_700_000_300_000,
                    }
                ],
            ]
        )

        with patch(
            "tokenDemo.autoTrade_pm.time.time",
            side_effect=[1_700_000_299, 1_700_000_301],
        ):
            result = await obj.get_long_short_ratio("BTCUSDT", force_refresh=True)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["longShortRatio"], "1.2")

    async def test_http_session_is_reused_and_closed_idempotently(self):
        obj = self.make_autobn()
        first = await obj._get_http_session()
        second = await obj._get_http_session()
        self.assertIs(first, second)

        await obj.close_http_session()
        await obj.close_http_session()
        self.assertTrue(first.closed)
        self.assertIsNone(obj._http_session)

    async def test_exchange_info_is_reused_within_ttl(self):
        obj = self.make_autobn()
        exchange_info = {"symbols": []}
        obj._call_api = AsyncMock(return_value=exchange_info)

        with patch("tokenDemo.autoTrade_pm.time.time", side_effect=[100, 101]):
            first = await obj.get_exchange_info()
            second = await obj.get_exchange_info()

        self.assertIs(first, second)
        obj._call_api.assert_awaited_once()

    async def test_exchange_info_refreshes_after_ttl(self):
        obj = self.make_autobn()
        obj._call_api = AsyncMock(side_effect=[{"symbols": []}, {"symbols": []}])

        with patch(
            "tokenDemo.autoTrade_pm.time.time",
            side_effect=[100, 100 + obj.EXCHANGE_INFO_CACHE_TTL + 1],
        ):
            await obj.get_exchange_info()
            await obj.get_exchange_info()

        self.assertEqual(obj._call_api.await_count, 2)

    def test_supplied_exchange_info_does_not_fetch_remotely(self):
        obj = self.make_autobn()
        exchange_info = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "quantityPrecision": 3,
                "quotePrecision": 2,
                "quoteAsset": "USDT",
                "status": "TRADING",
            }]
        }

        obj.get_symbols_info(exchange_info)

        obj.market_client.rest_api.exchange_information.assert_not_called()
        self.assertIn("BTCUSDT", obj.symbols_info)

    def test_supplied_position_risk_does_not_fetch_remotely(self):
        obj = self.make_autobn()
        position_risk = [{
            "symbol": "BTCUSDT",
            "entryPrice": "100",
            "markPrice": "101",
            "positionAmt": "1",
            "notional": "101",
            "unRealizedProfit": "1",
            "positionSide": "LONG",
            "maintMargin": "0.4",
        }]

        result = obj.get_position_risk(position_risk)

        obj.papi_client.rest_api.query_um_position_information.assert_not_called()
        self.assertIn("BTCUSDT", result)


class AutoAHttpSessionCharacterizationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        if AUTOA._http_session is not None and not AUTOA._http_session.closed:
            await AUTOA._http_session.close()
        AUTOA._http_session = None

    async def test_get_http_session_reuses_open_session(self):
        AUTOA._http_session = None

        first = await AUTOA._get_http_session()
        second = await AUTOA._get_http_session()

        self.assertIs(first, second)

        await AUTOA.close_http_session()
        await AUTOA.close_http_session()
        self.assertTrue(first.closed)
        self.assertIsNone(AUTOA._http_session)


if __name__ == "__main__":
    unittest.main()
