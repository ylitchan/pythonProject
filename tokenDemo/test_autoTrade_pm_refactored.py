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


def make_ths_data():
    session = MagicMock()
    http = SimpleNamespace(get=AsyncMock(return_value=session), timeout=1)
    return m.AshareMarketData(http, MagicMock()), session


def ths_response(payload, *, callback=None, status=200):
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


def ths_today(code="000001", date="20260909", time="1000", **updates):
    return {
        f"hs_{code}": {
            "1": date,
            "dt": time,
            "7": "10",
            "8": "12",
            "9": "9",
            "11": "11",
            "13": 123400,
            **updates,
        }
    }


def ths_history():
    return {
        "name": "测试",
        "num": 19,
        "data": ";".join(
            f"{date.strftime('%Y%m%d')},10,12,9,11,10000,0"
            for date in pd.bdate_range("2026-08-13", "2026-09-08")
        ),
    }


class UnifiedSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_today_ohlcv_and_volume_units_come_from_ths(self):
        data, session = make_ths_data()
        session.get.return_value = ths_response(
            ths_today(), callback="quotebridge_today"
        )
        with patch.object(m, "market_time", return_value=NOW):
            bar = await data.daily_bar("000001")
        self.assertEqual(
            bar, {"open": 10, "high": 12, "low": 9, "close": 11, "volume": 1234}
        )
        self.assertIn("10jqka.com.cn", session.get.call_args.args[0])

    async def test_today_rejects_wrong_date_stale_time_and_invalid_numbers(self):
        for payload in (
            ths_today(date="20260908"),
            ths_today(time="0930"),
            ths_today(**{"11": "nan"}),
            ths_today(**{"13": -1}),
        ):
            with self.subTest(payload=payload):
                data, session = make_ths_data()
                session.get.return_value = ths_response(payload, callback="quote")
                with patch.object(m, "market_time", return_value=NOW):
                    self.assertIsNone(await data.daily_bar("000001"))

    async def test_history_uses_same_source_and_does_not_duplicate_today(self):
        data, session = make_ths_data()
        history = ths_history()
        history["data"] += ";20260909,1,2,1,2,100,0"
        session.get.side_effect = [
            ths_response(ths_today(), callback="quote"),
            ths_response(history, callback="line"),
            ths_response(ths_today(**{"11": "10.5"}), callback="quote"),
        ]
        context = m.MarketContext(NOW, "2026-08-13", "2026-09-09")
        with patch.object(m, "market_time", return_value=NOW):
            first = await data.fetch_bars("000001", context)
            second = await data.fetch_bars("000001", context)
        self.assertEqual((len(first), len(second)), (20, 20))
        self.assertEqual(first.volumes[-2:], (100, 1234))
        self.assertEqual(second.price, 10.5)
        self.assertEqual(session.get.call_count, 3)
        self.assertTrue(
            all("10jqka.com.cn" in c.args[0] for c in session.get.call_args_list)
        )

    async def test_calendar_supplies_trading_and_reopen_dates_with_daily_cache(self):
        data, session = make_ths_data()
        data.CALENDAR_WINDOW_DAYS = 3
        session.get.return_value = ths_response(
            {
                "status_code": 0,
                "data": {
                    "code": 0,
                    "trade_day": False,
                    "prev_dates": ["20260928", "20260929", "20260930"],
                    "next_dates": ["20261008", "20261009", "20261012"],
                },
            }
        )
        now = NOW.replace(month=10, day=1)
        with patch.object(
            m, "market_time", side_effect=lambda value=None: value or now
        ):
            self.assertFalse(await data.is_trading_day(now))
            self.assertEqual(
                await data.following_dates(now), ["2026-10-08", "2026-10-09"]
            )
        self.assertEqual(session.get.call_count, 1)

    async def test_limit_pool_pagination_preserves_all_codes(self):
        data, session = make_ths_data()
        data.is_trading_day = AsyncMock(return_value=True)
        data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-08-13"])
        session.get.side_effect = [
            ths_response(
                {
                    "status_code": 0,
                    "data": {
                        "page": {"page": 1, "count": 2, "total": 2},
                        "info": [{"code": "000001", "name": "甲"}],
                    },
                }
            ),
            ths_response(
                {
                    "status_code": 0,
                    "data": {
                        "page": {"page": 2, "count": 2, "total": 2},
                        "info": [{"code": "600185", "name": "乙"}],
                    },
                }
            ),
        ]
        pool, context = await data.limit_up_pool(NOW)
        self.assertEqual(pool, (("000001", "甲"), ("600185", "乙")))
        self.assertEqual(context.start_date, "2026-08-13")

    async def test_unified_source_does_not_import_akshare(self):
        import ast

        tree = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        self.assertNotIn("akshare", imports)

    async def test_pool_rejects_partial_pages_and_preserves_observations(self):
        data, session = make_ths_data()
        data.is_trading_day = AsyncMock(return_value=True)
        data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-08-13"])
        good = {
            "status_code": 0,
            "data": {
                "page": {"page": 1, "count": 2, "total": 2},
                "info": [{"code": "000001", "name": "甲"}],
            },
        }
        bad_pages = [
            {
                "status_code": 0,
                "data": {"page": {"page": 2, "count": 2, "total": 2}, "info": []},
            },
            {
                "status_code": 0,
                "data": {
                    "page": {"page": 2, "count": 2, "total": 2},
                    "info": [{"code": "000001", "name": "甲"}],
                },
            },
            {
                "status_code": 0,
                "data": {
                    "page": {"page": 2, "count": 2, "total": 3},
                    "info": [{"code": "600185", "name": "乙"}],
                },
            },
        ]
        for bad in bad_pages:
            with self.subTest(page=bad):
                session.get.side_effect = [ths_response(good), ths_response(bad)]
                snapshot = m.StateSnapshot({}, {"000001": make_observation("000001")})
                with self.assertRaises(ValueError):
                    await m.AUTOA(data).refresh_universe(NOW, snapshot)
                self.assertEqual(tuple(snapshot.observations), ("000001",))

    async def test_nontrading_day_never_requests_pool(self):
        data, session = make_ths_data()
        data.is_trading_day = AsyncMock(return_value=False)
        self.assertEqual(await data.limit_up_pool(NOW), ((), None))
        session.get.assert_not_called()

    async def test_calendar_failure_keeps_covered_cache_without_inventing_days(self):
        data, session = make_ths_data()
        data.cache.calendar = pd.Series(
            pd.to_datetime(["2026-09-08", "2026-09-09", "2026-09-10"])
        )
        data.cache.calendar_anchor = NOW.date()
        data.cache.calendar_loaded_on = NOW.date() - pd.Timedelta(days=1)
        session.get.return_value = ths_response({"status_code": 1, "data": {}})
        with patch.object(
            m, "market_time", side_effect=lambda value=None: value or NOW
        ):
            self.assertEqual(len(await data.trading_calendar(NOW)), 3)
            self.assertIsNone(await data.trading_calendar(NOW.replace(year=2027)))

    async def test_calendar_rejects_wrong_direction_and_unsorted_dates(self):
        for previous, following in (
            (["20260910"], ["20260911"]),
            (["20260908", "20260907"], ["20260910"]),
            (["20260908"], ["20260908"]),
        ):
            data, session = make_ths_data()
            session.get.return_value = ths_response(
                {
                    "status_code": 0,
                    "data": {
                        "code": 0,
                        "trade_day": True,
                        "prev_dates": previous,
                        "next_dates": following,
                    },
                }
            )
            with patch.object(
                m, "market_time", side_effect=lambda value=None: value or NOW
            ):
                self.assertIsNone(await data.trading_calendar(NOW))

    async def test_cooldown_fetches_calendar_for_older_close_date(self):
        data, session = make_ths_data()
        data.CALENDAR_WINDOW_DAYS = 1
        supplied = pd.Series(pd.to_datetime(["2026-09-08", "2026-09-09", "2026-09-10"]))
        session.get.return_value = ths_response(
            {
                "status_code": 0,
                "data": {
                    "code": 0,
                    "trade_day": True,
                    "prev_dates": ["20260430"],
                    "next_dates": ["20260507", "20260508", "20260511"],
                },
            }
        )
        closed = NOW.replace(month=5, day=6)
        with patch.object(
            m, "market_time", side_effect=lambda value=None: value or NOW
        ):
            self.assertEqual(
                await data.reopen_timestamp(closed, calendar=supplied),
                closed.replace(day=8, hour=0).timestamp(),
            )
        self.assertEqual(session.get.call_args.kwargs["params"]["date"], "20260506")

    async def test_lunch_and_postclose_allow_last_session_quote_but_reject_stale(self):
        for now, quote_time, valid in (
            (NOW.replace(hour=12), "1130", True),
            (NOW.replace(hour=15, minute=6), "1500", True),
            (NOW.replace(hour=15, minute=6), "1450", False),
        ):
            data, session = make_ths_data()
            session.get.return_value = ths_response(
                ths_today(time=quote_time), callback="quote"
            )
            with patch.object(m, "market_time", return_value=now):
                self.assertEqual((await data.daily_bar("000001")) is not None, valid)

    async def test_history_invalid_rows_do_not_enter_cache(self):
        for encoded in (
            "20260908,10,12,9,nan,100",
            "20260908,10,12,9,11,100;20260908,10,12,9,11,100",
            "20260908,10,12,9,11,100;20260907,10,12,9,11,100",
        ):
            data, session = make_ths_data()
            session.get.side_effect = [
                ths_response(ths_today(), callback="quote"),
                ths_response({"data": encoded}, callback="line"),
            ]
            with patch.object(m, "market_time", return_value=NOW):
                self.assertFalse(
                    await data.fetch_bars(
                        "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
                    )
                )
            self.assertFalse(data.cache.history)

    async def test_http_retry_is_bounded_and_cancellation_propagates(self):
        data, session = make_ths_data()
        session.get.return_value = ths_response({}, status=502)
        with self.assertRaises(m.aiohttp.ClientResponseError):
            await data._request("https://d.10jqka.com.cn/test")
        self.assertEqual(session.get.call_count, 2)
        session.get.reset_mock()
        session.get.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await data._request("https://d.10jqka.com.cn/test")
        session.get.assert_called_once()

    async def test_incomplete_calendar_cannot_replace_valid_snapshot(self):
        previous = (
            pd.bdate_range(end="2026-09-08", periods=60).strftime("%Y%m%d").tolist()
        )
        following = (
            pd.bdate_range(start="2026-09-10", periods=60).strftime("%Y%m%d").tolist()
        )
        for before, after in (
            (previous[:-1], following),
            (previous, following[:-1]),
            (previous, []),
        ):
            data, session = make_ths_data()
            session.get.return_value = ths_response(
                {
                    "status_code": 0,
                    "data": {
                        "code": 0,
                        "trade_day": True,
                        "prev_dates": before,
                        "next_dates": after,
                    },
                }
            )
            with patch.object(
                m, "market_time", side_effect=lambda value=None: value or NOW
            ):
                self.assertIsNone(await data.trading_calendar(NOW))
            self.assertIsNone(data.cache.calendar)

    async def test_valid_nonobject_json_is_schema_failure_without_retry(self):
        for callback in (None, "callback"):
            with self.subTest(callback=callback):
                data, session = make_ths_data()
                session.get.return_value = ths_response([], callback=callback)
                with self.assertRaises(ValueError):
                    await data._request("https://d.10jqka.com.cn/test")
                session.get.assert_called_once()


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
        engine = m.TradingEngine(
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
        data, session = make_ths_data()
        data.is_trading_day = AsyncMock(return_value=True)
        data.recent_dates = AsyncMock(return_value=["2026-09-09", "2026-09-08"])
        session.get.return_value = ths_response(
            {
                "status_code": 0,
                "data": {
                    "page": {"page": 1, "count": 1, "total": 1},
                    "info": [{"code": "000001", "name": "测试"}],
                },
            }
        )
        pool, context = await data.limit_up_pool(NOW.replace(hour=15, minute=6))
        self.assertEqual(pool, (("000001", "测试"),))
        self.assertEqual(context.end_date, "2026-09-09")
        session.get.return_value = ths_response(
            {
                "status_code": 0,
                "data": {
                    "page": {"page": 1, "count": 0, "total": 0},
                    "info": [],
                },
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
        return m.TradingEngine(
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
        engine = m.TradingEngine(
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
        return m.TradingEngine(
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
        data, session = make_ths_data()
        session.get.side_effect = [
            ths_response(ths_today(), callback="quote"),
            ths_response({}, status=502),
            ths_response(ths_history(), callback="line"),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
            )
        self.assertEqual(len(bars), 20)
        self.assertEqual(bars.volumes[-2:], (100, 1234))
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(
            session.get.call_args_list[1].args[0], session.get.call_args_list[2].args[0]
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
        data, session = make_ths_data()
        session.get.side_effect = [
            ths_response(ths_today(), callback="quote"),
            ths_response(ths_history(), callback="line"),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001",
                m.MarketContext(NOW, "2026-08-13", "2026-09-09", exit_only=True),
            )
        self.assertEqual(len(bars), 20)
        session.get.side_effect = None
        session.get.return_value = ths_response(
            ths_today(date="20260908"), callback="quote"
        )
        with patch.object(m, "market_time", return_value=NOW):
            self.assertFalse(
                await data.fetch_bars(
                    "000001",
                    m.MarketContext(NOW, "2026-08-13", "2026-09-09", exit_only=True),
                )
            )

    async def test_jsonp_is_parsed_as_data_and_never_evaluated(self):
        data, session = make_ths_data()
        response = MagicMock(status=200)
        response.text = AsyncMock(
            return_value='callback({"ok": true}); dangerous_call();'
        )
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=response)
        manager.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = manager
        with self.assertRaises(ValueError):
            await data._request("https://d.10jqka.com.cn/test")

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
        data, session = make_ths_data()
        session.get.side_effect = [
            ths_response(ths_today(), callback="quote"),
            ths_response({"data": "20260908,10"}, callback="line"),
        ]
        with patch.object(m, "market_time", return_value=NOW):
            bars = await data.fetch_bars(
                "000001", m.MarketContext(NOW, "2026-08-13", "2026-09-09")
            )
        self.assertFalse(bars)
        self.assertEqual(data.cache.history, {})
        self.assertTrue(
            all("10jqka.com.cn" in call.args[0] for call in session.get.call_args_list)
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
        expected = min(
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
            recovered.guard.open_interest, min(108, stats["mean"] + stats["std"] * 10)
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
                runtime = m.TradingEngine(
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
                runtime = m.TradingEngine(
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
