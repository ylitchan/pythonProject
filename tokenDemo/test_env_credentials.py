import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tokenDemo.autoTrade_pm import AUTOBN


class AutoBNCredentialsTest(unittest.TestCase):
    def _from_cfg(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            alert_file = Path(directory) / "alert_all.json"
            alert_file.write_text(json.dumps({}), encoding="utf-8")
            with (
                patch("tokenDemo.autoTrade_pm.ConfigurationRestAPI") as config,
                patch("tokenDemo.autoTrade_pm.DerivativesTradingUsdsFutures") as market,
                patch(
                    "tokenDemo.autoTrade_pm.DerivativesTradingPortfolioMargin"
                ) as portfolio,
                patch("tokenDemo.autoTrade_pm.atexit.register"),
            ):
                market.return_value.rest_api._session = MagicMock()
                obj = AUTOBN.from_cfg(
                    alert_all_file=str(alert_file), qy_key="test-qy-key", **kwargs
                )
                return obj, config.call_args_list, portfolio.call_args

    def test_reads_binance_credentials_from_environment(self):
        with patch.dict(
            os.environ,
            {"BINANCE_API_KEY": "env-key", "BINANCE_API_SECRET": "env-secret"},
            clear=True,
        ):
            _, config_calls, _ = self._from_cfg()

        self.assertEqual(config_calls[0].kwargs["api_key"], "env-key")
        self.assertEqual(config_calls[0].kwargs["api_secret"], "env-secret")

    def test_explicit_credentials_override_environment(self):
        with patch.dict(
            os.environ,
            {"BINANCE_API_KEY": "env-key", "BINANCE_API_SECRET": "env-secret"},
            clear=True,
        ):
            _, config_calls, _ = self._from_cfg(
                api_key="explicit-key", api_secret="explicit-secret"
            )

        self.assertEqual(config_calls[0].kwargs["api_key"], "explicit-key")
        self.assertEqual(config_calls[0].kwargs["api_secret"], "explicit-secret")

    def test_missing_credentials_fails_without_reading_bn_json(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("builtins.open", side_effect=AssertionError("不应读取 bn.json")),
        ):
            with self.assertRaisesRegex(ValueError, "BINANCE_API_KEY"):
                AUTOBN.from_cfg(qy_key="test-qy-key")


if __name__ == "__main__":
    unittest.main()
