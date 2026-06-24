"""
Curated ticker watchlists for flow monitoring and scanning.
Import and use via monitor.py --watchlist or possibly scanner.

Usage:
    python monitor.py --watchlist all
    python monitor.py --watchlist tech,semis,etfs
    python monitor.py --watchlist megacap,financials,healthcare
"""

WATCHLISTS = {

    # -----------------------------------------------------------------------
    # ETFs / Indices -- the market's heartbeat
    # -----------------------------------------------------------------------
    "etfs": [
        "SPY", "QQQ", "IWM", "DIA", "VXX", "UVXY", "SVIX",
        "TQQQ", "SQQQ", "SPXU", "UPRO", "TNA", "TZA",
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLU", "XLRE",
        "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ",
        "EEM", "EWZ", "FXI", "KWEB",
        "HYG", "LQD", "TLT", "TMF", "TBT",
        "ARKK", "ARKQ", "ARKG", "ARKW",
        "SMH", "SOXX", "IBB", "XBI",
        "JETS", "HACK", "CIBR",
    ],

    # -----------------------------------------------------------------------
    # Mega-cap -- heaviest option volume, most institutional flow
    # -----------------------------------------------------------------------
    "megacap": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG",
        "META", "TSLA", "AVGO", "ORCL", "BRK-B",
        "V", "MA", "JPM", "WMT", "UNH", "XOM",
    ],

    # -----------------------------------------------------------------------
    # Technology -- broad tech beyond mega-cap
    # -----------------------------------------------------------------------
    "tech": [
        "AAPL", "MSFT", "GOOGL", "META", "AMZN", "ORCL",
        "CRM", "ADBE", "NOW", "SAP", "INTU", "IBM",
        "DELL", "HPQ", "HPE", "CSCO", "ANET",
        "UBER", "LYFT", "ABNB", "BKNG", "EXPE",
        "SHOP", "ETSY", "EBAY", "PINS", "SNAP", "RDDT",
        "NFLX", "DIS", "WBD", "PARA", "ROKU",
        "TWLO", "ZM", "DOCN", "BOX", "DBX",
        "ACN", "CTSH", "INFY", "WIT",
    ],

    # -----------------------------------------------------------------------
    # Semiconductors -- highest IV, biggest sweeps
    # -----------------------------------------------------------------------
    "semis": [
        "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MU", "TXN",
        "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL",
        "ON", "SWKS", "MCHP", "MPWR", "WOLF", "ONTO",
        "ARM", "SMCI", "AEHR", "CEVA", "FORM",
        "SLAB", "AMBA", "ALGM", "POWI", "DIOD",
    ],

    # -----------------------------------------------------------------------
    # Cloud / SaaS / AI -- high growth, volatile, popular with options traders
    # -----------------------------------------------------------------------
    "cloud": [
        "SNOW", "PLTR", "DDOG", "NET", "CRWD", "PANW", "ZS",
        "OKTA", "GTLB", "HUBS", "VEEV", "WDAY", "COUP",
        "MDB", "ESTC", "CFLT", "DSGN", "BILL", "PAYC",
        "S", "CYBR", "FTNT", "SAIL", "SIEM",
        "AI", "BBAI", "GFAI", "MSAI",
        "CWAN", "BRZE", "ASAN", "MNDY", "FROG",
    ],

    # -----------------------------------------------------------------------
    # Financials -- rate-sensitive, big OI on banks around macro events
    # -----------------------------------------------------------------------
    "financials": [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "BX",
        "AXP", "V", "MA", "PYPL", "SQ", "SOFI", "AFRM", "LC",
        "COF", "DFS", "SYF", "ADS",
        "USB", "PNC", "TFC", "KEY", "RF", "ZION", "CFG",
        "SCHW", "RJF", "IBKR", "HOOD",
        "MET", "PRU", "AIG", "ALL", "TRV", "CB", "PGR",
        "CME", "NDAQ", "ICE", "CBOE",
        "COIN", "MSTR",   # crypto financials
    ],

    # -----------------------------------------------------------------------
    # Healthcare / Biotech -- earnings, FDA catalysts, huge IV events
    # -----------------------------------------------------------------------
    "healthcare": [
        "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "AMGN",
        "BMY", "GILD", "BIIB", "REGN", "VRTX", "MRNA",
        "ILMN", "IDXX", "IQV", "TMO", "DHR", "A",
        "MDT", "ABT", "BSX", "EW", "SYK", "BDX", "BAX",
        "HCA", "CNC", "MOH", "CVS", "WBA", "CI",
        "INCY", "ALNY", "IONS", "SRPT", "BMRN",
        "EXEL", "HALO", "RCKT", "SGEN", "RARE",
        "NVAX", "BNTX", "OCGN", "DVAX",
    ],

    # -----------------------------------------------------------------------
    # Energy -- oil, gas, renewables; reacts to geopolitics fast
    # -----------------------------------------------------------------------
    "energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC",
        "PSX", "VLO", "PXD", "FANG", "DVN", "APA", "HES",
        "HAL", "BKR", "NOV",
        "ENPH", "FSLR", "SEDG", "RUN", "NOVA", "ARRY",
        "NEE", "CEG", "CWEN", "AES",
        "LNG", "CQP", "ET", "KMI", "WMB",
    ],

    # -----------------------------------------------------------------------
    # Consumer -- retail, restaurants, e-commerce
    # -----------------------------------------------------------------------
    "consumer": [
        "AMZN", "WMT", "COST", "HD", "LOW", "TGT", "DG", "DLTR",
        "NKE", "LULU", "VFC", "PVH", "RL", "TPR",
        "MCD", "SBUX", "CMG", "YUM", "DPZ", "QSR",
        "TSLA", "F", "GM", "RIVN", "LCID", "NIO", "XPEV", "LI",
        "RACE", "HMC", "TM",
        "MGM", "WYNN", "LVS", "PENN", "DKNG",
        "CCL", "RCL", "NCLH", "MAR", "HLT", "H",
        "DAL", "UAL", "AAL", "LUV", "SAVE",
    ],

    # -----------------------------------------------------------------------
    # Defense / Aerospace -- moves on geopolitical news
    # -----------------------------------------------------------------------
    "defense": [
        "LMT", "RTX", "NOC", "GD", "BA", "HII", "L3H",
        "KTOS", "PLTR", "LDOS", "SAIC", "CACI", "BAH",
        "AXON", "AMMO", "POWW",
    ],

    # -----------------------------------------------------------------------
    # Crypto-adjacent -- high beta, volatile, strong options flow
    # -----------------------------------------------------------------------
    "crypto": [
        "COIN", "MSTR", "RIOT", "MARA", "CLSK", "IREN", "HUT",
        "BTBT", "BTDR", "WULF", "CORZ", "CIFR",
        "SQ", "PYPL", "HOOD",
    ],

    # -----------------------------------------------------------------------
    # China / International -- geopolitical event risk
    # -----------------------------------------------------------------------
    "china": [
        "BABA", "JD", "BIDU", "PDD", "NIO", "XPEV", "LI",
        "DIDI", "FUTU", "UP", "TIGR", "YUMC",
        "TSM", "ASML", "SONY", "TM", "HMC",
    ],

    # -----------------------------------------------------------------------
    # High-volatility / retail favorites -- lots of flow, fast movers
    # -----------------------------------------------------------------------
    "momentum": [
        "TSLA", "NVDA", "AMD", "AAPL", "META", "AMZN",
        "GME", "AMC", "BBBYQ", "SPCE", "NKLA",
        "PLTR", "SOFI", "RIVN", "LCID", "NIO",
        "MSTR", "COIN", "RIOT", "MARA",
        "HOOD", "RBLX", "U", "DKNG",
        "ARKK", "TQQQ", "SQQQ", "UVXY",
    ],

    # -----------------------------------------------------------------------
    # Earnings movers -- stocks with biggest option IV into earnings
    # -----------------------------------------------------------------------
    "earnings_volatile": [
        "AMZN", "GOOGL", "META", "AAPL", "MSFT", "NVDA",
        "NFLX", "TSLA", "AMD", "SNOW", "DDOG", "CRWD",
        "SHOP", "MDB", "COIN", "PLTR", "UBER",
        "JPM", "GS", "BAC", "C",
        "LLY", "MRNA", "BNTX", "REGN",
        "XOM", "CVX", "COP",
    ],

}

# Master list -- union of all categories, deduplicated
WATCHLISTS["all"] = sorted(set(
    ticker for tickers in WATCHLISTS.values() for ticker in tickers
))

# Convenient presets
WATCHLISTS["core"] = sorted(set(
    WATCHLISTS["megacap"] + WATCHLISTS["etfs"] + WATCHLISTS["semis"]
))

WATCHLISTS["aggressive"] = sorted(set(
    WATCHLISTS["momentum"] + WATCHLISTS["crypto"] + WATCHLISTS["cloud"]
))

WATCHLISTS["macro"] = sorted(set(
    WATCHLISTS["etfs"] + WATCHLISTS["financials"] + WATCHLISTS["energy"] + WATCHLISTS["defense"]
))


def resolve(names: list) -> list:
    """
    Given a list of watchlist names (and/or raw tickers), return a flat
    deduplicated sorted list of ticker symbols.

    resolve(["tech", "semis", "PLTR"])  ->  ["AAPL", "AMD", ..., "PLTR", ...]
    """
    out = set()
    for name in names:
        name = name.strip().upper()
        if name in WATCHLISTS:
            out.update(WATCHLISTS[name.lower()] if name.lower() in WATCHLISTS
                       else WATCHLISTS[name])
        else:
            # treat as a raw ticker symbol
            key = name.lower()
            if key in WATCHLISTS:
                out.update(WATCHLISTS[key])
            else:
                out.add(name)
    return sorted(out)


# Make lowercase lookup work too
_lower = {k.lower(): v for k, v in WATCHLISTS.items()}
WATCHLISTS.update(_lower)


if __name__ == "__main__":
    import sys
    names = sys.argv[1:] or ["all"]
    tickers = resolve(names)
    print(f"{len(tickers)} tickers in [{', '.join(names)}]:")
    print(", ".join(tickers))
