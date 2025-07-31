import re, time, os, json, datetime
import pandas as pd
import requests
from collections import defaultdict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# === Settings ===
SUBREDDITS = ["wallstreetbets", "stocks", "investing", "StockMarket",
              "pennystocks", "smallstreetbets", "weedstocks"]
POST_LIMIT = 100
USER_AGENT = "Mozilla/5.0 (stock-scraper)"
TIMESTAMP = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
HISTORY_FILE = f"history_{TIMESTAMP}.json"
CSV_OUT = f"sentiment_snapshot_{TIMESTAMP}.csv"

# ==================

analyzer = SentimentIntensityAnalyzer()
ticker_re = re.compile(r'\$[A-Z]{1,5}')

def extract_tickers(txt):
    return ticker_re.findall(txt.upper())

def fetch_posts(sub):
    url = f"https://www.reddit.com/r/{sub}/hot.json"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                        params={"limit": POST_LIMIT}, timeout=10)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    data = resp.json().get("data", {}).get("children", [])
    return [{
        "text": f"{d.get('title','')} {d.get('selftext','')}",
        "upvotes": d.get("score", 0)
    } for d in (c["data"] for c in data)]

def analyze(posts, source, hist):
    now = datetime.datetime.utcnow().isoformat()
    stats = defaultdict(lambda: {"mentions": 0, "sentences": [], "upvotes": 0})
    for p in posts:
        tickers = set(extract_tickers(p["text"]))
        if not tickers: continue
        score = analyzer.polarity_scores(p["text"])["compound"]
        for t in tickers:
            st = stats[t]
            st["mentions"] += 1
            st["sentences"].append(score)
            st["upvotes"] += p["upvotes"]

    rows = []
    for t, d in stats.items():
        m = d["mentions"]
        sent_list = d["sentences"]
        avg_sent = sum(sent_list) / m
        sent_vol = pd.Series(sent_list).std()
        weighted_sent = sum(s * u for s, u in zip(sent_list, [d["upvotes"]] * len(sent_list))) / max(d["upvotes"], 1)
        net = sum(1 for s in sent_list if s > 0.05) / m - sum(1 for s in sent_list if s < -0.05) / m

        hist_m, hist_std = hist.get(t, {}).get("mean", 0), hist.get(t, {}).get("std", 1)
        momentum = (m - hist_m) / hist_std if hist_std else None

        signal = "LONG" if avg_sent > 0.3 and (momentum is None or momentum > 1) \
            else ("SHORT" if avg_sent < -0.3 else "NEUTRAL")

        rows.append({
            "timestamp": now,
            "Subreddit": source,
            "Ticker": t,
            "Mentions": m,
            "Avg_Sentiment": round(avg_sent, 3),
            "Weighted_Sentiment": round(weighted_sent, 3),
            "Sentiment_Volatility": round(sent_vol, 3),
            "Net_Sentiment": round(net, 3),
            "Momentum": round(momentum, 3) if momentum is not None else None,
            "Signal": signal
        })
    return rows

def load_history():
    if os.path.exists(HISTORY_FILE):
        return json.load(open(HISTORY_FILE))
    return {}

def save_history(hist):
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f)

def summarize_market(df):
    summary = {}
    long_count = len(df[df["Signal"] == "LONG"])
    short_count = len(df[df["Signal"] == "SHORT"])
    neutral_count = len(df[df["Signal"] == "NEUTRAL"])
    total = len(df)

    summary["LONG %"] = round(100 * long_count / total, 2)
    summary["SHORT %"] = round(100 * short_count / total, 2)
    summary["NEUTRAL %"] = round(100 * neutral_count / total, 2)
    summary["Average Sentiment"] = round(df["Avg_Sentiment"].mean(), 3)
    summary["Weighted Market Sentiment"] = round(df["Weighted_Sentiment"].mean(), 3)
    summary["Sentiment Volatility (avg)"] = round(df["Sentiment_Volatility"].mean(), 3)

    sub_counts = df["Subreddit"].value_counts().to_dict()
    summary["Subreddit Activity"] = sub_counts

    if summary["LONG %"] > 50 and summary["Average Sentiment"] > 0.2:
        summary["Market Sentiment"] = "BULLISH"
    elif summary["SHORT %"] > 40 and summary["Average Sentiment"] < -0.2:
        summary["Market Sentiment"] = "BEARISH"
    else:
        summary["Market Sentiment"] = "NEUTRAL"

    return summary

def print_summary(summary):
    print("\n=== Market Summary ===")
    for k, v in summary.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for sub, count in v.items():
                print(f"  {sub}: {count} tickers")
        else:
            print(f"{k}: {v}")
    print("======================\n")

def write_full_csv(df, summary):
    with open(CSV_OUT, "w", encoding="utf-8") as f:
        df.to_csv(f, index=False)
        f.write("\n\nMarket Summary:\n")
        for k, v in summary.items():
            if isinstance(v, dict):
                f.write(f"{k}:\n")
                for sub, count in v.items():
                    f.write(f"  {sub},{count}\n")
            else:
                f.write(f"{k},{v}\n")

def main():
    hist = load_history()
    all_data = []

    for sub in SUBREDDITS:
        try:
            posts = fetch_posts(sub)
        except Exception as e:
            print(f"Error fetching r/{sub}: {e}")
            posts = []
        analyzed = analyze(posts, f"r/{sub}", hist)
        all_data.extend(analyzed)
        time.sleep(1)

    df = pd.DataFrame(all_data)
    if df.empty:
        print("No tickers found")
        return

    df.sort_values(["Momentum", "Mentions"], ascending=False, inplace=True)

    summary = summarize_market(df)
    print_summary(summary)

    write_full_csv(df, summary)
    print("Snapshot with market summary saved:", CSV_OUT)

    new_hist = {}
    for t, group in df.groupby("Ticker"):
        new_hist[t] = {
            "mean": group["Mentions"].mean(),
            "std": group["Mentions"].std()
        }
    save_history(new_hist)

    print(df.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
