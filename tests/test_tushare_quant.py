import importlib.util
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

        self.assertEqual(calls["token"], "test-token")
        self.assertEqual(calls["api"]._DataApi__http_url, "https://tushare-proxy.example/api")
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

        self.assertEqual(calls["token"], "file-token")
        self.assertEqual(calls["api"]._DataApi__http_url, "https://file-proxy.example/api")

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
        self.assertEqual(calls["token"], "file-token")
        self.assertEqual(rows[0]["trade_date"], "20240101")

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


class FakeApi:
    pass


def make_fake_tushare_module():
    calls = {}
    fake_tushare = types.ModuleType("tushare")

    def set_token(token):
        calls["token"] = token

    def pro_api(token):
        calls["pro_api_token"] = token
        calls["api"] = FakeApi()
        return calls["api"]

    def pro_bar(*, api=None, ts_code="", adj=None, start_date="", end_date=""):
        calls["pro_bar"] = {
            "api": api,
            "ts_code": ts_code,
            "adj": adj,
            "start_date": start_date,
            "end_date": end_date,
        }
        return FakeFrame()

    fake_tushare.set_token = set_token
    fake_tushare.pro_api = pro_api
    fake_tushare.pro_bar = pro_bar
    return fake_tushare, calls


if __name__ == "__main__":
    unittest.main()
