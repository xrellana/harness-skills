import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tushare-quant" / "scripts"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


if __name__ == "__main__":
    unittest.main()
