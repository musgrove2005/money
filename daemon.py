#!/usr/bin/env python3
"""
Trading Daemon -- Unified Signal Monitor
=========================================
Runs 6 signal monitors in one polling loop. Single process, no conflicts.

  1. Option flow alerts    (UW,  every 3s)   sweeps, large premiums, repeated hits
  2. Dark pool prints      (UW,  every 5s)   off-exchange institutional positioning
  3. Market tide           (UW,  every 5s)   real-time bull/bear premium direction flip
  4. GEX tracker           (UW,  every 60s)  dealer gamma exposure on SPY/QQQ
  5. IV spike detector     (yf,  every 90s)  sudden IV jumps across watchlist
  6. Position P&L monitor  (RH,  every 30s)  hit profit target or stop loss

  + Auto-scanner: when flow fires a high-score alert, runs the full options
    strategy scanner on that ticker and prints the breakdown inline.

Setup:
    pip install requests yfinance robin_stocks

    export UNUSUAL_WHALES_API_KEY=your_key
    export ROBINHOOD_USERNAME=your_email      # optional, for position monitor
    export ROBINHOOD_PASSWORD=your_password  # optional

Run:
    python daemon.py
    python daemon.py --watchlist tech,semis,etfs
    python daemon.py --watchlist all --min-score 55 --min-premium 50000
    python daemon.py --no-scanner   # skip auto-scanner (faster alerts)
    python daemon.py --no-positions # skip Robinhood polling

    Background:
    nohup python daemon.py --watchlist core > daemon.log 2>&1 &
"""

import argparse
import os
import subprocess
import sys
import time
from collections import deque
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("pip install requests yfinance")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    print("[warn] yfinance not installed -- IV spike detector disabled")

try:
    import robin_stocks.robinhood as rh
    HAS_RH = True
except ImportError:
    HAS_RH = False

try:
    from watchlists import resolve as resolve_watchlist, WATCHLISTS
    HAS_WATCHLISTS = True
except ImportError:
    HAS_WATCHLISTS = False

UW_BASE = "https://api.unusualwhales.com"
DEFAULT_MIN_SCORE  = 45
DEFAULT_MIN_PREMIUM = 25_000
GEX_TICKERS = ["SPY", "QQQ", "IWM"]     # tickers to track GEX on
IV_BATCH_SIZE = 5                         # tickers scanned per IV cycle
PROFIT_TARGET_PCT = 50                    # alert when options position up this %
STOP_LOSS_PCT = -50                       # alert when options position down this %


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def now_str():
    return datetime.now().strftime("%H:%M:%S")


def uw_get(api_key, path, params=None):
    """Single UW API GET with timeout and 429 backoff. Returns parsed data list or {}."""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        r = requests.get(f"{UW_BASE}{path}", headers=headers,
                         params=params or {}, timeout=6)
        if r.status_code == 429:
            time.sleep(5)
            return []
        if r.status_code != 200:
            return []
        body = r.json()
        return body.get("data", body) or []
    except requests.exceptions.RequestException:
        return []


SEP = "=" * 62

def header(label, direction=""):
    icons = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "─", "INFO": "●",
             "WARN": "⚠", "": "●"}
    icon = icons.get(direction.upper(), "●")
    print(f"\n{SEP}")
    print(f"  {icon} {direction}  [{now_str()}]  {label}")


# ---------------------------------------------------------------------------
# 1. Option flow alerts
# ---------------------------------------------------------------------------

def _flow_score(t):
    score = 0
    reasons = []
    prem = float(t.get("premium") or 0)
    vol  = float(t.get("size") or t.get("volume") or 0)
    oi   = float(t.get("open_interest") or 0)

    if prem >= 1_000_000: score += 50; reasons.append(f"${prem/1e6:.1f}M premium")
    elif prem >= 500_000: score += 35; reasons.append(f"${prem/1e3:.0f}K premium")
    elif prem >= 100_000: score += 20; reasons.append(f"${prem/1e3:.0f}K premium")
    elif prem >= 25_000:  score +=  8; reasons.append(f"${prem/1e3:.0f}K premium")

    if t.get("is_ask_side") or t.get("ask_side"):
        score += 20; reasons.append("ask-side")
    if t.get("is_sweep") or t.get("type") == "sweep":
        score += 15; reasons.append("sweep")
    if t.get("is_otm") or t.get("otm"):
        score += 15; reasons.append("OTM")
    if oi > 0 and vol >= oi * 0.5:
        ratio = vol / oi
        score += min(25, int(ratio * 8))
        reasons.append(f"vol {ratio:.1f}x OI" if vol >= oi else f"vol {ratio:.0%} OI")
    if t.get("is_floor") or t.get("floor"):
        score += 10; reasons.append("floor")
    rule = str(t.get("rule_name") or "")
    if "RepeatedHits" in rule:
        score += 20; reasons.append("repeated hits")
    if "Ascending" in rule:
        score += 10; reasons.append("ascending fill")
    return score, reasons


def _flow_direction(t):
    is_call = str(t.get("type") or t.get("option_type") or "").lower() == "call"
    is_ask  = t.get("is_ask_side") or t.get("ask_side")
    if is_call and is_ask:   return "BULLISH"
    if not is_call and is_ask: return "BEARISH"
    if is_call and not is_ask: return "BEARISH"
    return "NEUTRAL"


def _fmt_prem(p):
    if p >= 1_000_000: return f"${p/1e6:.2f}M"
    if p >= 1_000:     return f"${p/1e3:.0f}K"
    return f"${p:.0f}"


def check_flow(state, api_key, min_score, min_premium, tickers,
               calls_only, puts_only, run_scanner):
    params = {"limit": 100, "min_premium": str(int(min_premium))}
    if tickers:
        params["ticker_symbol"] = ",".join(tickers[:50])  # API cap
    if calls_only: params["is_call"] = "true"
    if puts_only:  params["is_put"]  = "true"

    trades = uw_get(api_key, "/api/option-flow-alerts", params)
    new_alerts = []

    for t in trades:
        tid = t.get("id") or t.get("trade_id") or str(t)
        if tid in state["flow_seen"]:
            continue
        state["flow_seen"].add(tid)

        score, reasons = _flow_score(t)
        if score < min_score:
            continue

        direction = _flow_direction(t)
        ticker  = str(t.get("ticker_symbol") or t.get("ticker") or "???").upper()
        prem    = float(t.get("premium") or 0)
        strike  = t.get("strike") or "?"
        expiry  = str(t.get("expiry") or t.get("expiration_date") or "?")
        otype   = str(t.get("type") or t.get("option_type") or "?").upper()[:4]

        header(f"{ticker}  {_fmt_prem(prem)} {otype}  score={score}", direction)
        print(f"  Strike: {strike}   Exp: {expiry}")
        print(f"  Why: {', '.join(reasons)}")

        # Plain-language note
        notes = []
        if "sweep" in reasons and "ask-side" in reasons:
            notes.append("aggressive sweep -- in a hurry to fill")
        elif "ask-side" in reasons:
            notes.append("paid the ask -- conviction opener")
        if "repeated hits" in reasons:
            notes.append("accumulation pattern")
        vol_oi = next((r for r in reasons if "OI" in r), None)
        if vol_oi: notes.append(f"new positioning ({vol_oi})")
        if notes: print(f"  Note: {'; '.join(notes)}")
        print(SEP)

        new_alerts.append((ticker, score))

    # Auto-scanner: run possibly on the highest-score new alert
    if run_scanner and new_alerts:
        best_ticker, best_score = max(new_alerts, key=lambda x: x[1])
        if best_score >= min_score + 10:  # only scanner if notably above threshold
            _run_scanner(best_ticker)

    # Cap memory
    if len(state["flow_seen"]) > 2000:
        state["flow_seen"] = set(list(state["flow_seen"])[-1000:])


# ---------------------------------------------------------------------------
# 2. Dark pool prints
# ---------------------------------------------------------------------------

DP_MIN_PREMIUM = 500_000   # only care about $500K+ dark pool prints

def check_darkpool(state, api_key, tickers):
    params = {"limit": 50}
    if tickers:
        params["ticker_symbol"] = ",".join(tickers[:50])

    # Try common UW dark pool endpoint variants
    trades = uw_get(api_key, "/api/darkpool/recent", params)
    if not trades:
        trades = uw_get(api_key, "/api/darkpool", params)
    if not trades:
        return

    for t in trades:
        tid = t.get("id") or t.get("trade_id") or str(t)
        if tid in state["dp_seen"]:
            continue
        state["dp_seen"].add(tid)

        prem    = float(t.get("premium") or t.get("total_value") or
                        (float(t.get("price") or 0) * float(t.get("size") or 0)))
        if prem < DP_MIN_PREMIUM:
            continue

        ticker = str(t.get("ticker_symbol") or t.get("ticker") or "???").upper()
        price  = t.get("price") or "?"
        size   = t.get("size") or "?"
        stype  = str(t.get("type") or "").upper()

        header(f"DARK POOL  {ticker}  {_fmt_prem(prem)}", "INFO")
        print(f"  Price: {price}   Size: {size}   Type: {stype}")
        print(f"  Large off-exchange print -- often precedes a move 1-2 days out")
        print(SEP)

    if len(state["dp_seen"]) > 2000:
        state["dp_seen"] = set(list(state["dp_seen"])[-1000:])


# ---------------------------------------------------------------------------
# 3. Market tide (direction flip detector)
# ---------------------------------------------------------------------------

def check_tide(state, api_key):
    data = uw_get(api_key, "/api/market/market-tide")
    if not data:
        data = uw_get(api_key, "/api/market-tide")
    if not data:
        return

    # Normalize -- data could be a list or a dict
    entry = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})

    bull = float(entry.get("call_premium") or entry.get("bull_premium") or 0)
    bear = float(entry.get("put_premium")  or entry.get("bear_premium") or 0)
    total = bull + bear
    if total == 0:
        return

    bull_pct = bull / total * 100
    direction = "BULLISH" if bull_pct >= 60 else "BEARISH" if bull_pct <= 40 else "NEUTRAL"
    prev = state.get("tide_direction")

    # Alert on flip or extreme reading
    flipped = prev and direction != prev and direction != "NEUTRAL"
    extreme = bull_pct >= 75 or bull_pct <= 25

    if flipped or extreme or prev is None:
        label = "FLIP" if flipped else ("EXTREME" if extreme else "INITIAL")
        header(f"MARKET TIDE  {label}  {bull_pct:.0f}% bull / {100-bull_pct:.0f}% bear", direction)
        if flipped:
            print(f"  Direction changed: {prev} → {direction}")
        if extreme:
            side = "bullish" if bull_pct >= 75 else "bearish"
            print(f"  Heavily one-sided {side} premium -- strong intraday signal")
        print(SEP)

    state["tide_direction"] = direction
    state["tide_bull_pct"]  = bull_pct


# ---------------------------------------------------------------------------
# 4. GEX tracker (gamma exposure)
# ---------------------------------------------------------------------------

def check_gex(state, api_key):
    for ticker in GEX_TICKERS:
        data = uw_get(api_key, f"/api/stocks/{ticker}/greek-exposure")
        if not data:
            data = uw_get(api_key, f"/api/greek-exposure/{ticker}")
        if not data:
            continue

        entry = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        gex = float(entry.get("gamma_exposure") or entry.get("gex") or 0)
        if gex == 0:
            continue

        prev_gex = state["gex_prev"].get(ticker)
        state["gex_prev"][ticker] = gex

        if prev_gex is None:
            continue

        # Alert on sign flip (zero gamma crossing) or large change (>20%)
        sign_flip = (prev_gex > 0) != (gex > 0)
        pct_change = abs(gex - prev_gex) / (abs(prev_gex) + 1e-9) * 100

        if sign_flip:
            direction = "BEARISH" if gex < 0 else "BULLISH"
            header(f"GEX FLIP  {ticker}  {prev_gex:+.2e} → {gex:+.2e}", direction)
            if gex < 0:
                print(f"  Negative GEX: dealers must now amplify moves -- expect higher vol")
            else:
                print(f"  Positive GEX: dealers dampen moves -- price may pin near key strikes")
            print(SEP)
        elif pct_change >= 30:
            header(f"GEX SHIFT  {ticker}  {pct_change:.0f}% change  ({gex:+.2e})", "INFO")
            print(f"  Large GEX change may signal repositioning around key strike levels")
            print(SEP)


# ---------------------------------------------------------------------------
# 5. IV spike detector
# ---------------------------------------------------------------------------

def check_iv_spikes(state):
    if not HAS_YF:
        return

    tickers = state.get("iv_tickers", [])
    if not tickers:
        return

    # Rotate batches to avoid hammering yfinance
    idx = state.get("iv_batch_idx", 0)
    batch = tickers[idx: idx + IV_BATCH_SIZE]
    state["iv_batch_idx"] = (idx + IV_BATCH_SIZE) % len(tickers)

    for ticker in batch:
        try:
            tk = yf.Ticker(ticker)
            exps = list(tk.options or [])
            if not exps:
                continue

            # Get nearest expiry chain
            chain = tk.option_chain(exps[0])
            calls = chain.calls
            hist = tk.history(period="5d")
            if hist.empty:
                continue

            spot = float(hist["Close"].dropna().iloc[-1])
            atm = calls.loc[(calls["strike"] - spot).abs().idxmin()]
            iv = float(atm.get("impliedVolatility", 0) or 0)
            if iv <= 0:
                continue

            # Maintain rolling baseline (last 8 samples)
            baseline_q = state["iv_baseline"].setdefault(ticker, deque(maxlen=8))
            if len(baseline_q) >= 3:
                avg_iv = sum(baseline_q) / len(baseline_q)
                spike_ratio = iv / avg_iv if avg_iv > 0 else 1.0
                if spike_ratio >= 1.30:
                    header(f"IV SPIKE  {ticker}  {avg_iv*100:.0f}% → {iv*100:.0f}% IV  (+{(spike_ratio-1)*100:.0f}%)", "WARN")
                    print(f"  ATM IV jumped significantly -- catalyst or unusual positioning suspected")
                    print(f"  Consider: long straddle or check flow for directional bet")
                    print(SEP)

            baseline_q.append(iv)

        except Exception:
            continue


# ---------------------------------------------------------------------------
# 6. Position P&L monitor
# ---------------------------------------------------------------------------

def setup_robinhood():
    username = os.environ.get("ROBINHOOD_USERNAME")
    password = os.environ.get("ROBINHOOD_PASSWORD")
    if not username or not password or not HAS_RH:
        return False
    try:
        rh.login(username, password, store_session=True)
        print(f"[{now_str()}] Robinhood logged in -- position P&L monitor active")
        return True
    except Exception as e:
        print(f"[{now_str()}] Robinhood login failed: {e}")
        return False


def check_positions(state):
    if not state.get("rh_active"):
        return
    try:
        # Equity positions
        eq = rh.get_open_stock_positions() or []
        for pos in eq:
            qty   = float(pos.get("quantity") or 0)
            avg   = float(pos.get("average_buy_price") or 0)
            sym   = str(pos.get("instrument_data", {}).get("symbol") or "?")
            if qty == 0 or avg == 0:
                continue
            prices = rh.get_latest_price(sym)
            if not prices:
                continue
            current = float(prices[0])
            pct = (current - avg) / avg * 100

            if pct >= 20:
                header(f"EQUITY TARGET  {sym}  +{pct:.1f}%  ({qty:.0f} shares)", "BULLISH")
                print(f"  Avg cost: ${avg:.2f}   Current: ${current:.2f}")
                print(f"  Consider taking partial profits or trailing stop")
                print(SEP)
            elif pct <= -15:
                header(f"EQUITY STOP  {sym}  {pct:.1f}%  ({qty:.0f} shares)", "BEARISH")
                print(f"  Avg cost: ${avg:.2f}   Current: ${current:.2f}")
                print(f"  Position at loss -- review stop or double-down thesis")
                print(SEP)

        # Option positions
        opts = rh.get_open_option_positions() or []
        for pos in opts:
            qty        = float(pos.get("quantity") or 0)
            avg_price  = float(pos.get("average_price") or 0)  # per contract
            current_prc = float(pos.get("current_price") or 0) * 100
            avg_cost    = avg_price
            if qty == 0 or avg_cost == 0:
                continue

            pct = (current_prc - avg_cost) / avg_cost * 100
            sym = str(pos.get("chain_symbol") or "?")
            side = str(pos.get("option_type") or "?").upper()

            if pct >= PROFIT_TARGET_PCT:
                header(f"OPTION TARGET  {sym} {side}  +{pct:.0f}%", "BULLISH")
                print(f"  Cost: ${avg_cost:.2f}   Current: ${current_prc:.2f} per contract")
                print(f"  At {pct:.0f}% gain -- consider closing at 50% profit rule")
                print(SEP)
            elif pct <= STOP_LOSS_PCT:
                header(f"OPTION STOP  {sym} {side}  {pct:.0f}%", "BEARISH")
                print(f"  Cost: ${avg_cost:.2f}   Current: ${current_prc:.2f} per contract")
                print(f"  At {pct:.0f}% loss -- manage or close to preserve capital")
                print(SEP)

    except Exception as e:
        if state.get("verbose"):
            print(f"[{now_str()}] position check error: {e}")


# ---------------------------------------------------------------------------
# Auto-scanner: run possibly on a ticker and print inline
# ---------------------------------------------------------------------------

def _run_scanner(ticker):
    scanner = os.path.join(os.path.dirname(__file__), "possibly")
    if not os.path.exists(scanner):
        return
    print(f"\n  [auto-scanner] running strategy scan on {ticker} ...")
    try:
        result = subprocess.run(
            [sys.executable, scanner, ticker, "--dte", "35"],
            capture_output=True, text=True, timeout=45
        )
        if result.stdout:
            # Indent the scanner output for visual separation
            for line in result.stdout.strip().splitlines():
                print(f"  {line}")
    except subprocess.TimeoutExpired:
        print(f"  [auto-scanner] timed out for {ticker}")
    except Exception as e:
        print(f"  [auto-scanner] error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Unified trading signal daemon.")
    ap.add_argument("--watchlist",
                    help="watchlist name(s): tech,semis,etfs,all  (see watchlists.py)")
    ap.add_argument("--tickers",
                    help="extra tickers to watch, comma-separated")
    ap.add_argument("--min-score",   type=int, default=DEFAULT_MIN_SCORE)
    ap.add_argument("--min-premium", type=int, default=DEFAULT_MIN_PREMIUM)
    ap.add_argument("--calls-only",  action="store_true")
    ap.add_argument("--puts-only",   action="store_true")
    ap.add_argument("--no-scanner",  action="store_true",
                    help="disable auto-scanner on flow alerts")
    ap.add_argument("--no-positions", action="store_true",
                    help="disable Robinhood position monitor")
    ap.add_argument("--verbose",     action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("UNUSUAL_WHALES_API_KEY")
    if not api_key:
        sys.exit("Set UNUSUAL_WHALES_API_KEY environment variable first.")

    # Resolve tickers
    tickers = None
    if args.watchlist and HAS_WATCHLISTS:
        tickers = resolve_watchlist([w.strip() for w in args.watchlist.split(",")])
    elif args.watchlist:
        print("[warn] watchlists.py not found -- ignoring --watchlist")
    if args.tickers:
        extra = [t.strip().upper() for t in args.tickers.split(",")]
        tickers = sorted(set((tickers or []) + extra))

    # IV scanner always uses a manageable subset
    iv_tickers = []
    if HAS_WATCHLISTS and HAS_YF:
        iv_tickers = (tickers or WATCHLISTS.get("core", []))[:100]

    # Robinhood login
    rh_active = False
    if not args.no_positions:
        rh_active = setup_robinhood()

    # Shared state
    state = {
        "flow_seen":      set(),
        "dp_seen":        set(),
        "tide_direction": None,
        "tide_bull_pct":  None,
        "gex_prev":       {},
        "iv_baseline":    {},
        "iv_tickers":     iv_tickers,
        "iv_batch_idx":   0,
        "rh_active":      rh_active,
        "verbose":        args.verbose,
    }

    # Schedule: track last-run epoch per signal
    last = {k: 0.0 for k in ("flow", "darkpool", "tide", "gex", "iv", "positions")}
    INTERVALS = {
        "flow":      3,
        "darkpool":  5,
        "tide":      5,
        "gex":      60,
        "iv":       90,
        "positions": 30,
    }

    watch_label = (f"{len(tickers)} tickers ({args.watchlist or 'custom'})"
                   if tickers else "all tickers")
    print(f"\n{'='*62}")
    print(f"  Trading Daemon  [{now_str()}]")
    print(f"  Watching: {watch_label}")
    print(f"  Signals:  flow | darkpool | tide | GEX | IV spikes | positions")
    print(f"  Min score: {args.min_score}   Min premium: ${args.min_premium:,}")
    print(f"  Ctrl+C to stop")
    print(f"{'='*62}\n")

    poll_count = 0
    try:
        while True:
            now = time.time()

            if now - last["flow"] >= INTERVALS["flow"]:
                check_flow(state, api_key, args.min_score, args.min_premium,
                           tickers, args.calls_only, args.puts_only,
                           not args.no_scanner)
                last["flow"] = now

            if now - last["darkpool"] >= INTERVALS["darkpool"]:
                check_darkpool(state, api_key, tickers)
                last["darkpool"] = now

            if now - last["tide"] >= INTERVALS["tide"]:
                check_tide(state, api_key)
                last["tide"] = now

            if now - last["gex"] >= INTERVALS["gex"]:
                check_gex(state, api_key)
                last["gex"] = now

            if now - last["iv"] >= INTERVALS["iv"]:
                check_iv_spikes(state)
                last["iv"] = now

            if now - last["positions"] >= INTERVALS["positions"]:
                check_positions(state)
                last["positions"] = now

            poll_count += 1

            # Heartbeat every ~5 min
            if poll_count % 1000 == 0:
                tide = state.get("tide_bull_pct")
                tide_str = f"  Tide: {tide:.0f}% bull" if tide else ""
                print(f"  [{now_str()}] alive -- {poll_count} ticks{tide_str}")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n[{now_str()}] Daemon stopped after {poll_count} ticks.")


if __name__ == "__main__":
    main()
