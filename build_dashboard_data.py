#!/usr/bin/env python3
"""
Build the dashboard JSON files from the signal history.

This runs as part of the daily workflow. Outputs go to dashboard_output/
and from there get copied to the public csf-dashboard repo.

SANITISATION RULES (privacy choice 2: tickers + percentages, no dollar amounts):
  - Show: strategy, ticker, dates, days held, return %, alpha %
  - Strip: signal_price, current_price, market_cap, transaction values
  - Strip: any field that reveals position sizing or capital
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config import BENCHMARK_TICKER
from utils.data import get_benchmark_prices, get_prices
from utils.performance import compute_performance
from utils.signals import compute_open_positions, load_all_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "dashboard_output"

# Strategies we expect to track. Used for stable equity-curve indexing.
STRATEGIES = ["pead", "quality_mom", "insider", "moonshot"]

# Benchmark display names — what humans see vs the ticker
BENCHMARK_NAMES = {
    "URTH": "MSCI World",
    "IWDA.L": "MSCI World (GBP)",
    "^GSPC": "S&P 500",
}


def first_signal_date() -> pd.Timestamp | None:
    """The day the fund 'started' — first signal across all strategies."""
    signals = load_all_signals()
    if signals.empty:
        return None
    return pd.to_datetime(signals["signal_date"]).min()


def build_summary(perf: pd.DataFrame, open_positions: pd.DataFrame) -> dict:
    """Compute aggregate + per-strategy summary metrics."""
    start = first_signal_date()
    days_live = (datetime.now() - start).days if start is not None else 0

    summary = {
        "phase": "Phase 1 — paper trading",
        "days_live": days_live,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "benchmark_ticker": BENCHMARK_TICKER,
        "benchmark_name": BENCHMARK_NAMES.get(BENCHMARK_TICKER, BENCHMARK_TICKER),
        "aggregate": {},
        "strategies": [],
    }

    if perf.empty:
        return summary

    # Aggregate (all strategies, all signals)
    summary["aggregate"] = {
        "n_signals": int(len(perf)),
        "n_open": int(len(open_positions)) if not open_positions.empty else 0,
        "return_pct": float(perf["return_pct"].mean()),
        "alpha_pct": float(perf["alpha_pct"].dropna().mean()) if perf["alpha_pct"].notna().any() else None,
        "win_rate": float((perf["return_pct"] > 0).mean() * 100),
    }

    # Per strategy
    for strat in STRATEGIES:
        s_perf = perf[perf["strategy"] == strat]
        if s_perf.empty:
            continue
        summary["strategies"].append({
            "strategy": strat,
            "n_signals": int(len(s_perf)),
            "mean_return_pct": float(s_perf["return_pct"].mean()),
            "median_return_pct": float(s_perf["return_pct"].median()),
            "mean_alpha_pct": float(s_perf["alpha_pct"].dropna().mean()) if s_perf["alpha_pct"].notna().any() else None,
            "win_rate": float((s_perf["return_pct"] > 0).mean() * 100),
        })

    return summary


def sanitise_performance(perf: pd.DataFrame) -> list[dict]:
    """Strip dollar amounts; keep only what's safe to publish."""
    if perf.empty:
        return []
    keep = ["strategy", "ticker", "signal_date", "days_held", "return_pct",
            "benchmark_return_pct", "alpha_pct"]
    return perf[keep].to_dict(orient="records")


def sanitise_positions(positions: pd.DataFrame, perf: pd.DataFrame) -> list[dict]:
    """Join open positions with current performance, strip prices."""
    if positions.empty:
        return []

    # Match each open position to its perf row
    perf_lookup = {}
    for _, p in perf.iterrows():
        key = (p["strategy"], p["ticker"], p["signal_date"])
        perf_lookup[key] = p

    out = []
    for _, pos in positions.iterrows():
        key = (pos["strategy"], pos["ticker"], pos["buy_date"])
        match = perf_lookup.get(key)
        out.append({
            "strategy": pos["strategy"],
            "ticker": pos["ticker"],
            "buy_date": pos["buy_date"],
            "days_held": int(match["days_held"]) if match is not None else None,
            "return_pct": float(match["return_pct"]) if match is not None else None,
            "alpha_pct": float(match["alpha_pct"]) if match is not None and pd.notna(match["alpha_pct"]) else None,
        })
    return out


def build_equity_curves(perf: pd.DataFrame) -> dict:
    """
    Build daily equity curves for each strategy and the benchmark.

    Approach: for each day since fund inception, compute the average cumulative
    return of all positions that were open on that day. This is a simple
    equal-weighted approximation — good enough for visualisation, not for
    real performance attribution.
    """
    if perf.empty:
        return {"dates": [], "benchmark": None, "strategies": {}}

    start = first_signal_date()
    end = pd.Timestamp.today().normalize()
    if start is None or start >= end:
        return {"dates": [], "benchmark": None, "strategies": {}}

    days_span = (end - start).days + 1
    # Fetch all price data we'll need
    all_tickers = perf["ticker"].unique().tolist()
    prices = get_prices(all_tickers, lookback_days=days_span + 30)
    benchmark = get_benchmark_prices(lookback_days=days_span + 30)

    if prices.empty:
        return {"dates": [], "benchmark": None, "strategies": {}}

    # Build a daily index — business days only
    date_range = pd.bdate_range(start=start, end=end)
    date_strs = [d.strftime("%Y-%m-%d") for d in date_range]

    # Build per-position cumulative return series
    signals = load_all_signals()
    buys = signals[signals["action"] == "buy"].copy()
    buys["signal_date"] = pd.to_datetime(buys["signal_date"])
    buys["signal_price"] = buys["signal_price"].astype(float)

    out = {
        "dates": date_strs,
        "benchmark_name": BENCHMARK_NAMES.get(BENCHMARK_TICKER, BENCHMARK_TICKER),
        "benchmark": None,
        "strategies": {},
        "aggregate": None,
    }

    # Benchmark: cumulative return from fund inception
    if not benchmark.empty:
        bench_start = float(benchmark.asof(start)) if not pd.isna(benchmark.asof(start)) else None
        if bench_start and bench_start > 0:
            bench_series = []
            for d in date_range:
                val = benchmark.asof(d)
                if pd.isna(val) or val == 0:
                    bench_series.append(None)
                else:
                    bench_series.append(round((float(val) / bench_start - 1) * 100, 2))
            out["benchmark"] = bench_series

    # Per strategy: average daily return of all open positions
    for strategy in STRATEGIES:
        s_buys = buys[buys["strategy"] == strategy]
        if s_buys.empty:
            continue

        daily_returns = []
        for d in date_range:
            # Positions open on this date = bought on or before d
            open_at_d = s_buys[s_buys["signal_date"] <= d]
            if open_at_d.empty:
                daily_returns.append(0.0)
                continue

            position_returns = []
            for _, pos in open_at_d.iterrows():
                ticker = pos["ticker"]
                if ticker not in prices.columns:
                    continue
                price_at_d = prices[ticker].asof(d)
                if pd.isna(price_at_d) or price_at_d <= 0:
                    continue
                ret = (float(price_at_d) / pos["signal_price"] - 1) * 100
                position_returns.append(ret)

            if position_returns:
                daily_returns.append(round(sum(position_returns) / len(position_returns), 2))
            else:
                daily_returns.append(None)

        out["strategies"][strategy] = daily_returns

    # Aggregate: equal-weighted across strategies on each day
    strategy_series = list(out["strategies"].values())
    if strategy_series:
        agg = []
        for i in range(len(date_strs)):
            vals = [s[i] for s in strategy_series if s[i] is not None]
            agg.append(round(sum(vals) / len(vals), 2) if vals else None)
        out["aggregate"] = agg

    return out


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Computing performance...")
    perf = compute_performance()
    logger.info(f"Loaded {len(perf)} signal performance rows")

    logger.info("Computing open positions...")
    open_positions = compute_open_positions()

    logger.info("Building summary...")
    summary = build_summary(perf, open_positions)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    logger.info("Sanitising performance...")
    perf_clean = sanitise_performance(perf)
    (OUTPUT_DIR / "performance.json").write_text(json.dumps(perf_clean, indent=2, default=str))

    logger.info("Sanitising positions...")
    pos_clean = sanitise_positions(open_positions, perf)
    (OUTPUT_DIR / "positions.json").write_text(json.dumps(pos_clean, indent=2, default=str))

    logger.info("Building equity curves...")
    equity = build_equity_curves(perf)
    (OUTPUT_DIR / "equity_curves.json").write_text(json.dumps(equity, indent=2, default=str))

    # Last-touch metadata file
    (OUTPUT_DIR / "signals.json").write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "total_signals": len(perf),
        "open_positions": len(open_positions) if not open_positions.empty else 0,
    }, indent=2))

    logger.info(f"Wrote 5 JSON files to {OUTPUT_DIR}")
    print(f"\n✓ Dashboard data written to {OUTPUT_DIR}")
    print(f"  - summary.json")
    print(f"  - performance.json  ({len(perf)} rows)")
    print(f"  - positions.json    ({len(pos_clean)} positions)")
    print(f"  - equity_curves.json")
    print(f"  - signals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
