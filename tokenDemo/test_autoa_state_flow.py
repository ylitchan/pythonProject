import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from tokenDemo.autoTrade_pm import AUTOA, CloseRecordManager, Observation, OrderSide, Position, PositionSide


class AutoAStateFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.position = Position(
            take_profit=20, stop_loss=5, close_side=OrderSide.SELL,
            position_side=PositionSide.LONG, entry_price=10, name="测试股票",
            date=20260701, strategy=[PositionSide.BZ, PositionSide.N],
        )
        self.observation = Observation(
            price=5, timestamp=pd.Timestamp("2026-07-01").timestamp(),
            side=OrderSide.BUY, strategy=[PositionSide.BZ, PositionSide.N],
            name="测试股票", bz_reference_high=11,
        )
        self.state = {
            "POSITIONS": {"000001": self.position.model_dump()},
            "OBSERVATIONS": {"000001": self.observation.model_dump()},
        }
        self.enterContext(patch.object(AUTOA, "alert_all", self.state))
        self.enterContext(patch.object(CloseRecordManager, "_pending_records", []))
        self.enterContext(patch.object(CloseRecordManager, "_record_close_batch"))
        self.enterContext(patch.object(AUTOA, "_trading_calendar", None))
        self.enterContext(patch.object(AUTOA, "_calendar_loaded_on", None))
        self.enterContext(patch.object(AUTOA, "hist_cache", {}))

    @staticmethod
    def hist(price):
        return pd.DataFrame([
            {"open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100}
            for _ in range(19)
        ] + [{"open": price + 1, "high": price + 1, "low": price - 0.5,
              "close": price, "volume": 100}])

    async def run_position(self, price):
        with (
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=self.hist(price))),
            patch.object(AUTOA, "calculate_atr", return_value=1),
        ):
            await AUTOA.on_positions(
                "000001", ["2026-07-02", "2026-06-01"],
                self.state["POSITIONS"]["000001"],
                pd.Timestamp("2026-07-02 10:00").to_pydatetime(),
            )

    async def test_calendar_failure_does_not_block_exit(self):
        with (
            patch.object(AUTOA, "_get_reopen_timestamp_after_close", new=AsyncMock(return_value=None)),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send,
        ):
            await self.run_position(4.5)
        self.assertNotIn("000001", self.state["POSITIONS"])
        self.assertEqual(len(CloseRecordManager._pending_records), 1)
        self.assertEqual(self.state["OBSERVATIONS"]["000001"]["reopen_pending_date"], "2026-07-02")
        send.assert_awaited_once()

    async def test_dca_state_precedes_notification_and_survives_cancellation(self):
        async def send_then_cancel(message, **kwargs):
            stored = Position.model_validate(self.state["POSITIONS"]["000001"])
            self.assertEqual(stored.strategy.count(PositionSide.DCA), 1)
            self.assertEqual(stored.entry_price, 9)
            self.assertEqual(stored.take_profit, 9.5)
            self.assertEqual(stored.stop_loss, 5)
            self.assertIn("9.50", message.content)
            raise asyncio.CancelledError()

        with patch.object(AUTOA, "send_msg", new=AsyncMock(side_effect=send_then_cancel)):
            with self.assertRaises(asyncio.CancelledError):
                await self.run_position(8)
        self.assertEqual(self.state["POSITIONS"]["000001"]["entry_price"], 9)

    async def test_close_record_is_queued_before_notification(self):
        async def send_then_cancel(*args, **kwargs):
            self.assertNotIn("000001", self.state["POSITIONS"])
            self.assertEqual(len(CloseRecordManager._pending_records), 1)
            raise asyncio.CancelledError()

        with (
            patch.object(AUTOA, "_get_reopen_timestamp_after_close", new=AsyncMock(return_value=pd.Timestamp("2026-07-06").timestamp())),
            patch.object(AUTOA, "send_msg", new=AsyncMock(side_effect=send_then_cancel)),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.run_position(4.5)
        self.assertEqual(CloseRecordManager._pending_records[0]["平仓数量"], 100)

    async def test_close_screening_snapshot_is_saved_explicitly(self):
        now = pd.Timestamp("2026-07-02 15:05").to_pydatetime()

        class FixedDateTime:
            @classmethod
            def today(cls):
                return now

        hist = self.hist(12.5)
        hist.loc[hist.index[-1], ["open", "high", "low", "volume"]] = [12, 14, 7, 200]
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(AUTOA, "alert_all_file", str(Path(directory) / "state.json")),
            patch.object(AUTOA, "zt_dates", ["2026-07-02", "2026-06-01"]),
            patch.object(AUTOA, "hist_cache", {}),
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(AUTOA, "calculate_chebyshev_probability", return_value={"chebyshev_upper_bound": 0.001}),
            patch("tokenDemo.autoTrade_pm.datetime.datetime", FixedDateTime),
            patch("tokenDemo.autoTrade_pm.ak.stock_zt_pool_em", return_value=pd.DataFrame({
                "代码": ["000001"], "名称": ["测试股票"], "连板数": [1],
            })),
        ):
            await AUTOA.filter_stocks()
            AUTOA.save_state()
            saved = json.loads(Path(AUTOA.alert_all_file).read_text(encoding="utf-8"))
        self.assertEqual(saved["OBSERVATIONS"]["000001"]["price"], 7)
        self.assertEqual(saved["OBSERVATIONS"]["000001"]["timestamp"], now.timestamp())

    async def test_pending_cooldown_survives_restart_and_recovers_from_calendar_failure(self):
        with patch.object(AUTOA, "send_msg", new=AsyncMock()):
            await self.run_position(4.5)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(AUTOA, "alert_all_file", str(Path(directory) / "state.json")),
            patch.object(AUTOA, "zt_dates", []),
            patch.object(AUTOA, "_batch_window_id", None),
            patch.object(AUTOA, "_batch_observations_snapshot", []),
        ):
            AUTOA.save_state()
            AUTOA.load_state(AUTOA.alert_all_file)
            stored = AUTOA.alert_all["OBSERVATIONS"]["000001"]
            calendar = pd.DataFrame({"trade_date": ["2026-07-02", "2026-07-03", "2026-07-06"]})
            with (
                patch("tokenDemo.autoTrade_pm.ak.tool_trade_date_hist_sina",
                      side_effect=[OSError("暂不可用"), calendar]) as get_calendar,
                patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=pd.DataFrame())) as get_hist,
            ):
                now = pd.Timestamp("2026-07-03 10:00").to_pydatetime()
                await AUTOA.on_observations("000001", ["2026-07-03", "2026-07-02"], stored, now)
                self.assertEqual(AUTOA.alert_all["OBSERVATIONS"]["000001"]["reopen_pending_date"], "2026-07-02")
                get_hist.assert_not_awaited()
                await AUTOA.on_observations("000001", ["2026-07-03", "2026-07-02"], stored, now)
                resolved = AUTOA.alert_all["OBSERVATIONS"]["000001"]
                self.assertIsNone(resolved["reopen_pending_date"])
                self.assertEqual(resolved["earliest_open_timestamp"], pd.Timestamp("2026-07-06").to_pydatetime().timestamp())
                get_hist.assert_not_awaited()
                await AUTOA.on_observations(
                    "000001", ["2026-07-06", "2026-07-03"], resolved,
                    pd.Timestamp("2026-07-06 10:00").to_pydatetime(),
                )
                get_hist.assert_awaited_once()
                self.assertEqual(get_calendar.call_count, 2)

    def test_failed_atomic_save_retains_previous_snapshot(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(AUTOA, "alert_all_file", str(Path(directory) / "state.json")),
        ):
            AUTOA.save_state()
            before = Path(AUTOA.alert_all_file).read_bytes()
            self.state["OBSERVATIONS"]["000001"]["price"] = 7
            with patch("tokenDemo.autoTrade_pm.os.replace", side_effect=OSError("文件被占用")):
                with self.assertRaises(OSError):
                    AUTOA.save_state()
            self.assertEqual(Path(AUTOA.alert_all_file).read_bytes(), before)
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["state.json"])

    async def test_cancelled_monitor_flushes_queued_exits_without_periodic_save(self):
        now = pd.Timestamp("2026-07-02 10:00").to_pydatetime()

        class FixedDateTime:
            @classmethod
            def today(cls):
                return now

        async def cancelled_batch(today):
            with patch.object(AUTOA, "send_msg", new=AsyncMock(side_effect=asyncio.CancelledError())):
                await self.run_position(4.5)

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(AUTOA, "alert_all_file", str(Path(directory) / "state.json")),
            patch.object(AUTOA, "zt_dates", ["2026-07-02", "2026-06-01"]),
            patch("tokenDemo.autoTrade_pm.datetime.datetime", FixedDateTime),
            patch.object(AUTOA, "_process_market_batch", side_effect=cancelled_batch),
        ):
            # record time also uses datetime.now().
            FixedDateTime.now = classmethod(lambda cls: now)
            with self.assertRaises(asyncio.CancelledError):
                await AUTOA.monitor_stocks()
            self.assertFalse(Path(AUTOA.alert_all_file).exists())
        CloseRecordManager._record_close_batch.assert_called_once()
        self.assertEqual(CloseRecordManager._pending_records, [])

    async def test_no_open_signal_skips_atr_and_preserves_observation_low(self):
        self.state["POSITIONS"].clear()
        hist = self.hist(10).astype(float)
        hist.loc[hist.index[-1], ["open", "low"]] = [9.9, 4]
        with (
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=hist)),
            patch.object(AUTOA, "calculate_atr") as atr,
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send,
        ):
            await AUTOA.on_observations("000001", ["2026-07-02", "2026-06-01"],
                                       self.observation.model_dump(), pd.Timestamp("2026-07-02 10:00").to_pydatetime())
        self.assertEqual(self.state["OBSERVATIONS"]["000001"]["price"], 4)
        self.assertEqual(self.state["POSITIONS"], {})
        atr.assert_not_called()
        send.assert_not_awaited()

    async def test_quote_parser_returns_ohlcv_from_one_request(self):
        response = MagicMock()
        response.json = AsyncMock(return_value={"result": {"data": [
            {"p": "10", "v": "100", "tot_v": "100"},
            {"p": "9", "v": "200", "tot_v": "300"},
            {"p": "11", "v": "100", "tot_v": "400"},
        ]}})
        session = MagicMock()
        session.get.return_value.__aenter__.return_value = response
        with patch.object(AUTOA, "_get_http_session", new=AsyncMock(return_value=session)):
            bar = await AUTOA._get_sina_daily_bar("000001")
        self.assertEqual(bar, {"open": 10, "high": 11, "low": 9, "close": 11, "volume": 4})
        session.get.assert_called_once()

    async def test_history_cache_keeps_completed_bars_and_refreshes_today(self):
        history = pd.DataFrame({
            "日期": pd.to_datetime(["2026-07-01", "2026-07-02"]),
            "开盘": [10, 11], "最高": [11, 12], "最低": [9, 10],
            "收盘": [10.5, 11.5], "成交量": [100, 100],
        })
        with (
            patch.object(AUTOA, "_get_sina_daily_bar", new=AsyncMock(side_effect=[
                {"open": 12, "high": 13, "low": 11, "close": 12.5, "volume": 200},
                {"open": 12, "high": 14, "low": 10, "close": 13, "volume": 300},
            ])) as current,
            patch("tokenDemo.autoTrade_pm.ak.stock_zh_a_hist", return_value=history) as historical,
        ):
            first = await AUTOA.stock_zh_a_hist("000001", "20260701", "20260702")
            second = await AUTOA.stock_zh_a_hist("000001", "2026-07-01", "2026-07-02")
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)
        self.assertEqual(first.iloc[-1]["low"], 11)
        self.assertEqual(second.iloc[-1]["low"], 10)
        historical.assert_called_once()
        self.assertEqual(current.await_count, 2)

    async def test_monitor_with_unavailable_calendar_exits_using_fresh_daily_history(self):
        now = pd.Timestamp("2026-07-02 10:00").to_pydatetime()

        class FixedDateTime:
            @classmethod
            def today(cls):
                return now

            @classmethod
            def now(cls):
                return now

        history = self.hist(4.5)
        history["date"] = pd.bdate_range(end="2026-07-02", periods=20)
        history = history.rename(columns={"date": "日期", "open": "开盘", "high": "最高",
                                          "low": "最低", "close": "收盘", "volume": "成交量"})
        with (
            patch.object(AUTOA, "zt_dates", []),
            patch.object(AUTOA, "get_last_trading_days", new=AsyncMock(return_value=[])),
            patch.object(AUTOA, "_get_sina_daily_bar", new=AsyncMock(return_value={
                "open": 5, "high": 5, "low": 4, "close": 4.5, "volume": 100,
            })),
            patch("tokenDemo.autoTrade_pm.ak.stock_zh_a_hist", return_value=history),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send,
            patch.object(AUTOA, "save_state"),
            patch.object(AUTOA, "on_observations", new=AsyncMock()) as open_check,
            patch("tokenDemo.autoTrade_pm.datetime.datetime", FixedDateTime),
        ):
            await AUTOA.monitor_stocks()
        self.assertNotIn("000001", self.state["POSITIONS"])
        self.assertEqual(self.state["OBSERVATIONS"]["000001"]["reopen_pending_date"], "2026-07-02")
        CloseRecordManager._record_close_batch.assert_called_once()
        send.assert_awaited_once()
        open_check.assert_not_awaited()

    async def test_calendar_fallback_rejects_previous_day_history(self):
        history = pd.DataFrame({"日期": ["2026-07-01"], "开盘": [5], "最高": [5],
                                "最低": [4], "收盘": [4.5], "成交量": [100]})
        with (
            patch.object(AUTOA, "_get_sina_daily_bar", new=AsyncMock(return_value={
                "open": 5, "high": 5, "low": 4, "close": 4.5, "volume": 100,
            })),
            patch("tokenDemo.autoTrade_pm.ak.stock_zh_a_hist", return_value=history),
        ):
            bars = await AUTOA.stock_zh_a_hist("000001", "2026-06-01", "2026-07-02", require_current_day=True)
        self.assertTrue(bars.empty)

    async def test_calendar_fallback_never_adds_to_positions(self):
        with (
            patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=self.hist(8))) as history,
            patch.object(AUTOA, "calculate_atr", return_value=1),
            patch.object(AUTOA, "send_msg", new=AsyncMock()) as send,
        ):
            await AUTOA.on_positions(
                "000001", ["2026-07-02", "2026-06-01"], self.position.model_dump(),
                pd.Timestamp("2026-07-02 10:00").to_pydatetime(), exit_only=True,
            )
        self.assertEqual(self.state["POSITIONS"]["000001"], self.position.model_dump())
        self.assertTrue(history.await_args.kwargs["require_current_day"])
        send.assert_not_awaited()

    async def test_shutdown_leaves_state_save_to_atexit_and_closes_sessions(self):
        from tokenDemo import autoTrade_pm

        autobn = MagicMock()
        autobn.close_http_session = AsyncMock()
        event = MagicMock()
        event.wait = AsyncMock(side_effect=asyncio.CancelledError())
        with (
            patch.object(AUTOA, "load_state"),
            patch.object(AUTOA, "save_state", side_effect=OSError("保存失败")) as save_state,
            patch.object(AUTOA, "close_http_session", new=AsyncMock()) as close_a,
            patch.object(CloseRecordManager, "flush_pending_records", new=AsyncMock()) as flush,
            patch.object(autoTrade_pm.AUTOBN, "from_cfg", return_value=autobn),
            patch.object(autoTrade_pm, "AsyncIOScheduler"),
            patch.object(autoTrade_pm, "load_dotenv"),
            patch.object(autoTrade_pm.atexit, "register") as register,
            patch.object(autoTrade_pm.signal, "signal"),
            patch.object(autoTrade_pm.logging, "basicConfig"),
            patch.object(autoTrade_pm.asyncio, "Event", return_value=event),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await autoTrade_pm.main()
            register.assert_called_once_with(save_state)
            save_state.assert_not_called()
        flush.assert_awaited_once()
        close_a.assert_awaited_once()
        autobn.close_http_session.assert_awaited_once()


class AutoAEntryAndBatchEfficiencyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = {"POSITIONS": {}, "OBSERVATIONS": {}}
        self.enterContext(patch.object(AUTOA, "alert_all", self.state))
        self.enterContext(patch.object(AUTOA, "_batch_window_id", None))
        self.enterContext(patch.object(AUTOA, "_batch_observations_snapshot", []))
        self.enterContext(patch.object(AUTOA, "zt_dates", ["2026-07-06", "2026-06-01"]))
        self.enterContext(patch.object(AUTOA, "_trading_calendar", None))
        self.enterContext(patch.object(AUTOA, "_calendar_loaded_on", None))

    @staticmethod
    def observation(*, pending=False):
        return Observation(
            price=9, timestamp=pd.Timestamp("2026-07-01").to_pydatetime().timestamp(),
            side=OrderSide.BUY, strategy=[PositionSide.BZ], name="测试股票",
            bz_reference_high=11, reopen_pending_date="2026-07-02" if pending else None,
        ).model_dump()

    async def test_invalid_atr_never_creates_bz_or_n_position(self):
        for branch, volume in (("BZ", 10000), ("N", 90)):
            for atr in (float("nan"), float("inf"), float("-inf"), 0, -1):
                with self.subTest(branch=branch, atr=atr):
                    self.state["POSITIONS"].clear()
                    self.state["OBSERVATIONS"]["000001"] = self.observation()
                    history = pd.DataFrame([
                        {"open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 90 + i % 5 * 10}
                        for i in range(19)
                    ] + [{"open": 12, "high": 13, "low": 11.5, "close": 12.5, "volume": volume}])
                    with (
                        patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=history)),
                        patch.object(AUTOA, "calculate_atr", return_value=atr) as calculate,
                        patch.object(AUTOA, "send_msg", new=AsyncMock()) as send,
                    ):
                        await AUTOA.on_observations(
                            "000001", AUTOA.zt_dates, self.state["OBSERVATIONS"]["000001"],
                            pd.Timestamp("2026-07-06 10:00").to_pydatetime(),
                        )
                    calculate.assert_called_once()
                    self.assertEqual(self.state["POSITIONS"], {})
                    send.assert_not_awaited()

    async def test_pending_cooldowns_share_one_calendar_request_per_batch(self):
        calendar = pd.Series(pd.to_datetime(["2026-07-02", "2026-07-03", "2026-07-06"]))
        for available_calendar in (calendar, None):
            with self.subTest(calendar_available=available_calendar is not None):
                self.state["OBSERVATIONS"] = {
                    f"{i:06}": self.observation(pending=True) for i in range(40)
                }
                AUTOA._batch_window_id = None

                async def get_calendar():
                    await asyncio.sleep(0)
                    return available_calendar

                with (
                    patch.object(AUTOA, "_get_trading_calendar", new=AsyncMock(side_effect=get_calendar)) as fetch,
                    patch.object(AUTOA, "stock_zh_a_hist", new=AsyncMock(return_value=pd.DataFrame())) as history,
                ):
                    await AUTOA._process_market_batch(pd.Timestamp("2026-07-06 10:00").to_pydatetime())
                fetch.assert_awaited_once()
                expected_pending = None if available_calendar is not None else "2026-07-02"
                for i in range(0, 40, 5):
                    stored = self.state["OBSERVATIONS"][f"{i:06}"]
                    self.assertEqual(stored["reopen_pending_date"], expected_pending)
                    if available_calendar is not None:
                        self.assertEqual(stored["earliest_open_timestamp"], pd.Timestamp("2026-07-06").to_pydatetime().timestamp())
                self.assertEqual(history.await_count, 8 if available_calendar is not None else 0)

    async def test_held_positions_do_not_wait_for_pending_calendar_request(self):
        self.state["OBSERVATIONS"] = {f"{i:06}": self.observation(pending=True) for i in range(40)}
        self.state["POSITIONS"]["900000"] = {"test_position": True}
        calendar_started = asyncio.Event()
        release_calendar = asyncio.Event()
        position_processed = asyncio.Event()

        async def get_calendar():
            calendar_started.set()
            await release_calendar.wait()
            return None

        async def process_position(*args, **kwargs):
            position_processed.set()

        with (
            patch.object(AUTOA, "_get_trading_calendar", new=AsyncMock(side_effect=get_calendar)),
            patch.object(AUTOA, "on_positions", new=AsyncMock(side_effect=process_position)) as held,
        ):
            batch = asyncio.create_task(AUTOA._process_market_batch(pd.Timestamp("2026-07-06 10:00").to_pydatetime()))
            try:
                await asyncio.wait_for(calendar_started.wait(), timeout=1)
                await asyncio.wait_for(position_processed.wait(), timeout=1)
                self.assertFalse(release_calendar.is_set())
            finally:
                release_calendar.set()
                await batch
        held.assert_awaited_once()

    async def test_five_slots_cover_observations_once_and_positions_each_time(self):
        self.state["OBSERVATIONS"] = {f"{i:06}": self.observation() for i in range(23)}
        self.state["POSITIONS"]["000001"] = {"test_position": True}
        with (
            patch.object(AUTOA, "on_positions", new=AsyncMock()) as held,
            patch.object(AUTOA, "on_observations", new=AsyncMock()) as observed,
            patch.object(AUTOA, "_get_trading_calendar", new=AsyncMock()) as calendar,
        ):
            for minute in range(5):
                await AUTOA._process_market_batch(pd.Timestamp(f"2026-07-06 10:0{minute}").to_pydatetime())
        processed = [call.args[0] for call in observed.await_args_list]
        self.assertEqual(sorted(processed), sorted(set(self.state["OBSERVATIONS"]) - {"000001"}))
        self.assertEqual(held.await_count, 5)
        calendar.assert_not_awaited()


class AutoAImportTest(unittest.TestCase):
    def test_import_does_not_read_state_or_register_exit_and_signal_handlers(self):
        code = '''
import builtins, os
from unittest.mock import patch
original_open = builtins.open
def guarded_open(filename, *args, **kwargs):
    if os.fspath(filename).endswith('alert_all_A.json'):
        raise AssertionError('import read business state')
    return original_open(filename, *args, **kwargs)
with patch('builtins.open', side_effect=guarded_open), patch('atexit.register') as register, patch('signal.signal') as signal:
    from tokenDemo.autoTrade_pm import AUTOA
    assert AUTOA.alert_all_file is None
    assert AUTOA.alert_all == {'POSITIONS': {}, 'OBSERVATIONS': {}}
    assert not any(getattr(call.args[0], '__module__', '') == 'tokenDemo.autoTrade_pm' for call in register.call_args_list)
    signal.assert_not_called()
'''
        result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                                cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode, 0, result.stderr)


class CloseRecordCancellationTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_flush_waits_for_write_before_retry(self):
        started = asyncio.Event()
        release = asyncio.Event()
        writes = []

        async def background_write(function, records):
            started.set()
            await release.wait()
            writes.append(records[:])

        with (
            patch.object(CloseRecordManager, "_pending_records", [{"source": "AUTOA"}]),
            patch.object(CloseRecordManager, "_batch_lock", None),
            patch.object(CloseRecordManager, "_batch_lock_loop", None),
            patch("tokenDemo.autoTrade_pm.asyncio.to_thread", side_effect=background_write),
        ):
            task = asyncio.create_task(CloseRecordManager.flush_pending_records())
            await started.wait()
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await CloseRecordManager.flush_pending_records()
            self.assertEqual(len(writes), 1)
            self.assertEqual(CloseRecordManager._pending_records, [])


if __name__ == "__main__":
    unittest.main()
