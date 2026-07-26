import asyncio
import tempfile
import unittest
from decimal import Decimal
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
        self.assertIsNone(observation.earliest_open_timestamp)

    def test_reopen_timestamp_persists_and_old_json_defaults_to_none(self):
        old_observation = Observation.model_validate({
            "price": 10,
            "timestamp": 1,
            "side": "BUY",
            "strategy": ["BZ"],
            "name": "测试股票",
        })
        self.assertIsNone(old_observation.earliest_open_timestamp)

        old_observation.earliest_open_timestamp = 12345.5
        restored = Observation.model_validate(old_observation.model_dump())
        self.assertEqual(restored.earliest_open_timestamp, 12345.5)

    def test_reopen_cooldown_uses_strict_timestamp_boundary(self):
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="测试股票",
            earliest_open_timestamp=100,
        )

        self.assertTrue(observation.is_reopen_cooldown_active(99.999))
        self.assertFalse(observation.is_reopen_cooldown_active(100))


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


class AutoAReopenCooldownTest(unittest.IsolatedAsyncioTestCase):
    async def test_following_trading_days_skip_weekend_and_market_holiday(self):
        calendar = pd.DataFrame({
            "trade_date": [
                "2026-09-30",
                "2026-10-09",
                "2026-10-12",
                "2026-10-13",
            ]
        })
        with patch(
            "tokenDemo.autoTrade_pm.ak.tool_trade_date_hist_sina",
            return_value=calendar,
        ):
            following = await AUTOA.get_following_trading_days(
                pd.Timestamp("2026-09-30").to_pydatetime()
            )

        self.assertEqual(following, ["2026-10-09", "2026-10-12"])

    async def test_reopen_timestamp_is_second_following_trading_day(self):
        with patch.object(
            AUTOA,
            "get_following_trading_days",
            new=AsyncMock(return_value=["2026-07-23", "2026-07-24"]),
        ):
            timestamp = await AUTOA._get_reopen_timestamp_after_close(
                pd.Timestamp("2026-07-22").to_pydatetime()
            )

        self.assertEqual(
            timestamp,
            pd.Timestamp("2026-07-24").to_pydatetime().timestamp(),
        )

    async def test_cooldown_returns_before_loading_market_data(self):
        observation = Observation(
            price=10,
            timestamp=pd.Timestamp("2026-07-01").timestamp(),
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="测试股票",
            earliest_open_timestamp=pd.Timestamp("2026-07-24").timestamp(),
        )
        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {},
                "OBSERVATIONS": {"000001": observation.model_dump()},
            }),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock()) as stock_hist,
        ):
            await AUTOA.on_observations(
                "000001",
                ["2026-07-23", "2026-07-22"],
                observation.model_dump(),
                pd.Timestamp("2026-07-23 10:00").to_pydatetime(),
            )

        stock_hist.assert_not_awaited()
    async def test_bz_n_open_preserves_shared_observation_timestamp(self):
        timestamp = pd.Timestamp("2026-07-01").timestamp()
        observation = Observation(
            price=10,
            timestamp=timestamp,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="测试股票",
            bz_reference_high=10,
        )
        hist = pd.DataFrame([
            {
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 100,
            }
            for _ in range(29)
        ] + [{
            "open": 12,
            "high": 13,
            "low": 11,
            "close": 12.5,
            "volume": 90,
        }])
        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {},
                "OBSERVATIONS": {"000001": observation.model_dump()},
            }),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(AUTOA, "check_gap_up_after_bz_reference", return_value=True),
            patch.object(AUTOA, "calculate_atr", return_value=1),
            patch.object(AUTOA, "send_msg", new=AsyncMock()),
        ):
            await AUTOA.on_observations(
                "000001",
                ["2026-07-02", "2026-07-01"],
                observation.model_dump(),
                pd.Timestamp("2026-07-02 10:00").to_pydatetime(),
            )
            stored = Observation.model_validate(
                AUTOA.alert_all["OBSERVATIONS"]["000001"]
            )
            has_position = "000001" in AUTOA.alert_all["POSITIONS"]

        self.assertEqual(stored.strategy, [PositionSide.BZ, PositionSide.N])
        self.assertEqual(stored.timestamp, timestamp)
        self.assertTrue(has_position)


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

    async def test_close_writes_second_following_trading_day_cooldown(self):
        position = self.make_position(strategies=[PositionSide.BZ])
        observation = Observation(
            price=10,
            timestamp=pd.Timestamp("2026-07-01").timestamp(),
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="测试股票",
        )
        hist = pd.DataFrame([
            {"high": 11, "low": 9, "close": 10, "volume": 100},
            {"high": 13, "low": 11, "close": 12, "volume": 100},
        ])
        expected_timestamp = pd.Timestamp("2026-07-24").to_pydatetime().timestamp()
        with (
            patch.object(AUTOA, "alert_all", {
                "POSITIONS": {"000001": position.model_dump()},
                "OBSERVATIONS": {"000001": observation.model_dump()},
            }),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(
                AUTOA,
                "_get_reopen_timestamp_after_close",
                new=AsyncMock(return_value=expected_timestamp),
            ),
            patch.object(AUTOA, "send_msg", new=AsyncMock()),
            patch.object(
                CloseRecordManager,
                "record_close_async",
                new=AsyncMock(),
            ),
        ):
            await AUTOA.on_positions(
                "000001",
                ["2026-07-22", "2026-07-21"],
                position.model_dump(),
                pd.Timestamp("2026-07-22 15:00").to_pydatetime(),
            )
            stored = Observation.model_validate(
                AUTOA.alert_all["OBSERVATIONS"]["000001"]
            )

        self.assertNotIn("000001", AUTOA.alert_all["POSITIONS"])
        self.assertEqual(stored.timestamp, observation.timestamp)
        self.assertEqual(stored.earliest_open_timestamp, expected_timestamp)

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

    async def test_auction_price_prefers_sina_intraday_quote(self):
        trading_days = ["20260711", "20260710"]
        with (
            patch.object(
                AUTOA,
                "_get_sina_intraday_price",
                new=AsyncMock(return_value=10.8),
            ) as sina_price,
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock()) as stock_hist,
        ):
            price = await AUTOA._get_auction_price("000001", trading_days)

        self.assertEqual(price, 10.8)
        sina_price.assert_awaited_once_with("000001")
        stock_hist.assert_not_awaited()

    async def test_auction_prices_still_fetch_each_stock_independently(self):
        trading_days = ["20260711", "20260710"]
        hist = pd.DataFrame([{"close": 10.5}])
        with (
            patch.object(
                AUTOA,
                "_get_sina_intraday_price",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)
            ) as stock_hist,
        ):
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

    async def test_short_position_ignores_low_long_short_ratio(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=10,
            take_profit=5,
            stop_loss=15,
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {},
        }
        obj.get_kline = AsyncMock(return_value=self.make_kline(10, 10))
        obj.calculate_atr = MagicMock(return_value=1)
        obj.close_bn_position = AsyncMock()
        obj.get_long_short_ratio = AsyncMock(
            return_value=[{"longShortRatio": "1.0"}]
        )
        obj._get_oi_5m_data = AsyncMock(return_value=[])
        obj.open_bn_position = AsyncMock(return_value=False)

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.close_bn_position.assert_not_awaited()
        obj._get_oi_5m_data.assert_not_awaited()

    async def test_short_position_ignores_high_long_short_ratio(self):
        obj = self.make_autobn()
        position = self.make_position(
            position_side=PositionSide.SHORT,
            entry_price=10,
            take_profit=5,
            stop_loss=15,
        )
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
        obj._get_oi_5m_data = AsyncMock(return_value=[])
        obj.open_bn_position = AsyncMock(return_value=False)

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.close_bn_position.assert_not_awaited()

    async def test_long_position_still_stops_on_high_long_short_ratio(self):
        obj = self.make_autobn()
        position = self.make_position(stop_guard_threshold=0)
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
        obj._get_oi_5m_data = AsyncMock(return_value=[])
        obj.open_bn_position = AsyncMock(return_value=False)

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.close_bn_position.assert_awaited_once()
        self.assertEqual(
            obj.close_bn_position.await_args.args[1].close_reason, "多空比止损"
        )

    async def test_zero_exchange_position_writes_24_hour_cooldown(self):
        obj = self.make_autobn()
        position = self.make_position()
        observation = Observation(
            price=10,
            timestamp=900,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.get_amount_close = AsyncMock(return_value=(0, 0))
        obj.send_msg = AsyncMock()
        with patch("tokenDemo.autoTrade_pm.time.time", return_value=1000):
            await obj.close_bn_position("BTCUSDT", position, 0, 10)

        stored = Observation.model_validate(
            obj.alert_all["OBSERVATIONS"]["BTCUSDT"]
        )
        self.assertEqual(stored.timestamp, observation.timestamp)
        self.assertEqual(
            stored.earliest_open_timestamp,
            1000 + obj.REOPEN_COOLDOWN_SECONDS,
        )
        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])

    async def test_bz_close_after_order_keeps_observation_and_sets_cooldown(self):
        obj = self.make_autobn()
        position = self.make_position()
        observation = Observation(
            price=10,
            timestamp=900,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.symbols_info = {"BTCUSDT": {"quantityPrecision": Decimal("0.001")}}
        obj.get_amount_close = AsyncMock(side_effect=[(10, 10), (0, 0)])
        obj.papi_client.rest_api.new_um_order = MagicMock()
        obj._call_api = AsyncMock(return_value={"origQty": "10"})
        obj.send_msg = AsyncMock()
        with (
            patch.object(CloseRecordManager, "record_close_async", new=AsyncMock()),
            patch("tokenDemo.autoTrade_pm.time.time", return_value=1000),
        ):
            await obj.close_bn_position("BTCUSDT", position, 0, 10)

        stored = Observation.model_validate(
            obj.alert_all["OBSERVATIONS"]["BTCUSDT"]
        )
        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertEqual(stored.timestamp, observation.timestamp)
        self.assertEqual(
            stored.earliest_open_timestamp,
            1000 + obj.REOPEN_COOLDOWN_SECONDS,
        )

    async def test_bz_zero_position_without_observation_still_clears_position(self):
        obj = self.make_autobn()
        position = self.make_position()
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {},
        }
        obj.get_amount_close = AsyncMock(return_value=(0, 0))
        obj.send_msg = AsyncMock()

        await obj.close_bn_position("BTCUSDT", position, 0, 10)

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertNotIn("BTCUSDT", obj.alert_all["OBSERVATIONS"])

    async def test_expired_bz_observation_is_removed_on_full_close(self):
        obj = self.make_autobn()
        position = self.make_position()
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.get_amount_close = AsyncMock(return_value=(0, 0))
        obj.send_msg = AsyncMock()
        close_time = 1 + obj.BZ_OBSERVATION_TIMEOUT_SECONDS + 1

        with patch("tokenDemo.autoTrade_pm.time.time", return_value=close_time):
            await obj.close_bn_position("BTCUSDT", position, 0, 10)

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertNotIn("BTCUSDT", obj.alert_all["OBSERVATIONS"])

    async def test_bd_zero_exchange_position_removes_observation(self):
        obj = self.make_autobn()
        position = self.make_position(position_side=PositionSide.SHORT)
        position.strategy = [PositionSide.BD]
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.SELL,
            strategy=[PositionSide.BD],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.get_amount_close = AsyncMock(return_value=(0, 0))
        obj.send_msg = AsyncMock()

        await obj.close_bn_position("BTCUSDT", position, 0, 10)

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertNotIn("BTCUSDT", obj.alert_all["OBSERVATIONS"])

    async def test_bd_close_removes_observation_after_order_confirms_zero(self):
        obj = self.make_autobn()
        position = self.make_position(position_side=PositionSide.SHORT)
        position.strategy = [PositionSide.BD]
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.SELL,
            strategy=[PositionSide.BD],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.symbols_info = {"BTCUSDT": {"quantityPrecision": Decimal("0.001")}}
        obj.get_amount_close = AsyncMock(side_effect=[(10, 10), (0, 0)])
        obj.papi_client.rest_api.new_um_order = MagicMock()
        obj._call_api = AsyncMock(return_value={"origQty": "10"})
        obj.send_msg = AsyncMock()
        with patch.object(CloseRecordManager, "record_close_async", new=AsyncMock()):
            await obj.close_bn_position("BTCUSDT", position, 0, 10)

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertNotIn("BTCUSDT", obj.alert_all["OBSERVATIONS"])

    async def test_bd_close_removes_observation_after_error_confirms_zero(self):
        obj = self.make_autobn()
        position = self.make_position(position_side=PositionSide.SHORT)
        position.strategy = [PositionSide.BD]
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.SELL,
            strategy=[PositionSide.BD],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.symbols_info = {"BTCUSDT": {"quantityPrecision": Decimal("0.001")}}
        obj.get_amount_close = AsyncMock(side_effect=[(10, 10), (0, 0)])
        obj.papi_client.rest_api.new_um_order = MagicMock()
        obj._call_api = AsyncMock(side_effect=RuntimeError("order status unknown"))
        obj.send_msg = AsyncMock()
        with (
            patch("tokenDemo.autoTrade_pm.asyncio.sleep", new=AsyncMock()),
            patch.object(obj.logger, "exception"),
        ):
            await obj.close_bn_position("BTCUSDT", position, 0, 10)

        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertNotIn("BTCUSDT", obj.alert_all["OBSERVATIONS"])

    async def test_partial_bd_close_keeps_observation_unchanged(self):
        obj = self.make_autobn()
        position = self.make_position(position_side=PositionSide.SHORT)
        position.strategy = [PositionSide.BD]
        observation = Observation(
            price=10,
            timestamp=1,
            side=OrderSide.SELL,
            strategy=[PositionSide.BD],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.symbols_info = {"BTCUSDT": {"quantityPrecision": Decimal("0.001")}}
        obj.get_amount_close = AsyncMock(side_effect=[(10, 10), (3, 10)])
        obj.papi_client.rest_api.new_um_order = MagicMock()
        obj._call_api = AsyncMock(return_value={"origQty": "7"})
        obj.send_msg = AsyncMock()
        obj.calc_stop_profit_loss = MagicMock(return_value=(8, 12))
        with patch.object(CloseRecordManager, "record_close_async", new=AsyncMock()):
            await obj.close_bn_position("BTCUSDT", position, 1, 10, 0.7)

        self.assertIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertEqual(
            obj.alert_all["OBSERVATIONS"]["BTCUSDT"], observation.model_dump()
        )

    async def test_strategy_specific_observation_expiration(self):
        current = pd.Timestamp("2026-07-11 10:00:00").to_pydatetime()
        old_timestamp = current.timestamp() - 2 * 24 * 60 * 60

        for strategies, should_remain in (
            ([PositionSide.BZ], False),
            ([PositionSide.BD], True),
            ([PositionSide.BZ, PositionSide.BD], False),
        ):
            with self.subTest(strategies=strategies):
                obj = self.make_autobn()
                observation = Observation(
                    price=10,
                    timestamp=old_timestamp,
                    side=(
                        OrderSide.BUY
                        if PositionSide.BZ in strategies
                        else OrderSide.SELL
                    ),
                    strategy=strategies,
                    name="BTCUSDT",
                )
                obj.alert_all = {
                    "POSITIONS": {},
                    "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
                }
                obj.get_kline = AsyncMock(
                    return_value=[
                        [0, 10, 11, 9, 10, 100],
                        [0, 10, 11, 9, 10, 100],
                        [0, 10, 11, 9, 10, 100],
                        [0, 10, 11, 9, 10, 50],
                    ]
                )
                obj._is_bd_observation = AsyncMock(return_value=False)

                await obj.rzq_token(
                    asyncio.Semaphore(1), "BTCUSDT", set(), current
                )

                self.assertEqual(
                    "BTCUSDT" in obj.alert_all["OBSERVATIONS"], should_remain
                )

    async def test_successful_initial_open_preserves_observation_timestamp(self):
        for side, strategy, current_close in (
            (OrderSide.BUY, PositionSide.BZ, 11),
            (OrderSide.SELL, PositionSide.BD, 9),
        ):
            with self.subTest(strategy=strategy):
                obj = self.make_autobn()
                observation = Observation(
                    price=10,
                    timestamp=pd.Timestamp("2026-07-11 09:00:00").timestamp(),
                    side=side,
                    strategy=[strategy],
                    name="BTCUSDT",
                )
                obj.alert_all = {
                    "POSITIONS": {},
                    "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
                }
                obj.get_kline = AsyncMock(
                    return_value=self.make_kline(10, current_close)
                )
                obj.check_side = AsyncMock(return_value=(True, None, None))
                obj.calculate_atr = MagicMock(return_value=1)
                obj.calc_stop_profit_loss = MagicMock(
                    return_value=(12, 8) if side == OrderSide.BUY else (8, 12)
                )
                obj.get_basis_rate = AsyncMock(return_value=0)
                obj.signal_qy_key = "test-key"
                obj.send_msg = AsyncMock()
                obj.open_bn_position = AsyncMock(return_value=True)

                await obj.rzq_token(
                    asyncio.Semaphore(1),
                    "BTCUSDT",
                    set(),
                    pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
                )

                stored = Observation.model_validate(
                    obj.alert_all["OBSERVATIONS"]["BTCUSDT"]
                )
                self.assertEqual(stored.timestamp, observation.timestamp)
                self.assertIn("BTCUSDT", obj.alert_all["POSITIONS"])

    async def test_atr_initialization_preserves_existing_observation(self):
        obj = self.make_autobn()
        position = self.make_position(take_profit=0, stop_loss=0)
        observation = Observation(
            price=9,
            timestamp=123,
            side=OrderSide.BUY,
            strategy=[PositionSide.BZ],
            name="BTCUSDT",
            bz_reference_high=11,
            earliest_open_timestamp=456,
        )
        obj.alert_all = {
            "POSITIONS": {"BTCUSDT": position.model_dump()},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.calculate_atr = MagicMock(return_value=1)
        obj.calc_stop_profit_loss = MagicMock(return_value=(12, 8))
        obj.get_long_short_ratio = AsyncMock(return_value=[])
        obj._get_oi_5m_data = AsyncMock(return_value=[])
        obj.open_bn_position = AsyncMock(return_value=False)

        await obj._manage_position(
            "BTCUSDT",
            position,
            observation,
            self.make_kline(10, 10),
            10,
            999,
        )

        self.assertEqual(
            obj.alert_all["OBSERVATIONS"]["BTCUSDT"], observation.model_dump()
        )
        stored_position = Position.model_validate(
            obj.alert_all["POSITIONS"]["BTCUSDT"]
        )
        self.assertGreater(stored_position.take_profit, 0)
        self.assertGreater(stored_position.stop_loss, 0)

    async def test_failed_initial_open_does_not_create_local_position(self):
        obj = self.make_autobn()
        observation = Observation(
            price=10,
            timestamp=pd.Timestamp("2026-07-11 09:00:00").timestamp(),
            side=OrderSide.SELL,
            strategy=[PositionSide.BD],
            name="BTCUSDT",
        )
        obj.alert_all = {
            "POSITIONS": {},
            "OBSERVATIONS": {"BTCUSDT": observation.model_dump()},
        }
        obj.get_kline = AsyncMock(
            return_value=[
                [0, 10, 11, 9, 10, 100] for _ in range(obj.MIN_KLINE_FOR_ANALYSIS - 1)
            ]
            + [[0, 9, 10, 8, 9, 100]]
        )
        obj.check_side = AsyncMock(return_value=(True, None, None))
        obj.calculate_atr = MagicMock(return_value=1)
        obj.calc_stop_profit_loss = MagicMock(return_value=(8, 10))
        obj.get_basis_rate = AsyncMock(return_value=0)
        obj.signal_qy_key = "test-key"
        obj.send_msg = AsyncMock()
        obj.open_bn_position = AsyncMock(return_value=None)

        await obj.rzq_token(
            __import__("asyncio").Semaphore(1),
            "BTCUSDT",
            set(),
            pd.Timestamp("2026-07-11 10:00:00").to_pydatetime(),
        )

        obj.open_bn_position.assert_awaited_once()
        self.assertNotIn("BTCUSDT", obj.alert_all["POSITIONS"])
        self.assertEqual(
            obj.alert_all["OBSERVATIONS"]["BTCUSDT"], observation.model_dump()
        )

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


class AutoBNShortSignalTest(unittest.IsolatedAsyncioTestCase):
    """BD做空信号 v3：入池三条件 + 扣扳机OI回撤"""

    @staticmethod
    def make_autobn(oi_window=None, completed_oi=None):
        obj = AUTOBN.__new__(AUTOBN)
        obj.logger = MagicMock()
        obj._get_bd_oi_windows = AsyncMock(
            return_value=(oi_window, completed_oi)
        )
        return obj

    @staticmethod
    def make_oi_window(old_peak=130, recent_peak=140):
        """前20根基线 + 中间7根旧成本OI + 最近3根高位OI。"""
        baseline = [100 + i % 3 for i in range(20)]
        old = [100] * 6 + [old_peak]
        recent = [110, 115, recent_peak]
        return baseline + old + recent

    @staticmethod
    def make_klines(close_high_today=True, vol_peak_age=5):
        close = [10.0] * 29 + [12.0 if close_high_today else 9.0]
        if not close_high_today:
            close[-2] = 12.0
        volume = [100.0] * 30
        volume[29 - vol_peak_age] = 999.0
        return close, volume

    async def test_bd_pool_rejects_when_price_not_at_window_high(self):
        obj = self.make_autobn(self.make_oi_window(), [100] * 30)
        close, volume = self.make_klines(close_high_today=False)

        self.assertFalse(await obj._is_bd_observation("BTCUSDT", close, volume, None))
        obj._get_bd_oi_windows.assert_not_awaited()

    async def test_bd_pool_rejects_fresh_volume_peak(self):
        obj = self.make_autobn(self.make_oi_window(), [100] * 30)
        close, volume = self.make_klines(vol_peak_age=2)

        self.assertFalse(await obj._is_bd_observation("BTCUSDT", close, volume, None))

    async def test_bd_pool_rejects_mild_old_oi_accumulation(self):
        obj = self.make_autobn(
            self.make_oi_window(old_peak=102, recent_peak=103), [100] * 30
        )
        close, volume = self.make_klines()

        self.assertFalse(await obj._is_bd_observation("BTCUSDT", close, volume, None))

    async def test_bd_pool_rejects_recent_oi_not_above_old_peak(self):
        obj = self.make_autobn(
            self.make_oi_window(old_peak=130, recent_peak=130), [100] * 30
        )
        close, volume = self.make_klines()

        self.assertFalse(await obj._is_bd_observation("BTCUSDT", close, volume, None))

    async def test_bd_pool_accepts_two_cohort_structure(self):
        obj = self.make_autobn(self.make_oi_window(), [100] * 30)
        close, volume = self.make_klines()

        self.assertTrue(await obj._is_bd_observation("BTCUSDT", close, volume, None))

    async def test_bd_pool_rejects_when_realtime_oi_window_unavailable(self):
        obj = self.make_autobn(None, None)
        close, volume = self.make_klines()

        self.assertFalse(await obj._is_bd_observation("BTCUSDT", close, volume, None))

    async def run_check_side_short(self, oi_5m_last, oi_1d_peak=100.0):
        realtime_oi = [50.0] * 29 + [oi_5m_last]
        completed_oi = [50.0] * 29 + [oi_1d_peak]
        obj = self.make_autobn(realtime_oi, completed_oi)
        return await obj.check_side(
            asyncio.Semaphore(1),
            "BTCUSDT",
            PositionSide.SHORT.value,
            dtn=pd.Timestamp("2026-07-11 10:00:00", tz="UTC").to_pydatetime(),
        )

    async def test_short_trigger_fires_at_drawdown_threshold(self):
        passed, _, _ = await self.run_check_side_short(90.0)

        self.assertTrue(passed)

    async def test_short_trigger_blocked_when_oi_holds_near_peak(self):
        passed, _, _ = await self.run_check_side_short(91.0)

        self.assertFalse(passed)

    async def test_bd_oi_windows_combine_29_daily_with_fresh_5m(self):
        obj = AUTOBN.__new__(AUTOBN)
        obj._get_oi_1d_data = AsyncMock(
            return_value=[{"sumOpenInterest": str(i)} for i in range(1, 31)]
        )
        dtn = pd.Timestamp("2026-07-25 12:00:00", tz="UTC").to_pydatetime()
        obj._get_oi_5m_data = AsyncMock(return_value=[{
            "sumOpenInterest": "99",
            "timestamp": int((dtn.timestamp() - 60) * 1000),
        }])

        realtime, completed = await obj._get_bd_oi_windows("BTCUSDT", dtn)

        self.assertEqual(realtime, [float(i) for i in range(2, 31)] + [99.0])
        self.assertEqual(completed, [float(i) for i in range(1, 31)])

    async def test_bd_oi_windows_reject_stale_or_future_5m(self):
        obj = AUTOBN.__new__(AUTOBN)
        obj._get_oi_1d_data = AsyncMock(
            return_value=[{"sumOpenInterest": "100"}] * 30
        )
        dtn = pd.Timestamp("2026-07-25 12:00:00", tz="UTC").to_pydatetime()

        for offset in (-obj.OI_5M_CACHE_TTL - 1, 1):
            obj._get_oi_5m_data = AsyncMock(return_value=[{
                "sumOpenInterest": "99",
                "timestamp": int((dtn.timestamp() + offset) * 1000),
            }])
            self.assertEqual(
                await obj._get_bd_oi_windows("BTCUSDT", dtn),
                (None, None),
            )

    async def test_daily_oi_uses_utc_availability_boundary(self):
        obj = AUTOBN.__new__(AUTOBN)
        obj._oi_1d_cache = {}
        boundary = pd.Timestamp("2026-07-25 00:00:00", tz="UTC")
        obj._call_api = AsyncMock(return_value=[
            {"sumOpenInterest": "100", "timestamp": int(boundary.timestamp() * 1000)},
            {"sumOpenInterest": "101", "timestamp": int((boundary.timestamp() + 86400) * 1000)},
        ])
        obj.market_client = MagicMock()

        result = await obj._get_oi_1d_data(
            "BTCUSDT",
            pd.Timestamp("2026-07-25 20:00:00", tz="UTC").to_pydatetime(),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sumOpenInterest"], "100")

    def test_observation_timeouts_are_strategy_specific(self):
        self.assertEqual(
            AUTOBN.BZ_OBSERVATION_TIMEOUT_SECONDS, 24 * 60 * 60
        )
        self.assertEqual(
            AUTOBN.BD_OBSERVATION_TIMEOUT_SECONDS, 7 * 24 * 60 * 60
        )
        self.assertEqual(AUTOA.OBSERVATION_TIMEOUT_SECONDS, 30 * 24 * 60 * 60)


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
