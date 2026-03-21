# ⚡ Semi / AI / Quantum Investment Dashboard

A free, auto-updating investment research dashboard focused on the **semiconductor, AI, and quantum computing** sectors — built for options traders.

**Live data from:**
- 📈 Yahoo Finance (prices, options chains, earnings)
- 📄 SEC EDGAR (10-K, 10-Q, 8-K filings)
- 📰 Google News RSS (sector headlines)

---

## 🚀 5-Minute Setup (Free Hosting on GitHub Pages)

### Step 1 — Create a GitHub account
Go to [github.com](https://github.com) and sign up for a free account if you don't have one.

### Step 2 — Create a new repository
1. Click the **+** button in the top-right → **New repository**
2. Name it something like `investment-dashboard`
3. Set it to **Public** (required for free GitHub Pages)
4. Click **Create repository**

### Step 3 — Upload the files
1. On your new repo page, click **Add file → Upload files**
2. Upload ALL files from this folder, preserving the folder structure:
   ```
   index.html
   generate_data.py
   requirements.txt
   .github/
     workflows/
       update_data.yml
   ```
   > Tip: You can drag the entire folder into the upload window.
3. Click **Commit changes**

### Step 4 — Enable GitHub Pages
1. Go to your repo → **Settings** → **Pages** (left sidebar)
2. Under **Source**, select **Deploy from a branch**
3. Select branch: `main`, folder: `/ (root)`
4. Click **Save**
5. After ~1 minute, your dashboard will be live at:
   `https://YOUR-USERNAME.github.io/investment-dashboard/`

### Step 5 — Run the first data fetch
1. Go to your repo → **Actions** tab
2. Click **Refresh Dashboard Data** → **Run workflow** → **Run workflow**
3. Wait ~3–5 minutes for it to complete
4. Refresh your dashboard URL — you should see live data!

After this, the workflow will **automatically run every 15 minutes** during market hours (Mon–Fri). No further action needed.

---

## 📊 Dashboard Features

| Tab | What you see |
|-----|-------------|
| **Overview** | Sector summary + price cards for all 28 tickers with price, % change, volume, market cap, IV |
| **Options Activity** | Call/put volume, OI, put/call ratio, and IV% for the nearest expiry |
| **Unusual Activity** | Options where today's volume is significantly higher than OI — potential smart money signals |
| **Earnings** | Upcoming earnings dates for tracked tickers (next 90 days) |
| **SEC Filings** | Recent 10-K, 10-Q, 8-K, and proxy filings linked directly to EDGAR |
| **News** | Latest headlines from Google News for semiconductors, AI, and quantum |

---

## 🎯 Tickers Tracked

| Sector | Tickers |
|--------|---------|
| Semiconductors | NVDA, AMD, INTC, TSM, ASML, AVGO, MU, QCOM, AMAT, LRCX |
| AI / Software | MSFT, GOOGL, META, AMZN, ORCL, PLTR, SOUN, SMCI |
| Quantum Computing | IONQ, RGTI, QUBT, IBM, QBTS, ARQQ |
| ETFs | SOXX, SMH, AIQ, QTUM |

To add or remove tickers, edit the `SECTORS` dictionary at the top of `generate_data.py`.

---

## ⚙️ Customization

**Add tickers:** Edit the `SECTORS` dict in `generate_data.py`

**Change refresh interval:** Edit the cron expression in `.github/workflows/update_data.yml`

**Add news sources:** Add RSS feed URLs to the `NEWS_FEEDS` list in `generate_data.py`

**Update your SEC contact email:** Find `your-email@example.com` in `generate_data.py` and replace it with your email. The SEC requires this in the User-Agent header per their API terms.

---

## 🔍 Options Trading Notes

- **Unusual Activity** flags options where `volume / open interest ≥ 1.5×`. Ratios above 5× are marked 🔥 HOT.
- **P/C Ratio** > 1.2 is bearish sentiment; < 0.6 is bullish. Shown in the Options Activity tab.
- **IV %** is calculated from the at-the-money call of the nearest expiry. Higher IV = more expensive options premium.
- **Earnings dates** are critical for avoiding or targeting earnings plays. Check before entering any position.

---

## ⚠️ Disclaimer

This dashboard is for research and informational purposes only. It is **not financial advice**. Options trading involves significant risk of loss. Always do your own due diligence.

---

## 🛠 Running Locally

If you want to run it on your own computer instead:

```bash
# Install dependencies
pip install -r requirements.txt

# Generate data
python generate_data.py

# Open the dashboard
open index.html   # macOS
# or just double-click index.html in your file explorer
```

The dashboard auto-refreshes every 15 minutes in the browser, but `data.json` will only update when you re-run `generate_data.py`.
