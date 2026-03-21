"""
Investment Dashboard - Data Generator
======================================
Fetches stock prices, options activity, earnings, SEC filings, and news
for the Semiconductor / AI / Quantum Computing investment dashboard.

Run this script manually or via GitHub Actions to refresh data.json.
"""

import yfinance as yf
import requests
import feedparser
import json
import time
import sys
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

SECTORS = {
    "Semiconductors": ["NVDA", "AMD", "INTC", "TSM", "ASML", "AVGO", "MU", "QCOM", "AMAT", "LRCX"],
    "AI / Software":  ["MSFT", "GOOGL", "META", "AMZN", "ORCL", "PLTR", "SOUN", "SMCI"],
    "Quantum Computing": ["IONQ", "RGTI", "QUBT", "IBM", "QBTS", "ARQQ"],
    "ETFs":           ["SOXX", "SMH", "AIQ", "QTUM"],
}

ALL_TICKERS = [t for tickers in SECTORS.values() for t in tickers]

# SEC EDGAR requires a User-Agent with contact info
SEC_HEADERS = {
    "User-Agent": "InvestmentDashboard/1.0 (contact: your-email@example.com)",
    "Accept-Encoding": "gzip, deflate",
}

NEWS_FEEDS = [
    ("Google News – Semiconductors",
     "https://news.google.com/rss/search?q=semiconductor+chip+NVDA+AMD+TSMC&hl=en-US&gl=US&ceid=US:en"),
    ("Google News – AI Investing",
     "https://news.google.com/rss/search?q=artificial+intelligence+investing+NVDA+MSFT+META&hl=en-US&gl=US&ceid=US:en"),
    ("Google News – Quantum Computing",
     "https://news.google.com/rss/search?q=quantum+computing+investing+IonQ+IBM&hl=en-US&gl=US&ceid=US:en"),
    ("Yahoo Finance",
     "https://finance.yahoo.com/news/rssindex"),
]

# Vol/OI ratio threshold to flag unusual options activity
UNUSUAL_RATIO_THRESHOLD = 1.5
# Minimum volume to consider (filters noise)
MIN_VOLUME = 200

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def safe_float(val, default=None):
    try:
        if val is None:
            return default
        f = float(val)
        return None if (f != f) else round(f, 4)  # NaN check
    except Exception:
        return default

def safe_int(val, default=0):
    try:
        return int(val) if val is not None else default
    except Exception:
        return default

def format_large_num(n):
    if n is None:
        return None
    n = int(n)
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.2f}T"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    return str(n)

# ─────────────────────────────────────────────
#  1. STOCK DATA
# ─────────────────────────────────────────────

def fetch_stock_data():
    print("  Fetching stock data...")
    stocks = {}

    for sector, tickers in SECTORS.items():
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                info = t.fast_info

                # Use fast_info for speed; fall back to .info for extras
                price       = safe_float(getattr(info, "last_price", None))
                prev_close  = safe_float(getattr(info, "previous_close", None))
                volume      = safe_int(getattr(info, "three_month_average_volume", None))
                market_cap  = safe_int(getattr(info, "market_cap", None))
                w52_high    = safe_float(getattr(info, "year_high", None))
                w52_low     = safe_float(getattr(info, "year_low", None))

                change_pct = None
                if price and prev_close and prev_close != 0:
                    change_pct = round(((price - prev_close) / prev_close) * 100, 2)

                # Richer info (slower but cached by yfinance)
                full_info = {}
                try:
                    full_info = t.info
                except Exception:
                    pass

                stocks[ticker] = {
                    "sector":      sector,
                    "name":        full_info.get("shortName", ticker),
                    "price":       price,
                    "prev_close":  prev_close,
                    "change_pct":  change_pct,
                    "volume":      volume,
                    "volume_fmt":  format_large_num(volume),
                    "market_cap":  market_cap,
                    "market_cap_fmt": format_large_num(market_cap),
                    "52w_high":    w52_high,
                    "52w_low":     w52_low,
                    "pe_ratio":    safe_float(full_info.get("forwardPE") or full_info.get("trailingPE")),
                    "iv":          None,   # filled in by options pass
                    "beta":        safe_float(full_info.get("beta")),
                }
                print(f"    ✓ {ticker}: ${price} ({change_pct:+.2f}%)" if change_pct is not None else f"    ✓ {ticker}: ${price}")
                time.sleep(0.15)

            except Exception as e:
                print(f"    ✗ {ticker}: {e}")
                stocks[ticker] = {"sector": sector, "name": ticker, "error": str(e)}

    return stocks


# ─────────────────────────────────────────────
#  2. OPTIONS DATA
# ─────────────────────────────────────────────

def fetch_options_data(stocks):
    print("  Fetching options data...")
    options_summary = []
    unusual_activity = []

    for ticker in ALL_TICKERS:
        try:
            t = yf.Ticker(ticker)
            expiries = t.options

            if not expiries:
                continue

            current_price = stocks.get(ticker, {}).get("price") or 0

            # Look at nearest 2 expiries for unusual activity detection
            for expiry_idx, expiry in enumerate(expiries[:2]):
                try:
                    chain = t.option_chain(expiry)
                    calls = chain.calls
                    puts  = chain.puts

                    if calls.empty and puts.empty:
                        continue

                    # ── Aggregate stats ──
                    total_call_vol = safe_int(calls["volume"].sum()) if not calls.empty else 0
                    total_put_vol  = safe_int(puts["volume"].sum())  if not puts.empty else 0
                    total_call_oi  = safe_int(calls["openInterest"].sum()) if not calls.empty else 0
                    total_put_oi   = safe_int(puts["openInterest"].sum())  if not puts.empty else 0
                    pcr = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None

                    # ── ATM implied volatility ──
                    atm_iv = None
                    if not calls.empty and current_price > 0:
                        calls = calls.copy()
                        calls["strike_diff"] = abs(calls["strike"] - current_price)
                        atm_row = calls.loc[calls["strike_diff"].idxmin()]
                        raw_iv = atm_row.get("impliedVolatility", 0)
                        atm_iv = round(safe_float(raw_iv, 0) * 100, 1)

                    if expiry_idx == 0:
                        options_summary.append({
                            "ticker":      ticker,
                            "expiry":      expiry,
                            "call_vol":    total_call_vol,
                            "put_vol":     total_put_vol,
                            "call_oi":     total_call_oi,
                            "put_oi":      total_put_oi,
                            "pcr":         pcr,
                            "iv":          atm_iv,
                        })
                        if ticker in stocks and atm_iv is not None:
                            stocks[ticker]["iv"] = atm_iv

                    # ── Unusual activity scan ──
                    for opt_type, df in [("CALL", calls), ("PUT", puts)]:
                        if df.empty:
                            continue
                        df = df.copy()
                        for _, row in df.iterrows():
                            vol = safe_int(row.get("volume", 0))
                            oi  = safe_int(row.get("openInterest", 0))
                            if vol < MIN_VOLUME or oi == 0:
                                continue
                            ratio = round(vol / oi, 2)
                            if ratio >= UNUSUAL_RATIO_THRESHOLD:
                                iv_val = round(safe_float(row.get("impliedVolatility", 0), 0) * 100, 1)
                                unusual_activity.append({
                                    "ticker":   ticker,
                                    "type":     opt_type,
                                    "expiry":   expiry,
                                    "strike":   safe_float(row.get("strike")),
                                    "volume":   vol,
                                    "oi":       oi,
                                    "ratio":    ratio,
                                    "iv":       iv_val,
                                    "last":     safe_float(row.get("lastPrice")),
                                    "bid":      safe_float(row.get("bid")),
                                    "ask":      safe_float(row.get("ask")),
                                    "in_money": bool(row.get("inTheMoney", False)),
                                })

                    time.sleep(0.2)
                except Exception as e:
                    print(f"    ✗ {ticker} options ({expiry}): {e}")

            print(f"    ✓ {ticker}: options done")

        except Exception as e:
            print(f"    ✗ {ticker} options: {e}")

    # Sort unusual activity by ratio descending
    unusual_activity.sort(key=lambda x: x["ratio"], reverse=True)
    return options_summary, unusual_activity[:75]


# ─────────────────────────────────────────────
#  3. EARNINGS CALENDAR
# ─────────────────────────────────────────────

def fetch_earnings():
    print("  Fetching earnings calendar...")
    earnings = []
    today = datetime.now().date()
    cutoff = today + timedelta(days=90)

    for ticker in ALL_TICKERS:
        try:
            t = yf.Ticker(ticker)

            # yfinance returns earnings dates differently across versions
            # Try .calendar first, then .earnings_dates
            cal = None
            try:
                cal = t.calendar
            except Exception:
                pass

            if cal is not None and hasattr(cal, "T"):
                cal = cal.T

            if cal is not None and not cal.empty:
                for col in ["Earnings Date", "earningsDate"]:
                    if col in cal.columns:
                        val = cal[col].iloc[0]
                        if hasattr(val, "date"):
                            edate = val.date()
                        else:
                            try:
                                edate = datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
                            except Exception:
                                edate = None
                        if edate and today <= edate <= cutoff:
                            earnings.append({
                                "ticker":       ticker,
                                "date":         str(edate),
                                "days_away":    (edate - today).days,
                                "eps_estimate": safe_float(cal.get("EPS Estimate", [None]).iloc[0]
                                                           if "EPS Estimate" in cal.columns else None),
                            })
                        break

            # Fallback: try earnings_dates property
            if not any(e["ticker"] == ticker for e in earnings):
                try:
                    ed = t.earnings_dates
                    if ed is not None and not ed.empty:
                        future = ed[ed.index > datetime.now(timezone.utc)]
                        if not future.empty:
                            next_date = future.index[0]
                            edate = next_date.date()
                            if today <= edate <= cutoff:
                                earnings.append({
                                    "ticker":       ticker,
                                    "date":         str(edate),
                                    "days_away":    (edate - today).days,
                                    "eps_estimate": None,
                                })
                except Exception:
                    pass

            time.sleep(0.15)

        except Exception as e:
            print(f"    ✗ {ticker} earnings: {e}")

    earnings.sort(key=lambda x: x["date"])
    print(f"    ✓ Found {len(earnings)} upcoming earnings dates")
    return earnings


# ─────────────────────────────────────────────
#  4. SEC EDGAR FILINGS
# ─────────────────────────────────────────────

def fetch_sec_filings():
    print("  Fetching SEC EDGAR filings...")
    filings = []
    TARGET_FORMS = {"10-K", "10-Q", "8-K", "DEF 14A"}

    # Load SEC's canonical ticker→CIK mapping
    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=SEC_HEADERS, timeout=15
        )
        resp.raise_for_status()
        ticker_map = resp.json()
    except Exception as e:
        print(f"    ✗ Could not load SEC ticker map: {e}")
        return []

    cik_lookup = {
        v["ticker"]: str(v["cik_str"]).zfill(10)
        for v in ticker_map.values()
    }

    for ticker in ALL_TICKERS:
        cik = cik_lookup.get(ticker)
        if not cik:
            print(f"    ? {ticker}: no CIK found")
            continue

        try:
            sub_resp = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=SEC_HEADERS, timeout=15
            )
            sub_resp.raise_for_status()
            sub = sub_resp.json()

            company_name = sub.get("name", ticker)
            recent = sub.get("filings", {}).get("recent", {})
            forms   = recent.get("form", [])
            dates   = recent.get("filingDate", [])
            accnums = recent.get("accessionNumber", [])
            docs    = recent.get("primaryDocument", [])

            for i, form in enumerate(forms):
                if form not in TARGET_FORMS:
                    continue
                if i >= len(dates):
                    break
                acc_clean = accnums[i].replace("-", "") if i < len(accnums) else ""
                doc       = docs[i] if i < len(docs) else ""
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
                    if acc_clean and doc else
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=10"
                )
                index_url = (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=10"
                )
                filings.append({
                    "ticker":       ticker,
                    "company":      company_name,
                    "form":         form,
                    "date":         dates[i],
                    "url":          filing_url,
                    "index_url":    index_url,
                })
                if len([f for f in filings if f["ticker"] == ticker]) >= 5:
                    break  # Max 5 filings per ticker

            print(f"    ✓ {ticker}: {len([f for f in filings if f['ticker'] == ticker])} filings")
            time.sleep(0.4)  # Respect SEC rate limits

        except Exception as e:
            print(f"    ✗ {ticker} SEC: {e}")

    filings.sort(key=lambda x: x["date"], reverse=True)
    return filings[:120]


# ─────────────────────────────────────────────
#  5. NEWS FEEDS
# ─────────────────────────────────────────────

def fetch_news():
    print("  Fetching news feeds...")
    news = []

    for source_name, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:12]:
                pub = entry.get("published", entry.get("updated", ""))
                summary = entry.get("summary", "")
                # Strip basic HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:300]

                news.append({
                    "source":    source_name,
                    "title":     entry.get("title", ""),
                    "url":       entry.get("link", ""),
                    "published": pub,
                    "summary":   summary.strip(),
                })
            print(f"    ✓ {source_name}: {min(12, len(feed.entries))} articles")
        except Exception as e:
            print(f"    ✗ {source_name}: {e}")

    return news[:60]


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    start = datetime.now()
    print(f"\n{'='*55}")
    print(f"  Investment Dashboard – Data Refresh")
    print(f"  {start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*55}\n")

    print("[1/5] Stock prices & fundamentals")
    stocks = fetch_stock_data()

    print("\n[2/5] Options chains & unusual activity")
    options_summary, unusual_activity = fetch_options_data(stocks)

    print("\n[3/5] Earnings calendar")
    earnings = fetch_earnings()

    print("\n[4/5] SEC EDGAR filings")
    sec_filings = fetch_sec_filings()

    print("\n[5/5] News feeds")
    news = fetch_news()

    # ── Compute sector performance summaries ──
    sector_stats = {}
    for sector, tickers in SECTORS.items():
        changes = [stocks[t]["change_pct"] for t in tickers
                   if t in stocks and stocks[t].get("change_pct") is not None]
        sector_stats[sector] = {
            "avg_change": round(sum(changes) / len(changes), 2) if changes else None,
            "gainers":    sum(1 for c in changes if c > 0),
            "losers":     sum(1 for c in changes if c < 0),
            "flat":       sum(1 for c in changes if c == 0),
        }

    output = {
        "last_updated":    start.isoformat() + "Z",
        "sectors":         SECTORS,
        "sector_stats":    sector_stats,
        "stocks":          stocks,
        "options":         options_summary,
        "unusual_activity": unusual_activity,
        "earnings":        earnings,
        "sec_filings":     sec_filings,
        "news":            news,
    }

    with open("data.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'='*55}")
    print(f"  ✅ data.json written in {elapsed:.1f}s")
    print(f"  Stocks: {len(stocks)} | Unusual: {len(unusual_activity)}")
    print(f"  Earnings: {len(earnings)} | Filings: {len(sec_filings)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
