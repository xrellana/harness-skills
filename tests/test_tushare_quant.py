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


def sample_analysis_bundle():
    return {
        "daily_basic": [
            {
                "trade_date": "20240110",
                "turnover_rate": 4.2,
                "volume_ratio": 1.35,
                "pe_ttm": 18.6,
                "pb": 2.1,
                "total_mv": 1234567,
                "circ_mv": 987654,
            }
        ],
        "moneyflow": [
            {
                "trade_date": "20240110",
                "net_mf_amount": 3456.7,
                "buy_lg_amount": 2100,
                "sell_lg_amount": 1300,
                "buy_elg_amount": 1800,
                "sell_elg_amount": 900,
            }
        ],
        "benchmark": {
            "code": "000300.SH",
            "rows": [
                {"trade_date": "20240101", "close": 3200.0},
                {"trade_date": "20240110", "close": 3360.0},
            ],
        },
        "fina_indicator": [
            {
                "ann_date": "20240420",
                "end_date": "20240331",
                "roe": 14.2,
                "or_yoy": 21.5,
                "netprofit_yoy": 18.8,
                "gross_margin": 35.1,
            }
        ],
        "adj_factor": [
            {"trade_date": "20240101", "adj_factor": 1.0},
            {"trade_date": "20240110", "adj_factor": 1.08},
        ],
        "stk_limit": [
            {"trade_date": "20240105", "up_limit": 11.5, "down_limit": 9.4},
        ],
        "suspend_d": [
            {"trade_date": "20240108", "suspend_type": "S", "suspend_timing": None},
        ],
        "warnings": ["moneyflow: permission denied"],
    }


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

    def test_indicator_report_includes_multidimensional_analysis_blocks(self):
        report = load_module("report")
        indicators = load_module("indicators")
        rows = indicators.add_indicators(sample_rows())

        output = report.format_indicator_report(
            "600519.SH",
            rows,
            "tushare",
            analysis=sample_analysis_bundle(),
        )

        for text in [
            "区间最大回撤",
            "量能与换手",
            "换手率",
            "量比",
            "估值锚点",
            "PE(TTM)",
            "PB",
            "资金流向",
            "主力资金净流入",
            "基准对比",
            "000300.SH",
            "财务质量",
            "ROE",
            "营收同比",
            "复权与交易约束",
            "复权因子",
            "涨停触及",
            "停牌记录",
            "数据缺口",
            "permission denied",
        ]:
            self.assertIn(text, output)

    def test_fetch_analysis_bundle_queries_supplemental_tushare_endpoints(self):
        tushare_client = load_module("tushare_client")
        fake_tushare, calls = make_fake_tushare_module(
            endpoint_frames={
                "daily_basic": RecordsFrame([{"trade_date": "20240102", "turnover_rate": 3.1}]),
                "moneyflow": RecordsFrame([{"trade_date": "20240102", "net_mf_amount": 123.4}]),
                "index_daily": RecordsFrame([{"trade_date": "20240102", "close": 3360.0}]),
                "fina_indicator": RecordsFrame([{"end_date": "20240331", "ann_date": "20240420", "roe": 12.3}]),
                "adj_factor": RecordsFrame([{"trade_date": "20240102", "adj_factor": 1.05}]),
                "stk_limit": RecordsFrame([{"trade_date": "20240102", "up_limit": 11.0, "down_limit": 9.0}]),
                "suspend_d": RecordsFrame([{"trade_date": "20240102", "suspend_type": "S"}]),
            }
        )
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            bundle = tushare_client.fetch_analysis_bundle(
                "600519",
                "20240101",
                "20240110",
                benchmark="000300.SH",
                token_env="TUSHARE_TEST_TOKEN",
                api_url="https://tushare-proxy.example/api",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        for endpoint in ["daily_basic", "moneyflow", "fina_indicator", "adj_factor", "stk_limit"]:
            self.assertEqual(calls[endpoint]["ts_code"], "600519.SH")
            self.assertEqual(calls[endpoint]["start_date"], "20240101")
            self.assertEqual(calls[endpoint]["end_date"], "20240110")
        self.assertEqual(calls["index_daily"]["ts_code"], "000300.SH")
        self.assertEqual(calls["suspend_d"]["suspend_type"], "S")
        self.assertEqual(bundle["daily_basic"][0]["turnover_rate"], 3.1)
        self.assertEqual(bundle["benchmark"]["code"], "000300.SH")
        self.assertEqual(bundle["benchmark"]["rows"][0]["close"], 3360.0)
        self.assertEqual(bundle["warnings"], [])

    def test_fetch_analysis_bundle_falls_back_to_trade_dates_for_flaky_limit_and_suspend_ranges(self):
        tushare_client = load_module("tushare_client")

        def fail_range_queries(kwargs):
            if "start_date" in kwargs:
                return "HTTP 502 Bad Gateway"
            return None

        def limit_frame(kwargs):
            return RecordsFrame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": kwargs["trade_date"],
                        "up_limit": 11.0,
                        "down_limit": 9.0,
                    }
                ]
            )

        def suspend_frame(kwargs):
            return RecordsFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": kwargs["trade_date"], "suspend_type": "S"},
                    {"ts_code": kwargs["ts_code"], "trade_date": kwargs["trade_date"], "suspend_type": "S"},
                ]
            )

        fake_tushare, calls = make_fake_tushare_module(
            endpoint_frames={
                "stk_limit": limit_frame,
                "suspend_d": suspend_frame,
            },
            endpoint_errors={
                "stk_limit": fail_range_queries,
                "suspend_d": fail_range_queries,
            },
        )
        sys.modules["tushare"] = fake_tushare
        os.environ["TUSHARE_TEST_TOKEN"] = "test-token"
        try:
            bundle = tushare_client.fetch_analysis_bundle(
                "300476",
                "20240101",
                "20240110",
                benchmark="000300.SH",
                trade_dates=["20240102", "20240103"],
                token_env="TUSHARE_TEST_TOKEN",
                api_url="https://tushare-proxy.example/api",
            )
        finally:
            sys.modules.pop("tushare", None)
            os.environ.pop("TUSHARE_TEST_TOKEN", None)

        self.assertEqual([row["trade_date"] for row in bundle["stk_limit"]], ["20240102", "20240103"])
        self.assertEqual([row["trade_date"] for row in bundle["suspend_d"]], ["20240102", "20240103"])
        self.assertTrue(all(row["ts_code"] == "300476.SZ" for row in bundle["suspend_d"]))
        self.assertEqual([call.get("trade_date") for call in calls["stk_limit_calls"][1:]], ["20240102", "20240103"])
        self.assertEqual([call.get("trade_date") for call in calls["suspend_d_calls"][1:]], ["20240102", "20240103"])
        self.assertTrue(any("used trade_date fallback" in warning for warning in bundle["warnings"]))

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

    def test_fetch_daily_bars_uses_custom_api_url_from_skill_env_file(self):
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
            os.environ["TUSHARE_TEST_TOKEN"] = "shell-token"
            os.environ["TUSHARE_API_URL"] = "https://shell-proxy.example/api"
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

        self.assertEqual(calls["pro_api_token"], "file-token")
        self.assertEqual(calls["api"]._DataApi__http_url, "https://file-proxy.example/api")

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

    def test_load_skill_env_uses_env_file_as_harness_source(self):
        tushare_client = load_module("tushare_client")
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "TUSHARE_TEST_TOKEN=file-token\nTUSHARE_API_URL=https://file-proxy.example/api\n",
                encoding="utf-8",
            )
            tushare_client.DEFAULT_ENV_FILE = env_path
            os.environ["TUSHARE_TEST_TOKEN"] = "shell-token"
            os.environ["TUSHARE_API_URL"] = "https://shell-proxy.example/api"
            try:
                loaded = tushare_client.load_skill_env()
                token_value = os.environ.get("TUSHARE_TEST_TOKEN")
                api_url_value = os.environ.get("TUSHARE_API_URL")
            finally:
                os.environ.pop("TUSHARE_TEST_TOKEN", None)
                os.environ.pop("TUSHARE_API_URL", None)

        self.assertEqual(loaded["TUSHARE_TEST_TOKEN"], "file-token")
        self.assertEqual(token_value, "file-token")
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

    def test_query_data_api_retries_transient_gateway_errors(self):
        tushare_client = load_module("tushare_client")
        requests_module = types.ModuleType("requests")
        responses = [
            FakeResponse(502, "<html>Bad Gateway</html>", json_error=True),
            FakeResponse(
                200,
                "",
                payload={
                    "code": 0,
                    "msg": "",
                    "data": {
                        "fields": ["trade_date", "value"],
                        "items": [["20240102", 1.0]],
                    },
                },
            ),
        ]
        calls = []

        def post(url, json, timeout):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return responses.pop(0)

        requests_module.post = post
        original_requests = sys.modules.get("requests")
        sys.modules["requests"] = requests_module
        try:
            frame = tushare_client._query_data_api(
                FakeApi(),
                "test-token",
                "adj_factor",
                {"ts_code": "300476.SZ"},
                "https://tushare-proxy.example/api",
            )
        finally:
            if original_requests is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = original_requests

        self.assertEqual(len(calls), 2)
        self.assertEqual(frame.to_dict("records")[0]["trade_date"], "20240102")

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
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "TUSHARE_TOKEN=test-token\nTUSHARE_API_URL=https://tushare-proxy.example/api\n",
                encoding="utf-8",
            )
            tq.tushare_client.DEFAULT_ENV_FILE = env_path
            os.environ.pop("TUSHARE_TOKEN", None)
            os.environ.pop("TUSHARE_API_URL", None)
            try:
                rows, source = tq.load_rows(
                    "600519",
                    "20240101",
                    "20240102",
                    "tushare",
                )
            finally:
                sys.modules.pop("tushare", None)
                os.environ.pop("TUSHARE_TOKEN", None)
                os.environ.pop("TUSHARE_API_URL", None)
                sys.modules.pop("tushare_client", None)

        self.assertEqual(rows[0]["trade_date"], "20240101")
        self.assertIn("unadjusted fallback", source)

    def test_tq_cli_does_not_expose_api_url_override(self):
        tq = load_tq_module()
        parser = tq.build_parser()
        help_text = parser.format_help()

        self.assertNotIn("--api-url", help_text)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["analyze", "--api-url", "https://proxy.example/api"])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertIn("unrecognized arguments: --api-url", stderr.getvalue())

    def test_tq_cli_configures_stdio_utf8_for_chinese_output(self):
        tq = load_tq_module()

        class FakeStream:
            encoding = "cp1252"
            errors = "strict"

            def __init__(self):
                self.reconfigure_calls = []

            def reconfigure(self, **kwargs):
                self.reconfigure_calls.append(kwargs)
                self.encoding = kwargs.get("encoding", self.encoding)
                self.errors = kwargs.get("errors", self.errors)

        stdout = FakeStream()
        stderr = FakeStream()

        tq.configure_utf8_stdio(stdout=stdout, stderr=stderr)

        self.assertEqual(stdout.encoding, "utf-8")
        self.assertEqual(stdout.errors, "replace")
        self.assertEqual(stderr.encoding, "utf-8")
        self.assertEqual(stderr.errors, "replace")
        self.assertEqual(stdout.reconfigure_calls, [{"encoding": "utf-8", "errors": "replace"}])
        self.assertEqual(stderr.reconfigure_calls, [{"encoding": "utf-8", "errors": "replace"}])

    def test_skill_warns_windows_users_to_read_chinese_files_as_utf8(self):
        script_guide = ROOT / "tushare-quant" / "references" / "script-guide.md"
        guide_text = script_guide.read_text(encoding="utf-8")

        self.assertIn("Get-Content -Encoding UTF8", guide_text)
        self.assertIn("PYTHONIOENCODING=utf-8", guide_text)

    def test_skill_documents_local_env_file_configuration(self):
        script_guide = ROOT / "tushare-quant" / "references" / "script-guide.md"
        guide_text = script_guide.read_text(encoding="utf-8")
        env_example = ROOT / "tushare-quant" / ".env.example"

        self.assertTrue(env_example.exists())
        self.assertIn("tushare-quant/.env", guide_text)
        self.assertIn("Harness reads `TUSHARE_TOKEN` and `TUSHARE_API_URL` only from `tushare-quant/.env`", guide_text)
        self.assertNotIn("External environment variables take precedence", guide_text)
        self.assertNotIn("export it in the shell", guide_text)
        self.assertNotIn("--api-url", guide_text)

    def test_skill_documents_local_virtualenv_python_usage(self):
        skill_text = (ROOT / "tushare-quant" / "SKILL.md").read_text(encoding="utf-8")
        script_guide = ROOT / "tushare-quant" / "references" / "script-guide.md"
        guide_text = script_guide.read_text(encoding="utf-8")

        self.assertIn("references/script-guide.md", skill_text)
        self.assertNotIn("-m pip install -r", skill_text)
        self.assertNotIn("tq.py analyze --symbol", skill_text)
        self.assertIn("tushare-quant/.venv", guide_text)
        self.assertIn(r"tushare-quant\.venv\Scripts\python.exe", guide_text)
        self.assertIn("tushare-quant/.venv/bin/python", guide_text)
        self.assertNotRegex(skill_text, r"(?m)^python tushare-quant/scripts/tq\.py analyze")

    def test_requirements_declares_live_data_dependencies(self):
        requirements_path = ROOT / "tushare-quant" / "requirements.txt"

        self.assertTrue(requirements_path.exists())
        requirements = {
            line.strip()
            for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

        for dependency in ["tushare", "pandas", "requests"]:
            self.assertIn(dependency, requirements)

    def test_skill_documents_fetch_daily_bars_import(self):
        guide_text = (ROOT / "tushare-quant" / "references" / "script-guide.md").read_text(encoding="utf-8")

        self.assertIn("from scripts.tushare_client import fetch_daily_bars", guide_text)
        self.assertNotIn("get_client", guide_text)

    def test_skill_routes_harness_to_script_guide_before_running_scripts(self):
        skill_text = (ROOT / "tushare-quant" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Read `references/script-guide.md` before running bundled scripts", skill_text)
        self.assertLess(skill_text.index("references/script-guide.md"), skill_text.index("## Workflow"))

    def test_script_guide_documents_script_purposes_and_required_inputs(self):
        guide_text = (ROOT / "tushare-quant" / "references" / "script-guide.md").read_text(encoding="utf-8")

        for text in [
            "`scripts/tq.py`",
            "`scripts/tushare_client.py`",
            "`scripts/indicators.py`",
            "`scripts/backtest.py`",
            "`scripts/report.py`",
            "Required inputs",
            "`--symbol`",
            "`--start`",
            "`--end`",
            "`--strategy`",
            "`--initial-cash`",
            "`--fee-rate`",
            "`--benchmark`",
            "`--source`",
            "`TUSHARE_API_URL`",
            "fetch_analysis_bundle",
            "unadjusted fallback",
        ]:
            self.assertIn(text, guide_text)

    def test_skill_requires_comprehensive_single_stock_reports(self):
        skill_text = (ROOT / "tushare-quant" / "SKILL.md").read_text(encoding="utf-8")
        checklist_text = (ROOT / "tushare-quant" / "references" / "quant-checklist.md").read_text(encoding="utf-8")

        for text in ["daily_basic", "moneyflow", "index_daily", "fina_indicator", "adj_factor", "stk_limit", "suspend_d"]:
            self.assertIn(text, skill_text)
        for text in ["量能", "估值", "财务", "基准对比", "复权", "涨跌停", "停牌"]:
            self.assertIn(text, checklist_text)


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


class RecordsFrame:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient):
        if orient != "records":
            raise ValueError("unexpected orient")
        return self.records


class FakeResponse:
    def __init__(self, status_code, text, payload=None, json_error=False):
        self.status_code = status_code
        self.text = text
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("not json")
        return self.payload

    def __bool__(self):
        return True


class FakeApi:
    pass


def make_fake_tushare_module(
    frame=None,
    fail_adjusted=False,
    set_token_raises=False,
    print_and_raise=None,
    daily_error=None,
    endpoint_frames=None,
    endpoint_errors=None,
):
    calls = {"pro_bar_calls": []}
    fake_tushare = types.ModuleType("tushare")
    response_frame = frame or FakeFrame()
    endpoint_frames = endpoint_frames or {}
    endpoint_errors = endpoint_errors or {}

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
        for endpoint in [
            "daily_basic",
            "moneyflow",
            "index_daily",
            "fina_indicator",
            "adj_factor",
            "stk_limit",
            "suspend_d",
        ]:
            def endpoint_method(_endpoint=endpoint, **kwargs):
                calls[_endpoint] = kwargs
                calls.setdefault(f"{_endpoint}_calls", []).append(kwargs)
                if _endpoint in endpoint_errors:
                    error = endpoint_errors[_endpoint]
                    message = error(kwargs) if callable(error) else error
                    if message:
                        raise RuntimeError(message)
                frame = endpoint_frames.get(_endpoint, response_frame)
                if callable(frame):
                    return frame(kwargs)
                return frame

            setattr(calls["api"], endpoint, endpoint_method)
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
