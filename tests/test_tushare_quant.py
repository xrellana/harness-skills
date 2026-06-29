import importlib.util
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tushare-quant" / "scripts"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tq_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        return load_module("tq")
    finally:
        sys.path.remove(str(SCRIPTS))


def sample_rows():
    closes = [10, 10.2, 10.4, 10.1, 10.5, 10.9, 11.2, 11.0, 11.4, 11.8]
    return [
        {
            "trade_date": f"202401{idx + 1:02d}",
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.3,
            "close": close,
            "vol": 1000 + idx * 100,
        }
        for idx, close in enumerate(closes)
    ]


class TushareQuantTests(unittest.TestCase):
    def test_macd_and_kdj_add_expected_fields(self):
        indicators = load_module("indicators")

        enriched = indicators.add_indicators(sample_rows())

        self.assertEqual(len(enriched), 10)
        last = enriched[-1]
        for field in ["ma5", "macd_diff", "macd_dea", "macd_hist", "kdj_k", "kdj_d", "kdj_j"]:
            self.assertIn(field, last)
            self.assertIsInstance(last[field], float)

    def test_backtest_reports_return_and_drawdown(self):
        backtest = load_module("backtest")
        rows = sample_rows()
        signals = [0, 1, 1, 1, 1, 0, 0, 1, 1, 0]

        result = backtest.run_signal_backtest(rows, signals, initial_cash=100000, fee_rate=0.001)

        self.assertEqual(result["trade_count"], 4)
        self.assertGreater(result["final_equity"], 100000)
        self.assertGreater(result["total_return_pct"], 0)
        self.assertLessEqual(result["max_drawdown_pct"], 0)
        self.assertEqual(len(result["equity_curve"]), len(rows))

    def test_fetch_daily_bars_uses_custom_api_url(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module()
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            rows = tushare_client.fetch_daily_bars(
                "600519",
                "20240101",
                "20240102",
                token_env="TUSHARE_TEST_TOKEN",
                api_url="https://tushare-proxy.example/api",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        self.assertNotIn("token", calls)
        self.assertEqual(calls["pro_api_token"], "test-token")
        self.assertEqual(calls["api"]._DataApi__http_url, "https://tushare-proxy.example/api")
        self.assertIs(calls["pro_bar"]["api"], calls["api"])
        self.assertEqual(rows[0]["trade_date"], "20240101")

    def test_fetch_daily_bars_passes_token_through_api_without_calling_set_token(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module(set_token_raises=True)
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            rows = tushare_client.fetch_daily_bars(
                "600519",
                "20240101",
                "20240102",
                token_env="TUSHARE_TEST_TOKEN",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        self.assertEqual(calls["pro_api_token"], "test-token")
        self.assertIs(calls["pro_bar"]["api"], calls["api"])
        self.assertEqual(rows[0]["trade_date"], "20240101")

    def test_fetch_daily_bars_uses_custom_api_url_from_environment(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module()
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        os.environ["TUSHARE_API_URL"] = "https://env-proxy.example/api"
        try:
            tushare_client.fetch_daily_bars(
                "600519",
                "20240101",
                "20240102",
                token_env="TUSHARE_TEST_TOKEN",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)
            os.environ.pop("TUSHARE_API_URL", None)

        self.assertEqual(calls["api"]._DataApi__http_url, "https://env-proxy.example/api")

    def test_load_env_file_reads_values_without_overwriting_existing_environment(self):
        tushare_client = load_module("tushare_client")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        "TUSHARE_TEST_TOKEN=file-token",
                        'TUSHARE_API_URL="https://file-proxy.example/api"',
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["TUSHARE_TEST_TOKEN"] = "shell-token"
            os.environ.pop("TUSHARE_API_URL", None)
            try:
                loaded = tushare_client.load_env_file(env_path)
                token_value = os.environ.get("TUSHARE_TEST_TOKEN")
                api_url_value = os.environ.get("TUSHARE_API_URL")
            finally:
                os.environ.pop("TUSHARE_TEST_TOKEN", None)
                os.environ.pop("TUSHARE_API_URL", None)

        self.assertEqual(loaded["TUSHARE_TEST_TOKEN"], "file-token")
        self.assertEqual(token_value, "shell-token")
        self.assertEqual(loaded["TUSHARE_API_URL"], "https://file-proxy.example/api")
        self.assertEqual(api_url_value, "https://file-proxy.example/api")

    def test_fetch_daily_bars_reads_token_and_url_from_env_file(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module()
        sys.modules["tushare"] = fake_tushare
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "TUSHARE_TEST_TOKEN=file-token\nTUSHARE_API_URL=https://file-proxy.example/api\n",
                encoding="utf-8",
            )
            tushare_client.DEFAULT_ENV_FILE = env_path
            os.environ.pop("TUSHARE_TEST_TOKEN", None)
            os.environ.pop("TUSHARE_API_URL", None)
            try:
                tushare_client.fetch_daily_bars(
                    "600519",
                    "20240101",
                    "20240102",
                    token_env="TUSHARE_TEST_TOKEN",
                )
            finally:
                sys.modules.pop("tushare", None)
                os.environ.pop("TUSHARE_TEST_TOKEN", None)
                os.environ.pop("TUSHARE_API_URL", None)

        self.assertNotIn("token", calls)
        self.assertEqual(calls["pro_api_token"], "file-token")
        self.assertEqual(calls["api"]._DataApi__http_url, "https://file-proxy.example/api")

    def test_fetch_daily_bars_falls_back_to_unadjusted_when_qfq_adj_factor_is_unavailable(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module(fail_adjusted=True)
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            result = tushare_client.fetch_daily_bars_result(
                "600519",
                "20240101",
                "20240102",
                token_env="TUSHARE_TEST_TOKEN",
                api_url="https://tushare-proxy.example/api",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        self.assertEqual([call["adj"] for call in calls["pro_bar_calls"]], ["qfq"])
        self.assertEqual(calls["daily"]["ts_code"], "600519.SH")
        self.assertEqual(result.adjustment, "unadjusted-fallback")
        self.assertIn("adj_factor", result.warning)
        self.assertEqual(result.rows[0]["trade_date"], "20240101")

    def test_fetch_daily_bars_raises_clear_error_when_no_rows_are_returned(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, _calls = make_fake_tushare_module(frame=EmptyFrame())
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            with self.assertRaisesRegex(tushare_client.TushareDataError, "No Tushare bars returned"):
                tushare_client.fetch_daily_bars(
                    "600519",
                    "20240101",
                    "20240102",
                    token_env="TUSHARE_TEST_TOKEN",
                    api_url="https://tushare-proxy.example/api",
                )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

    def test_fetch_daily_bars_suppresses_noisy_sdk_prints_and_keeps_error_details(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, _calls = make_fake_tushare_module(print_and_raise="proxy socket blocked")
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                with self.assertRaisesRegex(tushare_client.TushareDataError, "proxy socket blocked"):
                    tushare_client.fetch_daily_bars(
                        "600519",
                        "20240101",
                        "20240102",
                        token_env="TUSHARE_TEST_TOKEN",
                        api_url="https://tushare-proxy.example/api",
                    )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        self.assertEqual(stdout.getvalue(), "")

    def test_token_error_from_unadjusted_fallback_is_not_masked_as_adj_factor_error(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, _calls = make_fake_tushare_module(
            fail_adjusted=True,
            daily_error="Tushare API daily failed: Token无效或已过期，请联系客服续费",
        )
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            with self.assertRaisesRegex(tushare_client.TushareDataError, "^Tushare API daily failed"):
                tushare_client.fetch_daily_bars(
                    "600519",
                    "20240101",
                    "20240102",
                    token_env="TUSHARE_TEST_TOKEN",
                    api_url="https://tushare-proxy.example/api",
                )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

    def test_data_api_payload_error_includes_proxy_message(self):
        tushare_client = load_module("tushare_client")

        with self.assertRaisesRegex(tushare_client.TushareDataError, "Token无效或已过期"):
            tushare_client._frame_from_data_api_payload(
                "daily",
                401,
                {"code": -1, "msg": "Token无效或已过期，请联系客服续费"},
                "",
            )

    def test_auto_source_uses_env_file_before_falling_back_to_sample_data(self):
        tq = load_tq_module()
        fake_tushare, calls = make_fake_tushare_module()
        sys.modules["tushare"] = fake_tushare
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "TUSHARE_TOKEN=file-token\nTUSHARE_API_URL=https://file-proxy.example/api\n",
                encoding="utf-8",
            )
            tq.tushare_client.DEFAULT_ENV_FILE = env_path
            os.environ.pop("TUSHARE_TOKEN", None)
            os.environ.pop("TUSHARE_API_URL", None)
            try:
                rows, source = tq.load_rows("600519", "20240101", "20240102", "auto")
            finally:
                sys.modules.pop("tushare", None)
                os.environ.pop("TUSHARE_TOKEN", None)
                os.environ.pop("TUSHARE_API_URL", None)
                sys.modules.pop("tushare_client", None)

        self.assertEqual(source, "tushare-custom-url")
        self.assertNotIn("token", calls)
        self.assertEqual(calls["pro_api_token"], "file-token")
        self.assertEqual(rows[0]["trade_date"], "20240101")

    def test_load_rows_marks_unadjusted_fallback_source(self):
        tq = load_tq_module()
        fake_tushare, _calls = make_fake_tushare_module(fail_adjusted=True)
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TOKEN"] = "test-token"
        try:
            rows, source = tq.load_rows(
                "600519",
                "20240101",
                "20240102",
                "tushare",
                api_url="https://tushare-proxy.example/api",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TOKEN", None)
            sys.modules.pop("tushare_client", None)

        self.assertEqual(rows[0]["trade_date"], "20240101")
        self.assertIn("unadjusted fallback", source)

    def test_skill_warns_windows_users_to_read_chinese_files_as_utf8(self):
        skill_text = (ROOT / "tushare-quant" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Get-Content -Encoding UTF8", skill_text)
        self.assertIn("PYTHONIOENCODING=utf-8", skill_text)

    def test_skill_documents_local_env_file_configuration(self):
        skill_text = (ROOT / "tushare-quant" / "SKILL.md").read_text(encoding="utf-8")
        env_example = ROOT / "tushare-quant" / ".env.example"

        self.assertTrue(env_example.exists())
        self.assertIn("tushare-quant/.env", skill_text)
        self.assertIn("External environment variables take precedence", skill_text)


class FakeFrame:
    def to_dict(self, orient):
        if orient != "records":
            raise ValueError("unexpected orient")
        return [
            {"trade_date": "20240102", "open": 10, "high": 11, "low": 9, "close": 10.5, "vol": 100},
            {"trade_date": "20240101", "open": 9, "high": 10, "low": 8, "close": 9.5, "vol": 90},
        ]


class EmptyFrame:
    def to_dict(self, orient):
        if orient != "records":
            raise ValueError("unexpected orient")
        return []


class FakeApi:
    pass


def make_fake_tushare_module(frame=None, fail_adjusted=False, set_token_raises=False, print_and_raise=None, daily_error=None):
    calls = {"pro_bar_calls": []}
    fake_tushare = types.ModuleType("tushare")
    response_frame = frame or FakeFrame()

    def set_token(token):
        if set_token_raises:
            raise PermissionError("should not write tk.csv")
        calls["token"] = token

    def pro_api(token):
        calls["pro_api_token"] = token
        calls["api"] = FakeApi()

        def daily(**kwargs):
            calls["daily"] = kwargs
            if daily_error:
                raise RuntimeError(daily_error)
            return response_frame

        calls["api"].daily = daily
        return calls["api"]

    def pro_bar(*, api=None, ts_code="", adj=None, start_date="", end_date="", retry_count=3):
        call = {
            "api": api,
            "ts_code": ts_code,
            "adj": adj,
            "start_date": start_date,
            "end_date": end_date,
            "retry_count": retry_count,
        }
        calls["pro_bar"] = call
        calls["pro_bar_calls"].append(call)
        if print_and_raise:
            print(print_and_raise)
            raise RuntimeError("ERROR.")
        if fail_adjusted and adj:
            raise KeyError("None of [Index(['trade_date', 'adj_factor'], dtype='str')] are in the [columns]")
        return response_frame

    fake_tushare.set_token = set_token
    fake_tushare.pro_api = pro_api
    fake_tushare.pro_bar = pro_bar
    return fake_tushare, calls


if __name__ == "__main__":
    unittest.main()
