#!/usr/bin/env python3
"""
Unusual Whales Flow Monitor
============================
Polls Unusual Whales option flow 20x/minute (every 3s).
Only surfaces trades that score above a significance threshold --
large sweeps, aggressive OTM positioning, volume crushing OI, floor trades.

Setup:
    pip install requests
    export UNUSUAL_WHALES_API_KEY=your_key

Run in background:
    python monitor.py &
    python monitor.py --min-score 60 --min-premium 100000
    python monitor.py --watchlist tech,semis,etfs
    python monitor.py --watchlist all
    python monitor.py --tickers AAPL,NVDA,SPY,QQQ
    python monitor.py --calls-only
    python monitor.py --puts-only

Available watchlists: etfs, megacap, tech, semis, cloud, financials,
  healthcare, energy, consumer, defense, crypto, china, momentum,
  earnings_volatile, core, aggressive, macro, all

Stop it:
    kill %1       (if backgrounded with &)
    or Ctrl+C
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

try:
    from watchlists import resolve as resolve_watchlist, WATCHLISTS
    HAS_WATCHLISTS = True
except ImportError:
    HAS_WATCHLISTS = False

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip install requests")

UW_BASE = "https://api.unusualwhales.com"
POLL_INTERVAL = 3          # seconds between polls (20x per minute)
DEFAULT_MIN_SCORE = 45     # minimum significance score to print an alert
DEFAULT_MIN_PREMIUM = 25_000


# ---------------------------------------------------------------------------
# Scoring -- only alert on trades that actually matter
# ---------------------------------------------------------------------------

def score_trade(t: dict) -> tuple:
    """
    Returns (score, reasons) where score > DEFAULT_MIN_SCORE means alert-worthy.

    Factors:
      Premium size       -- institutional money moves markets
      Ask-side execution -- aggressor paid the spread; conviction buy/sell
      Sweep              -- broken across exchanges quickly; urgency
      OTM contract       -- pure directional bet, not a hedge
      Volume > OI        -- new positioning, not just existing OI churning
      Floor trade        -- large-cap institutional print
      Repeated hits      -- same contract hit multiple times (accumulation)
    """
    score = 0
    reasons = []

    prem = float(t.get("premium") or 0)
    vol = float(t.get("size") or t.get("volume") or 0)
    oi = float(t.get("open_interest") or 0)

    # Premium size
    if prem >= 1_000_000:
        score += 50
        reasons.append(f"${prem/1e6:.1f}M premium")
    elif prem >= 500_000:
        score += 35
        reasons.append(f"${prem/1e3:.0f}K premium")
    elif prem >= 100_000:
        score += 20
        reasons.append(f"${prem/1e3:.0f}K premium")
    elif prem >= 25_000:
        score += 8
        reasons.append(f"${prem/1e3:.0f}K premium")

    # Ask-side (aggressor, conviction)
    if t.get("is_ask_side") or t.get("ask_side"):
        score += 20
        reasons.append("ask-side")

    # Sweep (urgency across exchanges)
    if t.get("is_sweep") or t.get("type") == "sweep":
        score += 15
        reasons.append("sweep")

    # OTM (directional, not hedging)
    if t.get("is_otm") or t.get("otm"):
        score += 15
        reasons.append("OTM")

    # Volume crushing OI (new open interest, not closing)
    if oi > 0 and vol >= oi * 0.5:
        ratio = vol / oi
        score += min(25, int(ratio * 8))
        if vol >= oi:
            reasons.append(f"vol {ratio:.1f}x OI")
        else:
            reasons.append(f"vol {ratio:.0%} of OI")

    # Floor trade (institution-level)
    if t.get("is_floor") or t.get("floor"):
        score += 10
        reasons.append("floor")

    # Repeated hits (accumulation signal)
    rule = str(t.get("rule_name") or t.get("alert_rule") or "")
    if "RepeatedHits" in rule:
        score += 20
        reasons.append("repeated hits")
    if "Ascending" in rule:
        score += 10
        reasons.append("ascending fill")

    return score, reasons


def trade_direction(t: dict) -> str:
    """BULLISH / BEARISH / NEUTRAL based on option type and side."""
    is_call = str(t.get("type") or t.get("option_type") or "").lower() == "call"
    is_ask = t.get("is_ask_side") or t.get("ask_side")
    is_bid = t.get("is_bid_side") or t.get("bid_side")

    if is_call and is_ask:
        return "BULLISH"
    if not is_call and is_ask:
        return "BEARISH"
    if is_call and is_bid:
        return "BEARISH"   # closing longs or opening short calls
    if not is_call and is_bid:
        return "BULLISH"   # closing puts or opening short puts
    return "NEUTRAL"


def fmt_premium(p: float) -> str:
    if p >= 1_000_000:
        return f"${p/1e6:.2f}M"
    if p >= 1_000:
        return f"${p/1e3:.0f}K"
    return f"${p:.0f}"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def fetch_flow(api_key: str, tickers=None, calls_only=False, puts_only=False,
               min_premium=DEFAULT_MIN_PREMIUM, limit=100) -> list:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {
        "limit": limit,
        "min_premium": str(int(min_premium)),
    }
    if tickers:
        params["ticker_symbol"] = ",".join(tickers)
    if calls_only:
        params["is_call"] = "true"
    if puts_only:
        params["is_put"] = "true"

    try:
        resp = requests.get(
            f"{UW_BASE}/api/option-flow-alerts",
            headers=headers,
            params=params,
            timeout=6,
        )
        if resp.status_code == 429:
            time.sleep(5)
            return []
        if resp.status_code != 200:
            return []
        return resp.json().get("data", []) or []
    except requests.exceptions.RequestException:
        return []


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------

DIRECTION_ICON = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "─"}

def print_alert(t: dict, score: int, reasons: list):
    ticker = str(t.get("ticker_symbol") or t.get("ticker") or "???").upper()
    prem = float(t.get("premium") or 0)
    strike = t.get("strike") or "?"
    expiry = str(t.get("expiry") or t.get("expiration_date") or "?")
    otype = str(t.get("type") or t.get("option_type") or "?").upper()[:4]
    direction = trade_direction(t)
    icon = DIRECTION_ICON[direction]
    now = datetime.now().strftime("%H:%M:%S")

    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {icon} {direction}  [{now}]  {ticker}  {fmt_premium(prem)} {otype}  score={score}")
    print(f"  Strike: {strike}  Exp: {expiry}")
    print(f"  Why: {', '.join(reasons)}")

    # Plain-language summary
    summary_parts = []
    if "sweep" in reasons and "ask-side" in reasons:
        summary_parts.append("aggressive sweep -- someone is in a hurry")
    elif "ask-side" in reasons:
        summary_parts.append("paid the ask -- conviction opener")
    if "repeated hits" in reasons:
        summary_parts.append("contract hit multiple times -- accumulation")
    vol_oi = next((r for r in reasons if "OI" in r), None)
    if vol_oi:
        summary_parts.append(f"new positioning ({vol_oi})")
    if summary_parts:
        print(f"  Note: {'; '.join(summary_parts)}")
    print(bar)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Unusual Whales flow monitor.")
    ap.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                    help=f"minimum significance score to alert (default {DEFAULT_MIN_SCORE})")
    ap.add_argument("--min-premium", type=int, default=DEFAULT_MIN_PREMIUM,
                    help=f"minimum premium $ (default {DEFAULT_MIN_PREMIUM:,})")
    ap.add_argument("--watchlist",
                    help="watchlist name(s), comma-separated: tech,semis,etfs  (see watchlists.py)")
    ap.add_argument("--tickers", help="comma-separated tickers to watch, e.g. AAPL,NVDA")
    ap.add_argument("--calls-only", action="store_true")
    ap.add_argument("--puts-only", action="store_true")
    ap.add_argument("--verbose", action="store_true",
                    help="print every poll result, not just alerts")
    args = ap.parse_args()

    api_key = os.environ.get("UNUSUAL_WHALES_API_KEY")
    if not api_key:
        sys.exit("Set UNUSUAL_WHALES_API_KEY environment variable first.")

    tickers = None
    if args.watchlist and HAS_WATCHLISTS:
        tickers = resolve_watchlist([w.strip() for w in args.watchlist.split(",")])
    elif args.watchlist:
        print("watchlists.py not found -- ignoring --watchlist flag")
    if args.tickers:
        extra = [t.strip().upper() for t in args.tickers.split(",")]
        tickers = sorted(set((tickers or []) + extra))

    seen_ids = set()       # deduplicate across polls
    poll_count = 0
    alert_count = 0

    watch_str = (f" watching {len(tickers)} tickers ({args.watchlist or 'custom'})"
                 if tickers else " watching all tickers")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Flow monitor started --{watch_str}")
    print(f"  Poll every {POLL_INTERVAL}s  |  min score {args.min_score}  |  "
          f"min premium ${args.min_premium:,}")
    print("  Ctrl+C to stop\n")

    try:
        while True:
            trades = fetch_flow(
                api_key,
                tickers=tickers,
                calls_only=args.calls_only,
                puts_only=args.puts_only,
                min_premium=args.min_premium,
            )
            poll_count += 1
            new_this_poll = 0

            for t in trades:
                tid = t.get("id") or t.get("trade_id") or str(t)
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                new_this_poll += 1

                score, reasons = score_trade(t)
                if score >= args.min_score:
                    print_alert(t, score, reasons)
                    alert_count += 1
                elif args.verbose:
                    ticker = str(t.get("ticker_symbol") or "?").upper()
                    prem = float(t.get("premium") or 0)
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] "
                          f"{ticker} {fmt_premium(prem)} score={score} (below threshold)")

            # Heartbeat every 100 polls (~5 min) so you know it's alive
            if poll_count % 100 == 0:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] "
                      f"alive -- {poll_count} polls, {alert_count} alerts, "
                      f"{len(seen_ids)} unique trades seen")

            # Cap seen_ids memory -- keep last 2000
            if len(seen_ids) > 2000:
                seen_ids = set(list(seen_ids)[-1000:])

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopped. "
              f"{poll_count} polls, {alert_count} alerts fired.")


if __name__ == "__main__":
    main()
