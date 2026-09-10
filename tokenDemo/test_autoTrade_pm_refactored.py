import asyncio
import json
import itertools
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from binance_common.errors import BadRequestError

from tokenDemo import autoTrade_pm_refactored as m


NOW = m.market_time(pd.Timestamp("2026-09-09 10:00").to_pydatetime())


def make_ashare_data():
    session = MagicMock()
    http = SimpleNamespace(get=AsyncMock(return_value=session), timeout=1)
    return m.AshareMarketData(http, MagicMock()), session


def http_response(payload, *, callback=None, status=200):
    response = MagicMock(status=status)
    text = json.dumps(payload)
    response.text = AsyncMock(return_value=f"{callback}({text});" if callback else text)
    response.json = AsyncMock(return_value=payload)
    if status >= 400:
        response.raise_for_status.side_effect = m.aiohttp.ClientResponseError(
            MagicMock(), (), status=status
        )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


def tencent_quote(code="000001", date="20260909", time="1000", **updates):
    quote = [""] * 35
    for index, value in {
        2: code,
        3: "11",
        5: "10",
        6: "1234",
        30: date + time + "00",
        33: "12",
        34: "9",
    }.items():
        quote[index] = value
    for key, value in updates.items():
        quote[{"11": 3, "13": 6}[key]] = value
    symbol = m.AshareMarketData._symbol(code)
    return {
        "code": 0,
        "data": {symbol: {"qt": {symbol: quote}, "qfqday": tencent_history()}},
    }


def tencent_history():
    return [
        [date.strftime("%Y-%m-%d"), "10", "11", "12", "9", "100"]
        for date in pd.bdate_range("2026-08-13", "2026-09-08")
    ]


class ThreeSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_tencent_ohlcv_and_volume_units(self):
        data, session = make_ashare_data()
        session.get.return_value = http_response(tencent_quote())
        bar = await data.daily_bar("000001", now=NOW)
        self.assertEqual(
            bar, {"open": 10, "high": 12, "low": 9, "close": 11, "volume": 1234}
        )
        self.assertIn("finance.qq.com", session.get.call_args.args[0])

    async def test_quote_rejects_stale_invalid_and_wrong_symbol(self):
        bad_symbol = tencent_quote()
        bad_symbol["data"]["sz000001"]["qt"]["sz000001"][2] = "600000"
        for payload in (
            tencent_quote(date="20260908"),
            tencent_quote(time="0930"),
            tencent_quote(**{"11": "nan"}),
            tencent_quote(**{"13": -1}),
            bad_symbol,
        ):
            data, session = make_ashare_data()
            session.get.return_value = http_response(payload)
            self.assertIsNone(await data.daily_bar("000001", now=NOW))

    async def test_history_single_request_no_duplicate_today(self):
        data, session = make_ashare_data()
        first = tencent_quote()
        first["data"]["sz000001"]["qfqday"].append(
            ["2026-09-09", "1", "2", "2", "1", "100"]
        )
        session.get.side_effect = [
            http_response(first),
            http_response(tencent_quote(**{"11": "10.5"})),
        ]
        context = m.MarketContext(NOW, "2026-08-13", "2026-09-09")
        one = await data.fetch_bars("000001", context)
        two = await data.fetch_bars("000001", context)
        self.assertEqual((len(one), len(two)), (20, 20))
        self.assertEqual(one.volumes[-2:], (100, 1234))
        self.assertEqual(two.price, 10.5)
        self.assertEqual(session.get.call_count, 2)

    async def test_invalid_history_is_rejected(self):
        for rows in (
            [],
            [["2026-09-08", "10"]],
            [["2026-09-08", "10", "nan", "12", "9", "100"]],
            [tencent_history()[-1]] * 2,
            list(reversed(tencent_history())),
        ):
            data, session = make_ashare_data()
            payload = tencent_quote()
            payload["data"]["sz000001"]["qfqday"] = rows
            session.get.return_value = http_response(payload)
            self.assertFalse(
                await data.fetch_bars(
                    "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
                )
            )

    async def test_no_unadjusted_history_fallback(self):
        data, session = make_ashare_data()
        payload = tencent_quote()
        body = payload["data"]["sz000001"]
        body["day"] = body.pop("qfqday")
        session.get.return_value = http_response(payload)
        self.assertFalse(
            await data.fetch_bars(
                "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
            )
        )

    async def test_eastmoney_pool(self):
        data, session = make_ashare_data()
        data.is_trading_day = AsyncMock(return_value=True)
        data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-08-13"])
        session.get.return_value = http_response(
            {
                "rc": 0,
                "data": {
                    "tc": 2,
                    "pool": [{"c": "000001", "n": "甲"}, {"c": "600185", "n": "乙"}],
                },
            }
        )
        pool, context = await data.limit_up_pool(NOW)
        self.assertEqual(pool, (("000001", "甲"), ("600185", "乙")))
        self.assertEqual(context.start_date, "2026-08-13")
        self.assertIn("eastmoney.com", session.get.call_args.args[0])

    async def test_invalid_pool_preserves_observations(self):
        for payload in (
            {"rc": 1},
            {"rc": 0, "data": {"tc": 2, "pool": [{"c": "000001", "n": "甲"}] * 2}},
            {"rc": 0, "data": {"tc": 1, "pool": [{"c": "bad", "n": "甲"}]}},
            {"rc": 0, "data": {"pool": {}}},
        ):
            data, session = make_ashare_data()
            data.is_trading_day = AsyncMock(return_value=True)
            data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-08-13"])
            session.get.return_value = http_response(payload)
            snapshot = m.StateSnapshot({}, {"000001": make_observation("000001")})
            with self.assertRaises(ValueError):
                await m.AUTOA(data).refresh_universe(NOW, snapshot)
            self.assertEqual(tuple(snapshot.observations), ("000001",))

    async def test_pool_total_must_match_before_any_update(self):
        for body in (
            {"tc": 2, "pool": [{"c": "000001", "n": "甲"}]},
            {"tc": 1, "pool": []},
            {"pool": [{"c": "000001", "n": "甲"}]},
            {"tc": True, "pool": [{"c": "000001", "n": "甲"}]},
            {"tc": -1, "pool": []},
        ):
            with self.subTest(body=body):
                data, session = make_ashare_data()
                data.is_trading_day = AsyncMock(return_value=True)
                data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-08-13"])
                session.get.return_value = http_response({"rc": 0, "data": body})
                snapshot = m.StateSnapshot({}, {"000001": make_observation("000001")})
                with self.assertRaises(ValueError):
                    await m.AUTOA(data).refresh_universe(NOW, snapshot)
                self.assertEqual(tuple(snapshot.observations), ("000001",))

    async def test_nontrading_day_never_requests_pool(self):
        data, session = make_ashare_data()
        data.is_trading_day = AsyncMock(return_value=False)
        self.assertEqual(await data.limit_up_pool(NOW), ((), None))
        session.get.assert_not_called()

    async def test_calendar_cache_and_reopen_dates(self):
        data, session = make_ashare_data()
        dates = list(pd.bdate_range("2026-08-01", "2026-09-30")) + list(
            pd.to_datetime(["2026-10-08", "2026-10-09", "2026-10-12"])
        )
        session.get.return_value = http_response({})
        with (
            patch.object(data, "_decode_calendar", return_value=dates),
            patch.object(m, "market_time", side_effect=lambda value=None: value or NOW),
        ):
            holiday = NOW.replace(month=10, day=1)
            self.assertFalse(await data.is_trading_day(holiday))
            self.assertEqual(
                await data.following_dates(holiday), ["2026-10-08", "2026-10-09"]
            )
            self.assertEqual(
                await data.reopen_timestamp(holiday),
                holiday.replace(day=9, hour=0).timestamp(),
            )
        self.assertEqual(session.get.call_count, 1)
        self.assertIn("sina.com.cn", session.get.call_args.args[0])

    async def test_calendar_failure_keeps_covered_cache(self):
        data, session = make_ashare_data()
        previous = pd.Series(pd.to_datetime(["2026-09-08", "2026-09-09", "2026-09-10"]))
        data.cache.calendar = previous
        session.get.return_value = http_response({})
        with patch.object(
            m, "market_time", side_effect=lambda value=None: value or NOW
        ):
            self.assertIs(await data.trading_calendar(NOW), previous)
            self.assertIsNone(await data.trading_calendar(NOW.replace(year=2027)))
        self.assertIs(data.cache.calendar, previous)

    async def test_sina_calendar_recorded_payload(self):
        # 2026-09-10公开响应；与参考解码器全量对照一致。
        payload = 'var datelist="LC/AAApNDXCw6mHbaPgkryxXv10eAJP1LW0SD39aT7+NV44Xba3PxCgTdrp5BkYVAc11hWvg0c/19UAc7jNtHQyWBAu2xmGuZI1NVAc3FepphjnTBw1X4hmGu+ypVAcvFenpBXPqCc6F4ZmGueLFwbIN8QTDXPsCc1FepphjvOoCc8FepphjvcgFO3CP00wxXXWhrkUdZrIJpw9X3ThrlEp6hlGc88Kcem0VeFpZM46VV4MrTC2KScKc811U4aLXUdlzINc9lTrwFW3T52KPj0mDueVFuUR1RtiEoCXfdgFOOSGRXnUhrXWhb0kt6Rk2pU44JV4SrTyU9wSDHPwCnXdP1FuiUM44r7qwdKqcYrIZpw1DqgrlU5IrHRawxjrwBaqcbrIt9gr3UhDtOpyVNjEnCHPnC3royNWvi0gjHXBXYdRlLbFpdJFueSFcqkK30sSDO+68K46IVOwVkaBX/";var KLC_TD_SH=datelist;'
        dates = m.AshareMarketData._decode_calendar(payload)
        self.assertEqual(len(dates), 8796)
        self.assertEqual(dates[0], pd.Timestamp("1990-12-19"))
        self.assertEqual(dates[-1], pd.Timestamp("2026-12-31"))
        self.assertNotIn(pd.Timestamp("2026-10-01"), dates)
        self.assertIn(pd.Timestamp("2026-10-08"), dates)
        self.assertEqual(dates, sorted(set(dates)))

    async def test_incomplete_calendar_keeps_previous_snapshot(self):
        data, session = make_ashare_data()
        previous = pd.Series(pd.bdate_range("2026-08-01", "2026-12-31"))
        data.cache.calendar = previous
        session.get.return_value = http_response({})
        for dates in (
            [pd.Timestamp("2026-09-09")],
            list(pd.bdate_range("2025-01-01", "2025-12-31")),
        ):
            with patch.object(data, "_decode_calendar", return_value=dates):
                self.assertIs(await data.trading_calendar(NOW), previous)
                self.assertIs(data.cache.calendar, previous)

    async def test_calendar_decoder_rejects_bad_payload(self):
        for payload in ("{}", 'var datelist="!";', 'var datelist="AAAA";'):
            with self.assertRaises((ValueError, IndexError)):
                m.AshareMarketData._decode_calendar(payload)

    async def test_lunch_and_postclose_quote_freshness(self):
        for now, time, valid in (
            (NOW.replace(hour=12), "1130", True),
            (NOW.replace(hour=15, minute=6), "1500", True),
            (NOW.replace(hour=15, minute=6), "1450", False),
        ):
            data, session = make_ashare_data()
            session.get.return_value = http_response(tencent_quote(time=time))
            self.assertEqual(await data.daily_bar("000001", now=now) is not None, valid)

    async def test_http_retry_bounded_and_cancellation_propagates(self):
        data, session = make_ashare_data()
        session.get.return_value = http_response({}, status=502)
        with self.assertRaises(m.aiohttp.ClientResponseError):
            await data._request("https://proxy.finance.qq.com/test")
        self.assertEqual(session.get.call_count, 2)
        session.get.reset_mock()
        session.get.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await data._request("https://proxy.finance.qq.com/test")
        session.get.assert_called_once()

    async def test_nonobject_json_no_retry(self):
        for callback in (None, "callback"):
            data, session = make_ashare_data()
            session.get.return_value = http_response([], callback=callback)
            with self.assertRaises(ValueError):
                await data._request("https://proxy.finance.qq.com/test")
            session.get.assert_called_once()

    async def test_no_akshare_import(self):
        import ast

        tree = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertNotIn("akshare", [a.name for a in node.names])
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "akshare")


class BinanceWebsocketKlineTest(unittest.IsolatedAsyncioTestCase):
    async def test_valid_recovery_resets_backoff_but_bad_message_does_not(self):
        data = self.ready_data()
        data._reconnect_delay = 30.0
        data._handle_ws_message(self.message(c="nan"), 1)
        self.assertEqual(data._reconnect_delay, 30.0)
        data._handle_ws_message(self.message(), 1)
        self.assertEqual(data._reconnect_delay, 1.0)

    def ready_data(self):
        data = m.BinanceMarketData(make_gateway(), MagicMock())
        data._slot_symbols = {"BTCUSDT"}
        data._subscribed_symbols = {"BTCUSDT"}
        data._slot_events = {"BTCUSDT": asyncio.Event()}
        data._slot_deadline = m.time.monotonic() + 30

        data._active_generation = 1
        data._accept_after_ms = int(m.time.time() * 1000) - 100
        return data

    def message(self, **changes):
        now = int(m.time.time() * 1000)
        d = now // 86400000 * 86400000
        k = {
            "s": "BTCUSDT",
            "i": "1d",
            "t": d,
            "T": d + 86400000 - 1,
            "o": "10",
            "h": "12",
            "l": "9",
            "c": "11",
            "v": "20",
            "x": False,
        }
        k.update(changes)
        return {"e": "kline", "E": now, "s": "BTCUSDT", "k": k}

    def history(self, d):
        return [[d - (29 - i) * 86400000, 10, 12, 9, 11, 20] for i in range(29)]

    async def test_valid_current_and_rest_range_then_cache_reuse(self):
        data = self.ready_data()
        payload = self.message()
        d = payload["k"]["t"]
        data._handle_ws_message(payload, 1)
        self.assertTrue(await data.wait_ready("BTCUSDT"))
        data.gateway.call = AsyncMock(return_value=self.history(d))
        bars = await data.fetch_bars("BTCUSDT", m.MarketContext(NOW))
        self.assertEqual(len(bars), 30)
        self.assertEqual(
            data.gateway.call.await_args.kwargs,
            {
                "symbol": "BTCUSDT",
                "interval": "1d",
                "start_time": d - 29 * 86400000,
                "end_time": d - 1,
                "limit": 29,
            },
        )
        await data.fetch_bars("BTCUSDT", m.MarketContext(NOW))
        data.gateway.call.assert_awaited_once()
        self.assertEqual(len(data.cache.kline_history["BTCUSDT"]), 29)

    async def test_invalid_day_values_closed_and_generation_rejected(self):
        for changes in (
            {"t": 0},
            {"c": "nan"},
            {"v": -1},
            {"h": 1},
            {"x": True},
            {"i": "1m"},
        ):
            data = self.ready_data()
            data._handle_ws_message(self.message(**changes), 1)
            self.assertFalse(data._latest_klines)
        data = self.ready_data()
        data._handle_ws_message(self.message(), 0)
        self.assertFalse(data._latest_klines)
        p = self.message()
        p["E"] = data._accept_after_ms
        data._handle_ws_message(p, 1)
        self.assertFalse(data._latest_klines)

    async def test_missing_ws_no_rest_and_cancellation_propagates(self):
        data = self.ready_data()
        data.gateway.call = AsyncMock()
        data._slot_deadline = m.time.monotonic() + 0.01
        self.assertFalse(await data.wait_ready("BTCUSDT"))
        self.assertFalse(await data.fetch_bars("BTCUSDT", m.MarketContext(NOW)))
        data.gateway.call.assert_not_awaited()
        data._slot_deadline = m.time.monotonic() + 30
        task = asyncio.create_task(data.wait_ready("BTCUSDT"))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_rest_cross_day_or_disconnect_does_not_detect(self):
        for disconnect in (False, True):
            data = self.ready_data()
            p = self.message()
            d = p["k"]["t"]
            data._handle_ws_message(p, 1)

            async def fetch(*args, **kwargs):
                if disconnect:
                    data._active_generation = None
                else:
                    data._latest_klines["BTCUSDT"] = (
                        p["E"],
                        (d + 86400000, 10, 12, 9, 11, 20),
                    )
                return self.history(d)

            data.gateway.call = AsyncMock(side_effect=fetch)
            self.assertFalse(await data.fetch_bars("BTCUSDT", m.MarketContext(NOW)))

    async def test_history_integrity_and_midnight_refresh(self):
        data = self.ready_data()
        p = self.message()
        d = p["k"]["t"]
        data._handle_ws_message(p, 1)
        data.cache.kline_history["BTCUSDT"] = self.history(d - 86400000)
        data.gateway.call = AsyncMock(return_value=self.history(d))
        self.assertEqual(
            len(await data.fetch_bars("BTCUSDT", m.MarketContext(NOW))), 30
        )
        for history in (
            self.history(d)[:-1],
            self.history(d)[::-1],
            self.history(d - 86400000),
        ):
            self.assertFalse(data._valid_history(history, d))

    async def test_claim_once_and_disconnect_notice_dedup(self):
        data = self.ready_data()
        p = self.message()
        data._handle_ws_message(p, 1)
        bars = m.MarketBars.from_binance(
            self.history(p["k"]["t"]) + [[p["k"]["t"], 10, 12, 9, 11, 20]]
        )
        self.assertEqual(len(data.claim_bar("BTCUSDT", bars)), 30)
        self.assertIn("BTCUSDT", data._slot_symbols)
        notify = AsyncMock()
        data.set_disconnect_notifier(notify)
        data._connection_failed(ConnectionError())
        data._connection_failed(ConnectionError())
        await asyncio.gather(*data._notice_tasks)
        notify.assert_awaited_once()
        await data.close()

    async def test_end_slot_keeps_subscription_and_fresh_quote(self):
        data = self.ready_data()
        data._handle_ws_message(self.message(), 1)
        data._stream = MagicMock()
        data._stream.unsubscribe_batch = AsyncMock()
        data._subscribed_symbols = {"BTCUSDT"}
        await data.end_slot()
        self.assertIsNone(data._slot_deadline)
        self.assertIn("BTCUSDT", data._latest_klines)
        self.assertEqual(data._subscribed_symbols, {"BTCUSDT"})
        data._stream.unsubscribe_batch.assert_not_awaited()
        data._slot_deadline = m.time.monotonic() + 10
        self.assertIsNotNone(data._latest_bar("BTCUSDT"))

    async def test_next_slot_subscribes_only_new_symbols_and_accepts_idle_update(self):
        data = self.ready_data()
        stream = MagicMock()
        stream.disconnected = asyncio.Event()
        stream.subscribe_batch = AsyncMock()
        stream.finish = AsyncMock()
        data._stream = stream
        data._ws_task = asyncio.create_task(asyncio.Event().wait())
        try:
            await data.end_slot()
            data._handle_ws_message(self.message(), 1)
            self.assertIn("BTCUSDT", data._latest_klines)
            await data.begin_slot(["BTCUSDT", "ETHUSDT"], m.time.monotonic() + 5)
            stream.subscribe_batch.assert_awaited_once_with(["ETHUSDT"])
            self.assertTrue(await data.wait_ready("BTCUSDT"))
            await data.end_slot()
            self.assertEqual(data._subscribed_symbols, {"BTCUSDT", "ETHUSDT"})
        finally:
            await data.close()

    async def test_unfinished_union_completed_unsubscribe_and_old_current_day_quote(
        self,
    ):
        data = self.ready_data()
        stream = MagicMock()
        stream.disconnected = asyncio.Event()
        stream.subscribe_batch = AsyncMock()
        stream.unsubscribe_batch = AsyncMock()
        stream.finish = AsyncMock()
        data._stream = stream
        data._ws_task = asyncio.create_task(asyncio.Event().wait())
        try:
            payload = self.message()
            data._accept_after_ms = payload["E"] - 120000
            payload["E"] -= 60000
            data._handle_ws_message(payload, 1)
            self.assertIsNotNone(data._latest_bar("BTCUSDT"))
            await data.end_slot()
            symbols = await data.begin_slot(["ETHUSDT"], m.time.monotonic() + 5)
            self.assertEqual(set(symbols), {"BTCUSDT", "ETHUSDT"})
            self.assertTrue(await data.wait_ready("BTCUSDT"))
            data.complete_slot_symbol("BTCUSDT")
            await data.end_slot()
            stream.unsubscribe_batch.assert_awaited_once_with(["BTCUSDT"])
            self.assertEqual(data._slot_symbols, {"ETHUSDT"})
            self.assertNotIn("BTCUSDT", data._latest_klines)
        finally:
            await data.close()

    async def test_history_short_is_explicit_but_bad_history_retries(self):
        data = self.ready_data()
        p = self.message()
        data._handle_ws_message(p, 1)
        data.gateway.call = AsyncMock(return_value=self.history(p["k"]["t"])[-8:])
        with self.assertRaises(m.InsufficientKlineHistory):
            await data.fetch_bars("BTCUSDT", m.MarketContext(NOW))
        data.gateway.call.return_value = self.history(p["k"]["t"])[-8:][::-1]
        self.assertFalse(await data.fetch_bars("BTCUSDT", m.MarketContext(NOW)))

    async def test_only_terminal_outcomes_remove_pending_and_cancel_retains(self):
        for outcome in m.ScanOutcome:
            data = self.ready_data()
            engine = m.TradingEngine(
                SimpleNamespace(data=data),
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
            )
            engine.process_instrument = AsyncMock(return_value=outcome)
            self.assertEqual(
                await engine._process_slot_symbol("BTCUSDT", m.MarketContext(NOW)),
                outcome,
            )
            self.assertEqual(
                "BTCUSDT" in data._slot_symbols,
                outcome in (m.ScanOutcome.NO_DATA, m.ScanOutcome.FAILED),
            )
        data = self.ready_data()
        engine.strategy.data = data
        engine.process_instrument = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await engine._process_slot_symbol("BTCUSDT", m.MarketContext(NOW))
        self.assertIn("BTCUSDT", data._slot_symbols)

    async def test_slot_budget_is_single_deadline_and_no_extra_first_message_limit(
        self,
    ):
        data = self.ready_data()
        data._slot_deadline = m.time.monotonic() + 1
        task = asyncio.create_task(data.wait_ready("BTCUSDT"))
        await asyncio.sleep(0.03)
        self.assertFalse(task.done())
        data._handle_ws_message(self.message(), 1)
        self.assertTrue(await task)
        self.assertFalse(hasattr(data, "_ready_deadline"))
        self.assertFalse(hasattr(data, "WS_FIRST_MESSAGE_TIMEOUT"))

    async def test_sdk_batch_ack_error_and_cleanup_without_network(self):
        from aiohttp import web

        commands = []

        async def handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for msg in ws:
                p = json.loads(msg.data)
                commands.append(p)
                await ws.send_json({"id": p["id"], "result": None})
                if p["method"] == "SUBSCRIBE":
                    await ws.send_json(
                        {"stream": p["params"][0], "data": self.message()}
                    )
            return ws

        app = web.Application()
        app.router.add_get("/market/stream", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        received = asyncio.Event()
        sdk = m.BinanceKlineStream(lambda _: received.set())
        sdk.configuration.stream_url = f"http://127.0.0.1:{port}/stream"
        try:
            await sdk.open()
            await sdk.subscribe_batch(["BTCUSDT", "ETHUSDT"])
            await asyncio.wait_for(received.wait(), 1)
            await sdk.unsubscribe_batch(["BTCUSDT", "ETHUSDT"])
            self.assertEqual(
                [p["method"] for p in commands], ["SUBSCRIBE", "UNSUBSCRIBE"]
            )
            self.assertEqual(len(commands[0]["params"]), 2)
        finally:
            await sdk.finish()
            await runner.cleanup()
        self.assertFalse(sdk._background)
        self.assertIsNone(sdk.session)

    async def test_all_waiters_share_deadline_instead_of_eight_at_a_time(self):
        data = self.ready_data()
        symbols = [f"COIN{i}USDT" for i in range(160)]
        data._slot_symbols = set(symbols)
        data._slot_events = {symbol: asyncio.Event() for symbol in symbols}
        started = m.time.monotonic()
        data._slot_deadline = started + 0.05
        outcomes = await asyncio.gather(
            *(data.wait_ready(symbol) for symbol in symbols)
        )
        self.assertFalse(any(outcomes))
        self.assertLess(m.time.monotonic() - started, 1.5)

    async def test_sdk_ack_timeout_marks_connection_failed(self):
        sdk = m.BinanceKlineStream(lambda _: None)
        connection = MagicMock()
        connection.pending_request = {}
        connection.websocket.send_str = AsyncMock()
        sdk._connection = connection
        with patch.object(m.asyncio, "wait_for", side_effect=asyncio.TimeoutError):
            with self.assertRaises(asyncio.TimeoutError):
                await sdk.command("LIST_SUBSCRIPTIONS")
        self.assertTrue(sdk.disconnected.is_set())
        self.assertFalse(connection.pending_request)

    async def test_reconnect_restores_retained_subscriptions_after_slot(self):
        data = self.ready_data()
        data._slot_deadline = None
        connections = []

        class Stream:
            def __init__(self, callback):
                self.callback = callback
                self.disconnected = asyncio.Event()
                self.subscriptions = []
                connections.append(self)

            async def open(self):
                pass

            async def subscribe_batch(self, symbols):
                self.subscriptions.append(tuple(symbols))

            async def unsubscribe_batch(self, symbols):
                pass

            async def finish(self):
                pass

            async def command(self, *args):
                return []

        with (
            patch.object(m, "BinanceKlineStream", Stream),
            patch.object(m.random, "uniform", return_value=0.001),
        ):
            try:
                await data.begin_slot(["BTCUSDT", "ETHUSDT"], m.time.monotonic() + 5)
                for _ in range(30):
                    if connections and connections[0].subscriptions:
                        break
                    await asyncio.sleep(0.005)
                data.complete_slot_symbol("BTCUSDT")
                connections[0].disconnected.set()
                for _ in range(30):
                    if len(connections) > 1 and connections[1].subscriptions:
                        break
                    await asyncio.sleep(0.005)
                self.assertEqual(connections[1].subscriptions, [("ETHUSDT",)])
                late = self.message(s="ETHUSDT")
                late["s"] = "ETHUSDT"
                late["E"] = data._accept_after_ms + 1
                connections[0].callback(late)
                self.assertFalse(data._latest_klines)
                connections[1].callback(late)
                self.assertIn("ETHUSDT", data._latest_klines)

                await data.end_slot()
                connections[1].disconnected.set()
                for _ in range(30):
                    if len(connections) > 2:
                        break
                    await asyncio.sleep(0.005)
                self.assertEqual(connections[2].subscriptions, [("ETHUSDT",)])
            finally:
                await data.close()


def make_test_engine(strategy, *args, **kwargs):
    # 既有交易规则测试只提供固定行情，不连接网络；WS生命周期由专项测试验证。
    strategy.data.begin_slot = AsyncMock(
        side_effect=lambda symbols, deadline: tuple(symbols)
    )
    strategy.data.end_slot = AsyncMock()
    strategy.data.wait_ready = AsyncMock(return_value=True)
    strategy.data.claim_bar = lambda symbol, bars: bars
    strategy.data.complete_slot_symbol = MagicMock()
    strategy.data.close = AsyncMock()
    return m.TradingEngine(strategy, *args, **kwargs)


def make_position(code="BTCUSDT", side=m.PositionSide.LONG, **updates):
    value = m.Position(
        take_profit=20 if side == m.PositionSide.LONG else 5,
        stop_loss=8 if side == m.PositionSide.LONG else 12,
        position_side=side,
        entry_price=10,
        name=code,
        date=20260908,
        strategy=(m.StrategyTag.BZ,),
        guard=m.OIStop(open_interest=100) if side == m.PositionSide.LONG else None,
    )
    return value.model_copy(update=updates)


def make_observation(code="BTCUSDT", tags=(m.StrategyTag.BZ,), **updates):
    return m.Observation(
        price=10,
        timestamp=(NOW - pd.Timedelta(days=1)).timestamp(),
        side=m.OrderSide.BUY,
        strategy=tags,
        name=code,
        **updates,
    )


def make_bars(price=10, volume=100):
    return m.MarketBars(
        times=tuple(range(30)),
        opens=tuple([10] * 29 + [price - 0.1]),
        highs=tuple([11] * 29 + [price + 0.5]),
        lows=tuple([9] * 29 + [price - 0.5]),
        closes=tuple([10] * 29 + [price]),
        volumes=tuple([100] * 29 + [volume]),
    )


def make_state(market="AUTOBN"):
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "state.json"
    path.write_text(
        json.dumps({"POSITIONS": {}, "OBSERVATIONS": {}, "extra": "kept"}),
        encoding="utf-8",
    )
    state = m.TradingState(market, path)
    state.load()
    return directory, state, path


def make_gateway():
    gateway = MagicMock()
    gateway.account = AsyncMock(
        return_value={"available": 1000, "equity": 1000, "maintenance": 0}
    )
    gateway.positions = AsyncMock(return_value=[])
    gateway.position_amount = AsyncMock(return_value=(1, 10))
    gateway.submit = AsyncMock(
        return_value={"status": "FILLED", "executedQty": "1", "origQty": "1"}
    )
    gateway.query_order = AsyncMock(
        return_value={"status": "FILLED", "executedQty": "1", "origQty": "1"}
    )
    gateway.call = AsyncMock(return_value={"markPrice": "10", "leverage": 5})
    return gateway


class RequestDiagnosticsTest(unittest.TestCase):
    def test_each_limit_status_logs_first_snapshot_and_suppresses_storm(self):
        import requests

        session = requests.Session()
        responses = []
        for status in (429, 429, 418, 418):
            response = requests.Response()
            response.status_code = status
            response._content = b"{}"
            response.headers["Retry-After"] = "secret-invalid-header"
            responses.append(response)
        session.send = MagicMock(side_effect=responses)
        logger = MagicMock()
        metrics = m.BinanceRequestDiagnostics(logger=logger)
        metrics.attach(session, "fapi")
        with patch.object(m.time, "monotonic", return_value=10):
            for _ in responses:
                metrics.invoke(
                    lambda: session.get(
                        "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT"
                    )
                )
        events = [json.loads(call.args[0]) for call in logger.info.call_args_list]
        self.assertEqual(
            [event["trigger"]["http_status"] for event in events], [429, 418]
        )
        self.assertEqual([event["http_5m"] for event in events], [1, 3])
        self.assertNotIn("secret-invalid-header", str(logger.mock_calls))

    def test_concurrent_calls_count_once_and_emit_minutely(self):
        import requests
        from concurrent.futures import ThreadPoolExecutor

        session = requests.Session()
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        session.send = MagicMock(return_value=response)
        clock = [100.0]
        logger = MagicMock()
        with patch.object(m.time, "monotonic", side_effect=lambda: clock[0]):
            metrics = m.BinanceRequestDiagnostics(logger=logger)
            metrics.attach(session, "fapi")
            metrics.attach(session, "fapi")
            request = requests.Request(
                "GET", "https://fapi.binance.com/fapi/v1/klines"
            ).prepare()

            def call(_):
                metrics.invoke(lambda: session.send(request))

            with ThreadPoolExecutor(8) as pool:
                list(pool.map(call, range(100)))
            snapshot = metrics.snapshot()
            self.assertEqual(
                (
                    snapshot["http_5m"],
                    snapshot["sdk_calls_5m"],
                    snapshot["extra_sends_5m"],
                ),
                (100, 100, 0),
            )
            logger.info.assert_not_called()
            clock[0] += 60
            call(None)
            logger.info.assert_called_once()
            self.assertEqual(
                json.loads(logger.info.call_args.args[0])["event"], "minute_summary"
            )

    def test_default_log_rotates_and_is_lazy(self):
        import logging

        with tempfile.TemporaryDirectory() as folder:
            logger = logging.Logger("isolated-diagnostics")
            with (
                patch.object(m.logging, "getLogger", return_value=logger),
                patch.object(m, "__file__", str(Path(folder) / "entry.py")),
            ):
                metrics = m.BinanceRequestDiagnostics()
            path = Path(folder) / "binance_requests.log"
            self.assertFalse(path.exists())
            handler = logger.handlers[0]
            self.assertEqual(handler.maxBytes, 5 * 1024 * 1024)
            self.assertEqual(handler.backupCount, 2)
            handler.maxBytes = 200
            for _ in range(6):
                metrics.report(force=True)
            handler.close()
            self.assertTrue(path.exists())
            self.assertLessEqual(
                len(list(Path(folder).glob("binance_requests.log*"))), 3
            )

    def test_counts_real_sends_including_sdk_retry_and_redacts_secrets(self):
        import requests

        session = requests.Session()
        session.trust_env = False
        response = requests.Response()
        response.status_code = 429
        response._content = b'{"code":-1003,"msg":"secret exception body"}'
        response.headers.update(
            {
                "X-MBX-USED-WEIGHT-1M": "2399",
                "Retry-After": "60",
                "Set-Cookie": "secret-cookie",
            }
        )
        sender = MagicMock(
            side_effect=[requests.ConnectionError("secret-url-signature"), response]
        )
        session.send = sender
        output = MagicMock()
        metrics = m.BinanceRequestDiagnostics(logger=output)
        metrics.attach(session, "fapi")

        def sdk():
            for _ in range(2):
                try:
                    return session.get(
                        "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=5m&signature=SECRET-SIGNATURE&api_key=SECRET-KEY"
                    )
                except requests.ConnectionError:
                    pass

        self.assertIs(metrics.invoke(sdk), response)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["http_5m"], 2)
        self.assertEqual(snapshot["sdk_calls_5m"], 1)
        self.assertEqual(snapshot["extra_sends_5m"], 1)
        text = str(output.mock_calls)
        for secret in (
            "SECRET-SIGNATURE",
            "SECRET-KEY",
            "secret-cookie",
            "secret exception body",
            "secret-url-signature",
        ):
            self.assertNotIn(secret, text)
        self.assertIn("2399", text)
        self.assertIn("rate_limit", text)
        self.assertIn("oi", text)

    def test_rolling_window_and_cache_events(self):
        metrics = m.BinanceRequestDiagnostics(logger=MagicMock())
        with patch.object(m.time, "monotonic", return_value=10):
            metrics.note("cache", "oi", "5m", "hit")
        with patch.object(m.time, "monotonic", return_value=71):
            self.assertEqual(metrics.snapshot()["events_1m"], {})
            self.assertTrue(metrics.snapshot()["events_5m"])
        with patch.object(m.time, "monotonic", return_value=311):
            self.assertEqual(metrics.snapshot()["events_5m"], {})

    def test_diagnostic_failure_does_not_change_response_or_exception(self):
        import requests

        session = requests.Session()
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        sender = MagicMock(return_value=response)
        session.send = sender
        output = MagicMock()
        output.info.side_effect = OSError("log disk failure")
        metrics = m.BinanceRequestDiagnostics(logger=output)
        metrics.attach(session, "fapi")
        self.assertIs(
            metrics.invoke(
                lambda: session.get(
                    "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT"
                )
            ),
            response,
        )
        error = requests.ConnectionError("test")
        sender.side_effect = error
        with self.assertRaises(requests.ConnectionError) as raised:
            metrics.invoke(
                lambda: session.get("https://fapi.binance.com/fapi/v1/klines")
            )
        self.assertIs(raised.exception, error)


class RequestDiagnosticIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_observes_real_sdk_retry_with_mock_transport(self):
        import requests
        from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
            KlineCandlestickDataIntervalEnum,
        )

        config = m.ConfigurationRestAPI(retries=2, backoff=0)
        client = m.DerivativesTradingUsdsFutures(config_rest_api=config)
        response = requests.Response()
        response.status_code = 200
        response._content = b'[[1,"10","11","9","10","100"]]'
        response.headers["Content-Type"] = "application/json"
        transport = MagicMock(
            side_effect=[requests.ConnectionError("transient"), response]
        )
        client.rest_api._session.send = transport
        gateway = m.BinanceGateway(market_client=client, papi_client=MagicMock())
        # Keep all output in memory while exercising the actual SDK's retry loop.
        gateway.diagnostics.logger = MagicMock()
        token = m._BINANCE_REQUEST_SCOPE.set("unobserved")
        try:
            result = await gateway.call(
                client.rest_api.kline_candlestick_data,
                symbol="BTCUSDT",
                interval=KlineCandlestickDataIntervalEnum("1d"),
                limit=30,
            )
        finally:
            m._BINANCE_REQUEST_SCOPE.reset(token)
        self.assertEqual(len(result), 1)
        snapshot = gateway.diagnostics.snapshot()
        self.assertEqual(
            (snapshot["http_5m"], snapshot["sdk_calls_5m"], snapshot["extra_sends_5m"]),
            (2, 1, 1),
        )
        self.assertTrue(
            any(
                ":unobserved:" in key
                for key in snapshot["events_5m"]
                if key.startswith("http:")
            )
        )

    async def test_cache_lagging_and_hit_counts_do_not_change_requests(self):
        gateway = make_gateway()
        gateway.diagnostics = m.BinanceRequestDiagnostics(logger=MagicMock())
        boundary = int(NOW.timestamp() * 1000) // 300000 * 300000
        row = {"timestamp": boundary - 300000, "sumOpenInterest": "100"}
        gateway.call.return_value = [row]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.cache.oi_5m["BTCUSDT"] = [row]
        with patch.object(m.time, "time", return_value=boundary / 1000 + 1):
            for _ in range(2):
                await data.oi_5m("BTCUSDT")
            data.cache.oi_5m["BTCUSDT"] = [{**row, "timestamp": boundary}]
            await data.oi_5m("BTCUSDT")
        gateway.call.assert_awaited()
        self.assertEqual(gateway.call.await_count, 2)
        events = gateway.diagnostics.snapshot()["events_5m"]
        self.assertEqual(events["cache:oi:5m:other:lag_refetch"], 2)
        self.assertEqual(events["cache:oi:5m:other:hit"], 1)


class StateModelTest(unittest.TestCase):
    def test_market_bars_and_state_codec(self):
        with self.assertRaises(ValueError):
            m.MarketBars(times=(1,), opens=(), highs=(), lows=(), closes=(), volumes=())
        data = m.MarketBars.from_frame(
            pd.DataFrame(
                {
                    "date": ["2026-09-09"],
                    "open": [1],
                    "high": [2],
                    "low": [0],
                    "close": [1.5],
                    "volume": [10],
                }
            )
        )
        self.assertEqual(data.price, 1.5)
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        state.apply(
            m.StatePatch(
                positions=(("BTCUSDT", make_position()),),
                observations=(("BTCUSDT", make_observation()),),
            )
        )
        state.save()
        raw = json.loads(path.read_text())
        self.assertEqual(raw["POSITIONS"]["BTCUSDT"]["close_side"], "SELL")
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertIsInstance(restored.snapshot().positions["BTCUSDT"].guard, m.OIStop)

    def test_typed_patch_rejects_wrong_domain(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        with self.assertRaises(TypeError):
            state.apply(m.StatePatch(positions=(("bad", make_observation()),)))
        self.assertEqual(state.snapshot().positions, {})

    def test_pending_order_roundtrips(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        intent = m.TradeIntent(
            m.ActionKind.OPEN,
            "BTCUSDT",
            make_position(),
            10,
            observation=make_observation(),
        )
        state.remember_order(
            m.PreparedOrder(intent, 1, 10, 10, client_order_id="at-known")
        )
        state.save()
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.pending_order("BTCUSDT").client_order_id, "at-known")


class DataAndExecutionTest(unittest.IsolatedAsyncioTestCase):
    async def test_binance_universe_requires_exact_trading_status(self):
        rows = [
            {
                "symbol": symbol,
                "quoteAsset": quote,
                "status": status,
                "quantityPrecision": 3,
                "quotePrecision": 8,
            }
            for symbol, quote, status in (
                ("BTCUSDT", "USDT", "TRADING"),
                ("GAIBUSDT", "USDT", "PENDING_TRADING"),
                ("PREUSDT", "USDT", "PRE_TRADING"),
                ("POSTUSDT", "USDT", "POST_TRADING"),
                ("CLOSEUSDT", "USDT", "CLOSE"),
                ("BTCUSDC", "USDC", "TRADING"),
                ("FAKEUSDT", "USDTX", "TRADING"),
            )
        ]
        gateway = MagicMock(
            call=AsyncMock(return_value={"symbols": rows}),
            positions=AsyncMock(return_value=[]),
        )
        data = m.BinanceMarketData(gateway, MagicMock())
        self.assertTrue(await data.refresh(NOW))
        self.assertEqual(data.universe(), ("BTCUSDT",))
        self.assertEqual(set(data.cache.symbols_info), {"BTCUSDT"})

    async def test_nontrading_holdings_and_pending_orders_still_scanned(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position("GAIBUSDT")
        state.apply(m.StatePatch(positions=(("GAIBUSDT", held),)))
        state.remember_order(
            m.PreparedOrder(
                m.TradeIntent(
                    m.ActionKind.CLOSE, "PENDINGUSDT", make_position("PENDINGUSDT"), 10
                ),
                1,
                10,
                10,
                client_order_id="at-pending",
            )
        )
        strategy = MagicMock(
            prepare_cycle=AsyncMock(
                return_value=(m.MarketContext(NOW), m.StatePatch())
            ),
            scan_candidates=MagicMock(return_value=("BTCUSDT",)),
        )
        engine = make_test_engine(
            strategy,
            MagicMock(),
            state,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        engine.process_instrument = AsyncMock(return_value=m.ScanOutcome.PROCESSED)
        await engine._scan(NOW)
        self.assertEqual(
            {call.args[0] for call in engine.process_instrument.await_args_list},
            {"BTCUSDT", "GAIBUSDT", "PENDINGUSDT"},
        )
        self.assertIn("GAIBUSDT", state.snapshot().positions)
        self.assertEqual(state.pending_symbols(), ("PENDINGUSDT",))

    async def test_binance_refresh_is_atomic_and_bootstrap_is_once(self):
        gateway = MagicMock()
        gateway.positions = AsyncMock(return_value=[])
        gateway.call = AsyncMock(
            side_effect=[{"symbols": []}, OSError("down"), OSError("again")]
        )
        data = m.BinanceMarketData(gateway, MagicMock())
        self.assertFalse(await data.refresh(NOW))
        self.assertFalse(await data.bootstrap(NOW))
        self.assertFalse(await data.bootstrap(NOW))
        self.assertEqual(gateway.call.await_count, 2)

    async def test_binance_order_has_id_and_reconciles_unknown(self):
        gateway = MagicMock()
        gateway.submit = AsyncMock(side_effect=OSError("timeout"))
        gateway.query_order = AsyncMock(
            return_value={"status": "FILLED", "executedQty": "1", "origQty": "1"}
        )
        executor = m.BinanceExecutor(
            gateway,
            MagicMock(precision=MagicMock(return_value=Decimal("0.001"))),
            MagicMock(),
        )
        intent = m.TradeIntent(m.ActionKind.OPEN, "BTCUSDT", make_position(), 10)
        result = await executor.submit(
            m.PreparedOrder(intent, 1, 10, 10, client_order_id="at-reconcile")
        )
        self.assertTrue(result.filled)
        gateway.submit.assert_awaited_once()
        gateway.query_order.assert_awaited_once()

    async def test_binance_position_queries_keep_position_side(self):
        gateway = MagicMock()
        gateway.positions = AsyncMock(
            return_value=[
                {
                    "symbol": "BTCUSDT",
                    "positionSide": "LONG",
                    "positionAmt": "2",
                    "entryPrice": "10",
                },
            ]
        )
        self.assertEqual(
            (await gateway.positions("BTCUSDT", "LONG"))[0]["positionSide"], "LONG"
        )
        data = m.BinanceMarketData(gateway, MagicMock())
        data.cache.symbols_info["BTCUSDT"] = {"quantityPrecision": Decimal("0.001")}
        executor = m.BinanceExecutor(gateway, data, MagicMock())
        intent = m.TradeIntent(m.ActionKind.CLOSE, "BTCUSDT", make_position(), 10)
        await executor.prepare(intent)
        gateway.positions.assert_awaited_with("BTCUSDT", "LONG")

    async def test_full_close_without_precision_uses_confirmed_amount_but_partial_waits(
        self,
    ):
        gateway = MagicMock()
        gateway.position_amount = AsyncMock(return_value=(1, 10))
        executor = m.BinanceExecutor(
            gateway, MagicMock(precision=MagicMock(return_value=None)), MagicMock()
        )
        full = m.TradeIntent(m.ActionKind.CLOSE, "BTCUSDT", make_position(), 10)
        partial = m.TradeIntent(
            m.ActionKind.CLOSE, "BTCUSDT", make_position(), 10, ratio=0.7
        )
        self.assertIsNotNone(await executor.prepare(full))
        # 小名义价值会按原规则升级为全平，不需要精度。
        self.assertIsNotNone(await executor.prepare(partial))

    async def test_ashare_executor_is_virtual(self):
        executor = m.AshareExecutor()
        intent = m.TradeIntent(m.ActionKind.OPEN, "000001", make_position("000001"), 10)
        result = await executor.submit(await executor.prepare(intent))
        self.assertTrue(result.filled)
        self.assertEqual(result.quantity, 100)

    async def test_ashare_pool_returns_typed_bars_context_and_preserves_empty(self):
        data, session = make_ashare_data()
        data.is_trading_day = AsyncMock(return_value=True)
        data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-09-08"])
        session.get.return_value = http_response(
            {
                "rc": 0,
                "data": {"tc": 1, "pool": [{"c": "000001", "n": "测试"}]},
            }
        )
        pool, context = await data.limit_up_pool(NOW.replace(hour=15, minute=6))
        self.assertEqual(pool, (("000001", "测试"),))
        self.assertEqual(context.end_date, "2026-09-09")
        session.get.return_value = http_response(
            {
                "rc": 0,
                "data": {"tc": 0, "pool": []},
            }
        )
        empty, no_context = await data.limit_up_pool(NOW.replace(hour=15, minute=6))
        self.assertEqual(empty, ())
        self.assertIsNone(no_context)


class EngineTest(unittest.IsolatedAsyncioTestCase):
    def make_engine(self, strategy, executor, state):
        records = MagicMock()
        records.flush_pending_records = AsyncMock()
        notifications = MagicMock()
        notifications.send = AsyncMock()
        return make_test_engine(
            strategy, executor, state, notifications, records, MagicMock(), MagicMock()
        )

    async def test_engine_commits_state_before_trade_notification(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        strategy = MagicMock(
            MARKET="AUTOBN", SIGNAL_CHANNEL="feishu", SIGNAL_BEFORE_ORDER=True
        )
        strategy.signal_message = MagicMock(return_value="signal")
        strategy.trade_message = MagicMock(
            return_value=m.TradeNotification("trade", "trade")
        )
        strategy.observation_after_open = MagicMock(return_value=make_observation())
        strategy.record_symbol = MagicMock(return_value="BTCUSDT")
        executor = MagicMock(REQUIRES_ORDER_JOURNAL=True)
        intent = m.TradeIntent(
            m.ActionKind.OPEN,
            "BTCUSDT",
            make_position(),
            10,
            observation=make_observation(),
        )
        executor.prepare = AsyncMock(
            return_value=m.PreparedOrder(intent, 1, 10, 10, client_order_id="x")
        )
        executor.submit = AsyncMock(
            return_value=m.ExecutionResult(
                m.ExecutionStatus.FILLED, 1, 10, 10, original_quantity="1"
            )
        )
        executor.complete_result = AsyncMock(side_effect=lambda order, result: result)
        engine = self.make_engine(strategy, executor, state)
        seen = []

        async def notify(*args, **kwargs):
            seen.append("BTCUSDT" in state.snapshot().positions)

        engine.notifications.send.side_effect = notify
        self.assertTrue(await engine.execute_action(intent, m.MarketContext(NOW)))
        # 信号是交易前通知；成交通知发生在状态提交之后。
        self.assertEqual(seen, [False, True])

    async def test_engine_keeps_unknown_order_pending(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        strategy = MagicMock(
            MARKET="AUTOBN", SIGNAL_CHANNEL="feishu", SIGNAL_BEFORE_ORDER=True
        )
        strategy.signal_message = MagicMock(return_value="signal")
        executor = MagicMock(REQUIRES_ORDER_JOURNAL=True)
        intent = m.TradeIntent(
            m.ActionKind.OPEN,
            "BTCUSDT",
            make_position(),
            10,
            observation=make_observation(),
        )
        executor.prepare = AsyncMock(return_value=m.PreparedOrder(intent, 1, 10, 10))
        executor.submit = AsyncMock(
            return_value=m.ExecutionResult(m.ExecutionStatus.UNKNOWN)
        )
        engine = self.make_engine(strategy, executor, state)
        self.assertFalse(await engine.execute_action(intent, m.MarketContext(NOW)))
        self.assertIn("BTCUSDT", state.pending_symbols())
        self.assertFalse(await engine.execute_action(intent, m.MarketContext(NOW)))
        executor.submit.assert_awaited_once()

    async def test_confirmed_order_removes_pending_from_recovery_state(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        strategy = MagicMock(
            MARKET="AUTOBN", SIGNAL_CHANNEL="feishu", SIGNAL_BEFORE_ORDER=True
        )
        strategy.signal_message = MagicMock(return_value="signal")
        strategy.trade_message = MagicMock(return_value=None)
        strategy.observation_after_open = MagicMock(return_value=make_observation())
        executor = MagicMock(REQUIRES_ORDER_JOURNAL=True)
        intent = m.TradeIntent(
            m.ActionKind.OPEN,
            "BTCUSDT",
            make_position(),
            10,
            observation=make_observation(),
        )
        executor.prepare = AsyncMock(
            return_value=m.PreparedOrder(intent, 1, 10, 10, client_order_id="x")
        )
        executor.submit = AsyncMock(
            return_value=m.ExecutionResult(
                m.ExecutionStatus.FILLED, 1, 10, 10, original_quantity="1"
            )
        )
        executor.complete_result = AsyncMock(side_effect=lambda order, result: result)
        engine = self.make_engine(strategy, executor, state)
        await engine.execute_action(intent, m.MarketContext(NOW))
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.pending_symbols(), ())
        self.assertIn("BTCUSDT", restored.snapshot().positions)

    async def test_daily_pipeline_order(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        strategy = MagicMock()
        strategy.daily_report_due = AsyncMock(return_value=True)
        strategy.build_daily_report = AsyncMock(
            return_value=m.TradeNotification("t", "c")
        )
        strategy.refresh_universe = AsyncMock(return_value=(True, m.StatePatch()))
        notifications = MagicMock()
        notifications.send = AsyncMock()
        records = MagicMock()
        records.flush_pending_records = AsyncMock()
        events = []
        strategy.build_daily_report.side_effect = lambda *args: events.append(
            "report"
        ) or m.TradeNotification("t", "c")
        strategy.refresh_universe.side_effect = lambda *args: events.append(
            "refresh"
        ) or (True, m.StatePatch())

        async def send(*args, **kwargs):
            events.append("send")

        notifications.send.side_effect = send
        state.save = MagicMock(side_effect=lambda: events.append("save"))
        engine = make_test_engine(
            strategy,
            MagicMock(),
            state,
            notifications,
            records,
            SimpleNamespace(timeout=0.1),
            MagicMock(),
        )
        await engine.push_daily_report(NOW)
        self.assertEqual(events, ["report", "send", "refresh", "save"])

    async def test_child_cancel_does_not_leave_sibling_running(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        strategy = MagicMock()
        strategy.prepare_cycle = AsyncMock(
            return_value=(m.MarketContext(NOW), m.StatePatch())
        )
        strategy.scan_candidates = MagicMock(return_value=("a", "b"))
        engine = self.make_engine(strategy, MagicMock(), state)
        engine.BATCH_SLOT_COUNT = 1
        started, finished = asyncio.Event(), asyncio.Event()

        async def process(symbol, context):
            if symbol == "a":
                await started.wait()
                raise asyncio.CancelledError()
            started.set()
            finished.set()
            return m.ScanOutcome.PROCESSED

        engine.process_instrument = process
        await engine.run_market_cycle(NOW)
        self.assertTrue(finished.is_set())


class RuleTest(unittest.IsolatedAsyncioTestCase):
    def test_bn_ratio_constants_are_on_strategy_rule_not_data_source(self):
        self.assertEqual(m.AUTOBN.OI_DELTA_LONG_RATIO_WEIGHT, 0.4)
        self.assertEqual(m.BinanceMarketData.OI_QUERY_LIMIT, 30)

    def test_atr_and_probability_keep_previous_numeric_contract(self):
        from tokenDemo import autoTrade_pm as old

        rows = [
            [i, 10, 11 + (i % 3) * 0.1, 9 - (i % 2) * 0.1, 10 + i * 0.01, 100 + i]
            for i in range(30)
        ]
        frame = pd.DataFrame(
            rows, columns=["date", "open", "high", "low", "close", "volume"]
        )
        new_bn = m.AUTOBN(MagicMock())
        new_a = m.AUTOA(MagicMock())
        old_bn = old.AUTOBN.__new__(old.AUTOBN)
        self.assertEqual(
            new_bn.calculate_atr(m.MarketBars.from_binance(rows)),
            old_bn.calculate_atr(rows),
        )
        self.assertEqual(
            new_a.calculate_atr(m.MarketBars.from_frame(frame)),
            old.AUTOA.calculate_atr(frame),
        )
        for values in ([2, 2, 2], [1, 2, 3, 8]):
            self.assertEqual(
                m.sample_probability(values, 5),
                old_bn.calculate_chebyshev_probability(values, 5),
            )

    async def test_bn_long_price_stop_and_oi_stop_are_explicit(self):
        data = MagicMock()
        data.oi_5m = AsyncMock(return_value=[{"sumOpenInterest": 99}])
        strategy = m.AUTOBN(data)
        held = make_position()
        snapshot = m.StateSnapshot({"BTCUSDT": held}, {"BTCUSDT": make_observation()})
        before = await strategy.manage_position(
            "BTCUSDT", make_bars(7.5), snapshot, m.MarketContext(NOW)
        )
        self.assertEqual(before.intent.position.close_reason, "OI止损")
        held = make_position(tp_count=1)
        after = await strategy.manage_position(
            "BTCUSDT",
            make_bars(7.5),
            m.StateSnapshot({"BTCUSDT": held}, snapshot.observations),
            m.MarketContext(NOW),
        )
        self.assertEqual(after.intent.position.close_reason, "止盈后价格止损")

    async def test_a_share_volume_stop_uses_volume_guard(self):
        strategy = m.AUTOA(MagicMock())
        held = make_position("000001", guard=m.VolumeStop(volume=100))
        snapshot = m.StateSnapshot(
            {"000001": held}, {"000001": make_observation("000001")}
        )
        decision = await strategy.manage_position(
            "000001", make_bars(9, 50), snapshot, m.MarketContext(NOW)
        )
        self.assertEqual(decision.intent.kind, m.ActionKind.CLOSE)

    async def test_state_codec_keeps_autoa_volume_guard_and_extra_fields(self):
        directory, state, path = make_state("AUTOA")
        self.addCleanup(directory.cleanup)
        state.apply(
            m.StatePatch(
                positions=(
                    ("000001", make_position("000001", guard=m.VolumeStop(volume=100))),
                ),
                observations=(("000001", make_observation("000001", tags=())),),
            )
        )
        state.save()
        restored = m.TradingState("AUTOA", path)
        restored.load()
        self.assertIsInstance(
            restored.snapshot().positions["000001"].guard, m.VolumeStop
        )

    def test_atr_and_probability_match_previous_entry_algorithms(self):
        from tokenDemo import autoTrade_pm as old

        bn_data = MagicMock()
        bn = m.AUTOBN(bn_data)
        old_bn = old.AUTOBN.__new__(old.AUTOBN)
        a = m.AUTOA(MagicMock())
        old_a = old.AUTOA
        raw = [
            [i, 10, 11 + (i % 3) * 0.1, 9 - (i % 2) * 0.1, 10 + i * 0.01, 100 + i]
            for i in range(30)
        ]
        frame = pd.DataFrame(
            raw, columns=["date", "open", "high", "low", "close", "volume"]
        )
        named = m.MarketBars.from_binance(raw)
        self.assertEqual(bn.calculate_atr(named), old_bn.calculate_atr(raw))
        self.assertEqual(a.calculate_atr(named), old_a.calculate_atr(frame))
        values = [row[4] for row in raw]
        current = m.sample_probability(values, 10)
        expected = old_bn.calculate_chebyshev_probability(values, 10)
        self.assertEqual(
            (current["mean"], current["std"]), (expected["mean"], expected["std"])
        )
        self.assertEqual(
            current,
            expected,
        )

    async def test_bn_open_decision_has_typed_oi_guard_and_no_state_write(self):
        data = MagicMock()
        data.basis_rate = AsyncMock(return_value=0)
        strategy = m.AUTOBN(data)
        strategy.check_side = AsyncMock(return_value=(True, 1.1, 88))
        bars_value = make_bars(11, 200)
        state = m.StateSnapshot({}, {"BTCUSDT": make_observation()})
        decision = await strategy.evaluate_signal(
            "BTCUSDT", bars_value, state, m.MarketContext(NOW)
        )
        self.assertIsInstance(decision.intent, m.TradeIntent)
        self.assertIsInstance(decision.intent.position.guard, m.OIStop)
        self.assertEqual(decision.intent.position.guard.open_interest, 88)
        self.assertEqual(state.positions, {})

    async def test_autoa_bz_decision_uses_volume_guard(self):
        data = MagicMock()
        strategy = m.AUTOA(data)
        historical = m.MarketBars(
            times=tuple(range(30)),
            opens=tuple([10] * 29 + [12]),
            highs=tuple([11] * 29 + [14]),
            lows=tuple([9] * 29 + [7]),
            closes=tuple([10.5] * 29 + [12.5]),
            volumes=tuple([100] * 15 + [110] * 14 + [500]),
        )
        state = m.StateSnapshot({}, {"000001": make_observation("000001", tags=())})
        decision = await strategy.evaluate_signal(
            "000001", historical, state, m.MarketContext(NOW)
        )
        self.assertIsInstance(decision.intent, m.TradeIntent)
        self.assertIsInstance(decision.intent.position.guard, m.VolumeStop)

    async def test_daily_report_ignores_unregistered_binance_position(self):
        data = MagicMock()
        data.account_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "BTCUSDT",
                    "positionSide": "LONG",
                    "entryPrice": "10",
                    "notional": "20",
                    "unRealizedProfit": "1",
                },
                {
                    "symbol": "EXTERNAL",
                    "positionSide": "LONG",
                    "entryPrice": "10",
                    "notional": "20",
                    "unRealizedProfit": "1",
                },
            ]
        )
        data.gateway.account = AsyncMock(return_value={"equity": 1000})
        strategy = m.AUTOBN(data)
        state = m.StateSnapshot({"BTCUSDT": make_position()}, {})
        report = await strategy.build_daily_report(NOW, state)
        self.assertIn("BTCUSDT", report.content)
        self.assertNotIn("EXTERNAL", report.content)

    async def test_close_order_unknown_survives_cancel_without_resubmit(self):
        gateway = make_gateway()
        gateway.submit = AsyncMock(side_effect=asyncio.CancelledError())
        gateway.query_order = AsyncMock(
            return_value={"status": "NEW", "executedQty": "0"}
        )
        executor = m.BinanceExecutor(
            gateway,
            MagicMock(precision=MagicMock(return_value=Decimal("0.001"))),
            MagicMock(),
        )
        intent = m.TradeIntent(m.ActionKind.CLOSE, "BTCUSDT", make_position(), 8)
        result = await executor.submit(
            m.PreparedOrder(intent, 1, 8, 10, client_order_id="at-cancel")
        )
        self.assertIn(
            result.status, (m.ExecutionStatus.UNKNOWN, m.ExecutionStatus.FAILED)
        )
        gateway.submit.assert_awaited_once()


class RecoveryRegressionTest(unittest.IsolatedAsyncioTestCase):
    def engine(self, strategy, executor, state):
        return make_test_engine(
            strategy,
            executor,
            state,
            MagicMock(send=AsyncMock()),
            MagicMock(flush_pending_records=AsyncMock()),
            MagicMock(),
            MagicMock(),
        )

    async def test_definite_rejection_does_not_freeze_existing_position(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position()
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "3",
                "entryPrice": "10",
                "notional": "30",
            }
        ]
        gateway.submit.side_effect = BadRequestError("Margin is insufficient.", -2019)
        gateway.query_order.side_effect = BadRequestError(
            "Order does not exist.", -2013
        )
        data = MagicMock(precision=MagicMock(return_value=Decimal(".001")))
        data.fetch_bars = AsyncMock(return_value=make_bars())
        strategy = m.AUTOBN(data)
        strategy.manage_position = AsyncMock(return_value=m.Decision())
        strategy.after_instrument = AsyncMock(return_value=m.StatePatch())
        executor = m.BinanceExecutor(gateway, data, MagicMock())
        runtime = self.engine(strategy, executor, state)
        self.assertFalse(
            await runtime.execute_action(
                m.TradeIntent(m.ActionKind.ADD, "BTCUSDT", held, 9, 1),
                m.MarketContext(NOW),
            )
        )
        await runtime.process_instrument("BTCUSDT", m.MarketContext(NOW))
        self.assertEqual(state.pending_symbols(), ())
        strategy.manage_position.assert_awaited_once()
        gateway.query_order.assert_not_awaited()
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.pending_symbols(), ())

    async def test_ambiguous_timeout_still_blocks_resubmission(self):
        gateway = make_gateway()
        gateway.submit.side_effect = BadRequestError("Execution status unknown.", -1007)
        gateway.query_order.side_effect = BadRequestError(
            "Order does not exist.", -2013
        )
        executor = m.BinanceExecutor(gateway, MagicMock(), MagicMock())
        order = m.PreparedOrder(
            m.TradeIntent(m.ActionKind.OPEN, "BTCUSDT", make_position(), 10),
            1,
            10,
            10,
            client_order_id="at-timeout",
        )
        self.assertEqual(
            (await executor.submit(order)).status, m.ExecutionStatus.UNKNOWN
        )
        gateway.query_order.assert_awaited_once()

    async def test_virtual_pending_is_discarded_then_current_market_is_checked(self):
        directory, state, path = make_state("AUTOA")
        self.addCleanup(directory.cleanup)
        held = make_position("000001", guard=m.VolumeStop(volume=10))
        state.apply(m.StatePatch(positions=(("000001", held),)))
        state.remember_order(
            m.PreparedOrder(
                m.TradeIntent(m.ActionKind.CLOSE, "000001", held, 8),
                100,
                8,
                10,
                client_order_id="at-old-virtual",
            )
        )
        state.save()
        restored = m.TradingState("AUTOA", path)
        restored.load()
        data = MagicMock(fetch_bars=AsyncMock(return_value=make_bars()))
        strategy = m.AUTOA(data)
        strategy.manage_position = AsyncMock(return_value=m.Decision())
        runtime = self.engine(strategy, m.AshareExecutor(), restored)
        for _ in range(2):
            await runtime.process_instrument("000001", m.MarketContext(NOW))
        self.assertEqual(restored.pending_symbols(), ())
        self.assertIn("000001", restored.snapshot().positions)
        strategy.manage_position.assert_awaited()

    async def test_virtual_stop_does_not_require_disk_write(self):
        directory, state, _ = make_state("AUTOA")
        self.addCleanup(directory.cleanup)
        held = make_position("000001", guard=m.VolumeStop(volume=10))
        state.apply(m.StatePatch(positions=(("000001", held),)))
        state.save = MagicMock(side_effect=OSError("disk unavailable"))
        runtime = self.engine(m.AUTOA(MagicMock()), m.AshareExecutor(), state)
        self.assertTrue(
            await runtime.execute_action(
                m.TradeIntent(m.ActionKind.CLOSE, "000001", held, 7),
                m.MarketContext(NOW),
            )
        )
        self.assertNotIn("000001", state.snapshot().positions)
        self.assertEqual(state.pending_symbols(), ())
        state.save.assert_not_called()

    async def test_open_refuses_residual_exchange_position_after_restart(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "3152",
                "entryPrice": "10",
                "notional": "31.52",
            }
        ]
        executor = m.BinanceExecutor(
            gateway,
            MagicMock(precision=MagicMock(return_value=Decimal(".001"))),
            MagicMock(),
        )
        self.assertIsNone(
            await executor.prepare(
                m.TradeIntent(m.ActionKind.OPEN, "BTCUSDT", make_position(), 10)
            )
        )
        gateway.submit.assert_not_awaited()

    async def test_startup_refresh_reads_actual_positions_and_preserves_strategy(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position(tp_count=2)
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        gateway = make_gateway()
        gateway.call.return_value = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "quantityPrecision": 3,
                    "quotePrecision": 8,
                }
            ]
        }
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "30",
                "entryPrice": "11",
                "notional": "330",
            }
        ]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.fetch_bars = AsyncMock(return_value=make_bars())
        strategy = m.AUTOBN(data)
        strategy.manage_position = AsyncMock(return_value=m.Decision())
        strategy.after_instrument = AsyncMock(return_value=m.StatePatch())
        runtime = self.engine(
            strategy, m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        await runtime.run_market_cycle(NOW)
        restored = state.snapshot().positions["BTCUSDT"]
        self.assertEqual(restored.entry_price, 11)
        self.assertEqual(
            (restored.tp_count, restored.stop_loss, restored.take_profit), (2, 8, 20)
        )
        gateway.positions.assert_awaited_once()

    async def test_add_cannot_create_new_position_when_exchange_is_flat(self):
        gateway = make_gateway()
        executor = m.BinanceExecutor(
            gateway,
            MagicMock(precision=MagicMock(return_value=Decimal(".001"))),
            MagicMock(),
        )
        order = await executor.prepare(
            m.TradeIntent(m.ActionKind.ADD, "BTCUSDT", make_position(), 9, 1)
        )
        self.assertTrue(order.no_position)
        self.assertEqual(
            (await executor.submit(order)).status, m.ExecutionStatus.NO_POSITION
        )
        gateway.submit.assert_not_awaited()

    async def test_partial_close_recovers_remaining_state_without_full_snapshot_write(
        self,
    ):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        original_disk = path.read_bytes()
        held = make_position()
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        gateway = make_gateway()
        gateway.position_amount.side_effect = [(100, 10), (30, 10)]
        gateway.submit.return_value = {
            "status": "FILLED",
            "executedQty": "70",
            "origQty": "70",
        }
        data = MagicMock(precision=MagicMock(return_value=Decimal(".001")))
        runtime = self.engine(
            m.AUTOBN(data), m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        await runtime.execute_action(
            m.TradeIntent(
                m.ActionKind.CLOSE,
                "BTCUSDT",
                held,
                12,
                1,
                ratio=0.7,
                take_profit_stage="first",
            ),
            m.MarketContext(NOW),
        )
        self.assertEqual(path.read_bytes(), original_disk)
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.snapshot().positions["BTCUSDT"].tp_count, 1)
        self.assertEqual(restored.snapshot().positions["BTCUSDT"].stop_loss, 8)
        self.assertEqual(restored.pending_symbols(), ())

    async def test_failed_add_still_refreshes_observation(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        state.apply(
            m.StatePatch(
                positions=(("BTCUSDT", make_position()),),
                observations=(("BTCUSDT", make_observation()),),
            )
        )
        data = MagicMock(fetch_bars=AsyncMock(return_value=make_bars(8.5, 200)))
        strategy = m.AUTOBN(data)
        intent = m.TradeIntent(m.ActionKind.ADD, "BTCUSDT", make_position(), 8.5, 1)
        strategy.manage_position = AsyncMock(return_value=m.Decision(intent=intent))
        strategy.after_instrument = AsyncMock(return_value=m.StatePatch())
        executor = MagicMock(REQUIRES_ORDER_JOURNAL=False)
        executor.prepare = AsyncMock(return_value=m.PreparedOrder(intent, 1, 8.5, 10))
        executor.submit = AsyncMock(
            return_value=m.ExecutionResult(m.ExecutionStatus.FAILED)
        )
        runtime = self.engine(strategy, executor, state)
        await runtime.process_instrument("BTCUSDT", m.MarketContext(NOW))
        strategy.after_instrument.assert_awaited_once()

    async def test_history_transient_502_retries_same_source_with_same_volume_unit(
        self,
    ):
        data, session = make_ashare_data()
        session.get.side_effect = [
            http_response({}, status=502),
            http_response(tencent_quote(), callback="quote"),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
            )
        self.assertEqual(len(bars), 20)
        self.assertEqual(bars.volumes[-2:], (100, 1234))
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(
            session.get.call_args_list[0].args[0], session.get.call_args_list[1].args[0]
        )

    async def test_journal_checkpoint_does_not_revert_later_rail_updates(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position()
        order = m.PreparedOrder(
            m.TradeIntent(m.ActionKind.OPEN, "BTCUSDT", held, 10),
            1,
            10,
            10,
            client_order_id="at-checkpoint",
        )
        state.remember_order(order, durable=True)
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        state.resolve_order("BTCUSDT", durable=True)
        journal = Path(state.order_journal_file)
        previous_journal = journal.read_bytes()
        state.apply(
            m.StatePatch(
                positions=(("BTCUSDT", held.model_copy(update={"take_profit": 19})),)
            )
        )
        state.save()
        # 模拟快照已替换、旧日志还没清理时进程中断。
        journal.write_bytes(previous_journal)
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.snapshot().positions["BTCUSDT"].take_profit, 19)
        self.assertEqual(restored.pending_symbols(), ())

    async def test_incomplete_journal_tail_does_not_poison_next_event(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position()
        order = m.PreparedOrder(
            m.TradeIntent(m.ActionKind.OPEN, "BTCUSDT", held, 10),
            1,
            10,
            10,
            client_order_id="at-tail",
        )
        state.remember_order(order, durable=True)
        with Path(state.order_journal_file).open("ab") as stream:
            stream.write(b'{"sequence":2,"type":"resol')
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.pending_symbols(), ("BTCUSDT",))
        restored.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        restored.resolve_order("BTCUSDT", durable=True)
        again = m.TradingState("AUTOBN", path)
        again.load()
        self.assertEqual(again.pending_symbols(), ())
        self.assertEqual(again.snapshot().positions["BTCUSDT"], held)

    async def test_cancel_during_post_fill_query_keeps_confirmed_stage_durable(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position()
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        gateway = make_gateway()
        querying = asyncio.Event()
        calls = 0

        async def amount(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 100, 10
            querying.set()
            await asyncio.Event().wait()

        gateway.position_amount.side_effect = amount
        gateway.submit.return_value = {
            "status": "FILLED",
            "executedQty": "70",
            "origQty": "70",
        }
        data = MagicMock(precision=MagicMock(return_value=Decimal(".001")))
        runtime = self.engine(
            m.AUTOBN(data), m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        task = asyncio.create_task(
            runtime.execute_action(
                m.TradeIntent(
                    m.ActionKind.CLOSE,
                    "BTCUSDT",
                    held,
                    12,
                    1,
                    ratio=0.7,
                    take_profit_stage="first",
                ),
                m.MarketContext(NOW),
            )
        )
        await asyncio.wait_for(querying.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.snapshot().positions["BTCUSDT"].tp_count, 1)
        self.assertEqual(restored.pending_symbols(), ())
        gateway.submit.assert_awaited_once()

    async def test_real_order_is_not_submitted_without_recovery_log(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        state.remember_order = MagicMock(side_effect=OSError("journal unavailable"))
        gateway = make_gateway()
        data = MagicMock(precision=MagicMock(return_value=Decimal(".001")))
        runtime = self.engine(
            m.AUTOBN(data), m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        self.assertFalse(
            await runtime.execute_action(
                m.TradeIntent(
                    m.ActionKind.OPEN,
                    "BTCUSDT",
                    make_position(),
                    10,
                    observation=make_observation(),
                ),
                m.MarketContext(NOW),
            )
        )
        gateway.submit.assert_not_awaited()

    async def test_daily_refresh_reuses_report_positions_without_minute_sync(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        gateway = make_gateway()
        gateway.call.return_value = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "quantityPrecision": 3,
                    "quotePrecision": 8,
                }
            ]
        }
        data = m.BinanceMarketData(gateway, MagicMock())
        data.fetch_bars = AsyncMock(return_value=make_bars())
        strategy = m.AUTOBN(data)
        strategy.evaluate_signal = AsyncMock(return_value=m.Decision())
        strategy.after_instrument = AsyncMock(return_value=m.StatePatch())
        runtime = self.engine(
            strategy, m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        runtime.http.timeout = 0.1
        await runtime.run_market_cycle(NOW)
        await runtime.run_market_cycle(NOW + pd.Timedelta(minutes=15))
        gateway.positions.assert_awaited_once()
        await runtime.push_daily_report(NOW + pd.Timedelta(days=1))
        self.assertEqual(gateway.positions.await_count, 2)

    async def test_invalid_position_response_is_not_confirmed_zero(self):
        gateway = m.BinanceGateway(market_client=MagicMock(), papi_client=MagicMock())
        for payload in (None, {}, [{"symbol": "BTCUSDT"}]):
            with self.subTest(payload=payload):
                gateway.call = AsyncMock(return_value=payload)
                self.assertIsNone(await gateway.position_amount("BTCUSDT", "LONG"))

    async def test_scan_log_distinguishes_no_data_from_rule_skips(self):
        directory, state, _ = make_state("AUTOA")
        self.addCleanup(directory.cleanup)
        strategy = MagicMock()
        strategy.prepare_cycle = AsyncMock(
            return_value=(m.MarketContext(NOW), m.StatePatch())
        )
        strategy.scan_candidates.return_value = tuple(str(i) for i in range(5))
        runtime = self.engine(strategy, m.AshareExecutor(), state)
        runtime.BATCH_SLOT_COUNT = 1
        outcomes = tuple(m.ScanOutcome)
        runtime.process_instrument = AsyncMock(
            side_effect=lambda symbol, context: outcomes[int(symbol)]
        )
        await runtime.run_market_cycle(NOW)
        message = runtime.logger.info.call_args.args[0]
        for text in ("成功:1/5", "跳过:1", "无行情:1", "待确认:1", "失败:1"):
            self.assertIn(text, message)

    async def test_dated_today_bar_confirms_current_day_when_calendar_unavailable(self):
        data, session = make_ashare_data()
        session.get.side_effect = [
            http_response(tencent_quote(), callback="quote"),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001",
                m.MarketContext(NOW, "2026-08-13", "2026-09-09", exit_only=True),
            )
        self.assertEqual(len(bars), 20)
        session.get.side_effect = None
        session.get.return_value = http_response(
            tencent_quote(date="20260908"), callback="quote"
        )
        with patch.object(m, "market_time", return_value=NOW):
            self.assertFalse(
                await data.fetch_bars(
                    "000001",
                    m.MarketContext(NOW, "2026-08-13", "2026-09-09", exit_only=True),
                )
            )

    async def test_jsonp_is_parsed_as_data_and_never_evaluated(self):
        data, session = make_ashare_data()
        response = MagicMock(status=200)
        response.text = AsyncMock(
            return_value='callback({"ok": true}); dangerous_call();'
        )
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=response)
        manager.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = manager
        with self.assertRaises(ValueError):
            await data._request("https://proxy.finance.qq.com/test")

    async def test_failed_pending_fsync_rolls_back_unsubmitted_order(self):
        directory, state, path = make_state()
        self.addCleanup(directory.cleanup)
        order = m.PreparedOrder(
            m.TradeIntent(m.ActionKind.CLOSE, "BTCUSDT", make_position(), 8),
            1,
            8,
            10,
            client_order_id="at-fsync",
        )
        with patch.object(m.os, "fsync", side_effect=OSError("fsync failed")):
            with self.assertRaises(OSError):
                state.remember_order(order, durable=True)
        restored = m.TradingState("AUTOBN", path)
        restored.load()
        self.assertEqual(restored.pending_symbols(), ())

    async def test_resolution_log_retry_does_not_repeat_record_or_stage(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position()
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        gateway = make_gateway()
        gateway.position_amount.return_value = (30, 10)
        gateway.query_order.return_value = {
            "status": "FILLED",
            "executedQty": "70",
            "origQty": "70",
        }
        data = MagicMock(precision=MagicMock(return_value=Decimal(".001")))
        runtime = self.engine(
            m.AUTOBN(data), m.BinanceExecutor(gateway, data, MagicMock()), state
        )
        order = m.PreparedOrder(
            m.TradeIntent(m.ActionKind.CLOSE, "BTCUSDT", held, 12, 1, 0.7, "first"),
            70,
            12,
            10,
            0.7,
            client_order_id="at-finalize",
        )
        state.remember_order(order, durable=True)
        with patch.object(
            state, "_append_order_event", side_effect=OSError("log failed")
        ):
            await runtime.process_instrument("BTCUSDT", m.MarketContext(NOW))
        await runtime.process_instrument("BTCUSDT", m.MarketContext(NOW))
        self.assertEqual(runtime.records.enqueue_close.call_count, 1)
        self.assertEqual(state.snapshot().positions["BTCUSDT"].tp_count, 1)
        self.assertEqual(state.pending_symbols(), ())
        runtime.notifications.send.assert_awaited_once()

    async def test_positions_refresh_is_independent_of_exchange_metadata(self):
        directory, state, _ = make_state()
        self.addCleanup(directory.cleanup)
        held = make_position(tp_count=2)
        state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
        for metadata in (OSError("exchange metadata down"), {"symbols": []}):
            with self.subTest(metadata=metadata):
                gateway = make_gateway()
                gateway.call = (
                    AsyncMock(side_effect=metadata)
                    if isinstance(metadata, Exception)
                    else AsyncMock(return_value=metadata)
                )
                gateway.positions.return_value = [
                    {
                        "symbol": "BTCUSDT",
                        "positionSide": "LONG",
                        "positionAmt": "30",
                        "entryPrice": "11",
                    }
                ]
                strategy = m.AUTOBN(m.BinanceMarketData(gateway, MagicMock()))
                _, patch_value = await strategy.prepare_cycle(NOW, state.snapshot())
                self.assertEqual(dict(patch_value.positions)["BTCUSDT"].entry_price, 11)
                self.assertEqual(dict(patch_value.positions)["BTCUSDT"].tp_count, 2)

    async def test_malformed_history_is_skipped_without_switching_sources(self):
        data, session = make_ashare_data()
        session.get.side_effect = [
            http_response(
                {
                    "code": 0,
                    "data": {
                        "sz000001": {
                            "qt": tencent_quote()["data"]["sz000001"]["qt"],
                            "qfqday": [["2026-09-08", "10"]],
                        }
                    },
                }
            ),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
            )
        self.assertFalse(bars)
        self.assertEqual(data.cache.history, {})
        self.assertTrue(
            all("finance.qq.com" in call.args[0] for call in session.get.call_args_list)
        )

    async def test_close_record_order_id_is_idempotent_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "records.xlsx")
            record = dict(
                source="AUTOBN",
                symbol="BTCUSDT",
                position_side="LONG",
                entry_price=10,
                close_price=12,
                close_amount=70,
                realized_pnl=140,
                pnl_percent=0.2,
                execution_id="at-same-fill",
            )
            for _ in range(2):
                records = m.CloseRecordManager(filename)
                records.enqueue_close(**record)
                await records.flush_pending_records()
            self.assertEqual(len(pd.read_excel(filename, sheet_name="币安期货")), 1)

    async def test_malformed_metadata_does_not_block_daily_position_patch(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "30",
                "entryPrice": "11",
            }
        ]
        held = make_position(tp_count=2)
        for response in (
            {"symbols": [{"symbol": "BTCUSDT"}]},
            ["invalid"],
            {"symbols": "invalid"},
        ):
            with self.subTest(response=response):
                data = m.BinanceMarketData(gateway, MagicMock())
                data.cache.universe = ("OLDUSDT",)
                gateway.call = AsyncMock(return_value=response)
                changed, update = await m.AUTOBN(data).refresh_universe(
                    NOW, m.StateSnapshot({"BTCUSDT": held}, {})
                )
                self.assertFalse(changed)
                self.assertEqual(data.universe(), ("OLDUSDT",))
                self.assertEqual(dict(update.positions)["BTCUSDT"].entry_price, 11)
                self.assertEqual(dict(update.positions)["BTCUSDT"].tp_count, 2)


class MissingOIGuardTest(unittest.IsolatedAsyncioTestCase):
    def test_oi_threshold_uses_larger_candidate(self):
        strategy = m.AUTOBN(MagicMock())
        self.assertAlmostEqual(
            strategy._oi_stop_threshold(200, {"mean": 100, "std": 1}), 180
        )
        self.assertAlmostEqual(
            strategy._oi_stop_threshold(100, {"mean": 100, "std": 2}), 120
        )

    async def test_resolved_direction_conflict_restores_normal_position_management(
        self,
    ):
        data = m.BinanceMarketData(make_gateway(), MagicMock())
        data.oi_5m = AsyncMock(return_value=[{"sumOpenInterest": 120}])
        held = make_position()
        snapshot = m.StateSnapshot({"BTCUSDT": held}, {})
        strategy = m.AUTOBN(data)
        long = {
            "symbol": "BTCUSDT",
            "positionSide": "LONG",
            "positionAmt": "10",
            "entryPrice": "10",
        }
        short = {
            "symbol": "BTCUSDT",
            "positionSide": "SHORT",
            "positionAmt": "-2",
            "entryPrice": "10",
        }
        strategy._positions_patch([long, short], snapshot)
        self.assertEqual(data.recovery_symbols(), ("BTCUSDT",))
        strategy._positions_patch([long], snapshot)
        self.assertEqual(data.recovery_symbols(), ())
        decision = await strategy.manage_position(
            "BTCUSDT", make_bars(7), snapshot, m.MarketContext(NOW)
        )
        self.assertEqual(decision.intent.kind, m.ActionKind.ADD)

    async def test_conflicting_account_directions_block_add_but_keep_exits(self):
        data = m.BinanceMarketData(make_gateway(), MagicMock())
        data.require_position_recovery("BTCUSDT")
        data.oi_5m = AsyncMock(return_value=[{"sumOpenInterest": 120}])
        held = make_position()
        strategy = m.AUTOBN(data)
        for price, expected in ((7, None), (21, m.ActionKind.CLOSE)):
            result = await strategy.manage_position(
                "BTCUSDT",
                make_bars(price),
                m.StateSnapshot({"BTCUSDT": held}, {}),
                m.MarketContext(NOW),
            )
            self.assertEqual(result.intent.kind if result.intent else None, expected)

    async def test_recovery_rejects_other_symbol_response(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "OTHERUSDT",
                "positionSide": "LONG",
                "positionAmt": "1",
                "entryPrice": "10",
            }
        ]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.require_position_recovery("BTCUSDT")
        result = await m.AUTOBN(data).evaluate_signal(
            "BTCUSDT", make_bars(10), m.StateSnapshot({}, {}), m.MarketContext(NOW)
        )
        self.assertEqual(result.patch.positions, ())
        self.assertIsNone(result.intent)
        self.assertEqual(data.recovery_symbols(), ("BTCUSDT",))

    async def test_unregistered_account_position_recovers_n_without_new_order(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "10",
                "entryPrice": "10",
            }
        ]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.oi_5m = AsyncMock(return_value=[{"sumOpenInterest": 120}])
        data.oi_history = AsyncMock(
            return_value=[{"sumOpenInterest": 100 + i % 3} for i in range(30)]
        )
        strategy = m.AUTOBN(data)
        strategy._positions_patch(
            gateway.positions.return_value, m.StateSnapshot({}, {})
        )
        decision = await strategy.evaluate_signal(
            "BTCUSDT", make_bars(10), m.StateSnapshot({}, {}), m.MarketContext(NOW)
        )
        held = dict(decision.patch.positions)["BTCUSDT"]
        self.assertEqual(held.strategy, (m.StrategyTag.N,))
        self.assertGreater(held.guard.open_interest, 0)
        self.assertGreater(held.stop_loss, 0)
        self.assertEqual(held.entry_price, 10)
        self.assertIsNone(decision.intent)
        self.assertEqual(data.recovery_symbols(), ())
        gateway.submit.assert_not_awaited()

    async def test_unregistered_recovery_retries_without_opening_on_missing_oi(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "LONG",
                "positionAmt": "10",
                "entryPrice": "10",
            }
        ]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.require_position_recovery("BTCUSDT")
        data.oi_5m = AsyncMock(return_value=[])
        data.oi_history = AsyncMock(return_value=[])
        decision = await m.AUTOBN(data).evaluate_signal(
            "BTCUSDT", make_bars(10), m.StateSnapshot({}, {}), m.MarketContext(NOW)
        )
        self.assertEqual(decision.patch.positions, ())
        self.assertIsNone(decision.intent)
        self.assertEqual(data.recovery_symbols(), ("BTCUSDT",))
        gateway.submit.assert_not_awaited()

    async def test_closed_recovery_candidate_does_not_permanently_block_new_signals(
        self,
    ):
        gateway = make_gateway()
        data = m.BinanceMarketData(gateway, MagicMock())
        data.require_position_recovery("BTCUSDT")
        decision = await m.AUTOBN(data).evaluate_signal(
            "BTCUSDT", make_bars(10), m.StateSnapshot({}, {}), m.MarketContext(NOW)
        )
        self.assertEqual(data.recovery_symbols(), ())
        self.assertEqual(decision.patch.positions, ())

    async def test_short_recovery_has_price_rails_without_oi_requests(self):
        gateway = make_gateway()
        gateway.positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionSide": "SHORT",
                "positionAmt": "-10",
                "entryPrice": "10",
            }
        ]
        data = m.BinanceMarketData(gateway, MagicMock())
        data.require_position_recovery("BTCUSDT")
        data.oi_5m = AsyncMock()
        decision = await m.AUTOBN(data).evaluate_signal(
            "BTCUSDT", make_bars(10), m.StateSnapshot({}, {}), m.MarketContext(NOW)
        )
        held = dict(decision.patch.positions)["BTCUSDT"]
        self.assertEqual(held.position_side, m.PositionSide.SHORT)
        self.assertGreater(held.stop_loss, held.take_profit)
        data.oi_5m.assert_not_awaited()

    async def test_recovery_uses_peak_and_exits_if_current_already_below_guard(self):
        values = [100 + i % 3 for i in range(24)] + [150] * 6
        data = MagicMock(
            oi_5m=AsyncMock(return_value=[{"sumOpenInterest": 105}]),
            oi_history=AsyncMock(return_value=[{"sumOpenInterest": x} for x in values]),
        )
        held = make_position(
            guard=m.OIStop(open_interest=0), strategy=(m.StrategyTag.N,)
        )
        decision = await m.AUTOBN(data).manage_position(
            "BTCUSDT",
            make_bars(8.5),
            m.StateSnapshot({"BTCUSDT": held}, {}),
            m.MarketContext(NOW),
        )
        expected = max(
            150 * 0.9,
            m.sample_probability(values[:-6], 105)["mean"]
            + m.sample_probability(values[:-6], 105)["std"] * 10,
        )
        self.assertAlmostEqual(
            dict(decision.patch.positions)["BTCUSDT"].guard.open_interest, expected
        )
        self.assertEqual(decision.intent.kind, m.ActionKind.CLOSE)
        self.assertEqual(decision.intent.position.close_reason, "OI止损")
        self.assertEqual(decision.intent.ratio, 1)

    async def test_missing_guard_recovers_original_formula_before_dca(self):
        data = MagicMock(
            oi_5m=AsyncMock(return_value=[{"sumOpenInterest": 120}]),
            oi_history=AsyncMock(
                return_value=[{"sumOpenInterest": 100 + i % 3} for i in range(30)]
            ),
        )
        strategy = m.AUTOBN(data)
        held = make_position(
            guard=m.OIStop(open_interest=0),
            strategy=(m.StrategyTag.N, m.StrategyTag.DCA),
        )
        decision = await strategy.manage_position(
            "BTCUSDT",
            make_bars(8.5),
            m.StateSnapshot({"BTCUSDT": held}, {}),
            m.MarketContext(NOW),
        )
        recovered = dict(decision.patch.positions)["BTCUSDT"]
        sample = [100 + i % 3 for i in range(24)]
        stats = m.sample_probability(sample, 120)
        self.assertAlmostEqual(
            recovered.guard.open_interest, max(108, stats["mean"] + stats["std"] * 10)
        )
        self.assertEqual(recovered.stop_loss, held.stop_loss)
        self.assertEqual(recovered.strategy, held.strategy)
        self.assertEqual(recovered.tp_count, 0)
        if decision.intent:
            self.assertEqual(decision.intent.position.guard, recovered.guard)

    async def test_recovery_failure_blocks_add_but_not_exit(self):
        for value in (0, float("nan"), -1):
            data = MagicMock(
                oi_5m=AsyncMock(return_value=[]), oi_history=AsyncMock(return_value=[])
            )
            strategy = m.AUTOBN(data)
            held = make_position(guard=m.OIStop(open_interest=value))
            decision = await strategy.manage_position(
                "BTCUSDT",
                make_bars(7),
                m.StateSnapshot({"BTCUSDT": held}, {}),
                m.MarketContext(NOW),
            )
            self.assertIsNone(decision.intent)
            exit_decision = await strategy.manage_position(
                "BTCUSDT",
                make_bars(21),
                m.StateSnapshot({"BTCUSDT": held}, {}),
                m.MarketContext(NOW),
            )
            self.assertEqual(exit_decision.intent.kind, m.ActionKind.CLOSE)

    async def test_valid_guard_is_not_recalculated(self):
        data = MagicMock(
            oi_5m=AsyncMock(return_value=[{"sumOpenInterest": 120}]),
            oi_history=AsyncMock(),
        )
        held = make_position()
        decision = await m.AUTOBN(data).manage_position(
            "BTCUSDT",
            make_bars(10),
            m.StateSnapshot({"BTCUSDT": held}, {}),
            m.MarketContext(NOW),
        )
        self.assertEqual(dict(decision.patch.positions)["BTCUSDT"].guard, held.guard)
        data.oi_history.assert_not_awaited()


class CoreTradingParityTest(unittest.IsolatedAsyncioTestCase):
    async def test_bn_decisions_match_original_except_authorized_long_price_stop(self):
        from tokenDemo import autoTrade_pm as old

        for side, count, adds, atr, price, oi in itertools.product(
            (m.PositionSide.LONG, m.PositionSide.SHORT),
            (0, 1),
            (0, 1),
            (0, 1),
            (7, 8, 8.5, 9.5, 10, 10.5, 11, 20, 22),
            (90, 110),
        ):
            with self.subTest(
                side=side, count=count, adds=adds, atr=atr, price=price, oi=oi
            ):
                held = make_position(
                    side=side,
                    tp_count=count,
                    strategy=(m.StrategyTag.BZ,) + (m.StrategyTag.DCA,) * adds,
                )
                state = m.TradingState("AUTOBN", "unused")
                state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
                legacy = old.AUTOBN.__new__(old.AUTOBN)
                legacy.alert_all = json.loads(json.dumps(state.serialize()))
                legacy.logger = MagicMock()
                legacy.calculate_atr = lambda _: atr
                legacy._get_oi_5m_data = AsyncMock(
                    return_value=[{"sumOpenInterest": oi}]
                )
                actions = []

                async def close(
                    symbol, position, atr_value, px, ratio=1, *, take_profit_stage=None
                ):
                    actions.append(
                        ("CLOSE", ratio, take_profit_stage, position.close_reason)
                    )

                async def add(*args, **kwargs):
                    actions.append(("ADD", 1, None, ""))

                legacy.close_bn_position = close
                legacy._add_to_position = add
                bars = make_bars(price)
                rows = list(
                    zip(
                        bars.times,
                        bars.opens,
                        bars.highs,
                        bars.lows,
                        bars.closes,
                        bars.volumes,
                    )
                )
                await legacy._manage_position(
                    "BTCUSDT",
                    old.Position.model_validate(
                        legacy.alert_all["POSITIONS"]["BTCUSDT"]
                    ),
                    rows,
                    price,
                )
                strategy = m.AUTOBN(
                    MagicMock(oi_5m=AsyncMock(return_value=[{"sumOpenInterest": oi}]))
                )
                strategy.calculate_atr = lambda _: atr
                decision = await strategy.manage_position(
                    "BTCUSDT", bars, state.snapshot(), m.MarketContext(NOW)
                )
                actual = (
                    []
                    if decision.intent is None
                    else [
                        (
                            decision.intent.kind.value,
                            decision.intent.ratio,
                            decision.intent.take_profit_stage,
                            decision.intent.position.close_reason,
                        )
                    ]
                )
                if side == m.PositionSide.LONG and count and price <= held.stop_loss:
                    self.assertEqual(actual, [("CLOSE", 1, None, "止盈后价格止损")])
                else:
                    self.assertEqual(actual, actions)
                    if not actions:
                        state.apply(decision.patch)
                        self.assertEqual(
                            state.serialize(), json.loads(json.dumps(legacy.alert_all))
                        )

    def test_bn_post_profit_targets_keep_original_formula_and_fixed_long_stop(self):
        from tokenDemo import autoTrade_pm as old

        for side, stage, atr, price, count in itertools.product(
            (m.PositionSide.LONG, m.PositionSide.SHORT),
            (None, "first", "regular"),
            (0, 1),
            (7, 10, 12),
            (0, 2),
        ):
            with self.subTest(
                side=side, stage=stage, atr=atr, price=price, count=count
            ):
                held = make_position(side=side, tp_count=count)
                state = m.TradingState("AUTOBN", "unused")
                state.apply(m.StatePatch(positions=(("BTCUSDT", held),)))
                legacy = old.AUTOBN.__new__(old.AUTOBN)
                legacy.alert_all = state.serialize()
                old_held = old.Position.model_validate(
                    legacy.alert_all["POSITIONS"]["BTCUSDT"]
                )
                legacy._apply_close_state("BTCUSDT", old_held, atr, price, stage)
                updated = m.AUTOBN(MagicMock()).position_after_take_profit(
                    m.TradeIntent(
                        m.ActionKind.CLOSE, "BTCUSDT", held, price, atr, 0.7, stage
                    ),
                    m.ExecutionResult(m.ExecutionStatus.FILLED),
                )
                state.apply(m.StatePatch(positions=(("BTCUSDT", updated),)))
                expected = old_held.model_dump(mode="json")
                if side == m.PositionSide.LONG:
                    expected["stop_loss"] = held.stop_loss
                self.assertEqual(state.serialize()["POSITIONS"]["BTCUSDT"], expected)

    async def test_autoa_position_and_open_states_match_original(self):
        from tokenDemo import autoTrade_pm as old

        history = AsyncMock()
        with (
            patch.object(old.AUTOA, "stock_zh_a_hist", history),
            patch.object(old.AUTOA, "send_msg", AsyncMock()),
            patch.object(old.CloseRecordManager, "enqueue_close", MagicMock()),
            patch.object(old.AUTOA, "alert_all", {}),
        ):
            for is_n, adds, atr, price, exit_only, opened_today in itertools.product(
                (False, True),
                (0, 1),
                (0, 1),
                (7, 8, 8.5, 10, 10.5, 20, 21),
                (False, True),
                (False, True),
            ):
                held = make_position(
                    "000001",
                    guard=m.VolumeStop(volume=50),
                    strategy=(m.StrategyTag.BZ,)
                    + ((m.StrategyTag.N,) if is_n else ())
                    + (m.StrategyTag.DCA,) * adds,
                    date=20260909 if opened_today else 20260908,
                )
                state = m.TradingState("AUTOA", "unused")
                state.apply(
                    m.StatePatch(
                        positions=(("000001", held),),
                        observations=(("000001", make_observation("000001")),),
                    )
                )
                old.AUTOA.alert_all = json.loads(json.dumps(state.serialize()))
                bars = make_bars(price)
                history.return_value = pd.DataFrame(
                    list(
                        zip(
                            bars.times,
                            bars.opens,
                            bars.highs,
                            bars.lows,
                            bars.closes,
                            bars.volumes,
                        )
                    ),
                    columns=["date", "open", "high", "low", "close", "volume"],
                )
                with patch.object(old.AUTOA, "calculate_atr", return_value=atr):
                    await old.AUTOA.on_positions(
                        "000001",
                        ["2026-09-09", "2026-08-13"],
                        old.AUTOA.alert_all["POSITIONS"]["000001"],
                        NOW.replace(tzinfo=None),
                        exit_only=exit_only,
                    )
                strategy = m.AUTOA(MagicMock(fetch_bars=AsyncMock(return_value=bars)))
                strategy.calculate_atr = lambda _: atr
                runtime = make_test_engine(
                    strategy,
                    m.AshareExecutor(),
                    state,
                    MagicMock(send=AsyncMock()),
                    MagicMock(),
                    MagicMock(),
                    MagicMock(),
                )
                await runtime.process_instrument(
                    "000001", m.MarketContext(NOW, exit_only=exit_only)
                )
                self.assertEqual(
                    state.serialize(),
                    json.loads(json.dumps(old.AUTOA.alert_all)),
                    (is_n, adds, atr, price, exit_only, opened_today),
                )

            for tags, volume, atr, age in itertools.product(
                ((), (m.StrategyTag.BZ,), (m.StrategyTag.BZ, m.StrategyTag.N)),
                (90, 500),
                (0, 1),
                (0, 2, 31),
            ):
                obs = make_observation(
                    "000001", tags=tags, bz_reference_high=11
                ).model_copy(
                    update={"timestamp": (NOW - pd.Timedelta(days=age)).timestamp()}
                )
                state = m.TradingState("AUTOA", "unused")
                state.apply(m.StatePatch(observations=(("000001", obs),)))
                old.AUTOA.alert_all = json.loads(json.dumps(state.serialize()))
                rows = [[i, 10, 11, 9, 10, 100 + i % 5] for i in range(29)] + [
                    [29, 12, 14, 11, 13, volume]
                ]
                history.return_value = pd.DataFrame(
                    rows, columns=["date", "open", "high", "low", "close", "volume"]
                )
                with patch.object(old.AUTOA, "calculate_atr", return_value=atr):
                    await old.AUTOA.on_observations(
                        "000001",
                        ["2026-09-09", "2026-08-13"],
                        old.AUTOA.alert_all["OBSERVATIONS"]["000001"],
                        NOW.replace(tzinfo=None),
                    )
                strategy = m.AUTOA(
                    MagicMock(
                        fetch_bars=AsyncMock(
                            return_value=m.MarketBars.from_frame(history.return_value)
                        )
                    )
                )
                strategy.calculate_atr = lambda _: atr
                runtime = make_test_engine(
                    strategy,
                    m.AshareExecutor(),
                    state,
                    MagicMock(send=AsyncMock()),
                    MagicMock(),
                    MagicMock(),
                    MagicMock(),
                )
                await runtime.process_instrument("000001", m.MarketContext(NOW))
                self.assertEqual(
                    state.serialize(),
                    json.loads(json.dumps(old.AUTOA.alert_all)),
                    (tags, volume, atr, age),
                )


class StructureTest(unittest.TestCase):
    def test_single_engine_and_executor_owners(self):
        source = (
            Path(__file__)
            .with_name("autoTrade_pm_refactored.py")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(source.count("class TradingEngine"), 1)
        self.assertEqual(source.count("class TradeExecutor"), 1)
        self.assertEqual(source.count("class TradingState"), 1)
        self.assertIn("engine.run_market_cycle", source)
        self.assertIn("engine.push_daily_report", source)


if __name__ == "__main__":
    unittest.main()
