import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
import itertools

# -------------------
# CONFIG
# -------------------
API_KEY_ODDS = "YOUR_ODDS_API_KEY"   # <-- replace with your Odds API key
SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA Football": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}
REGIONS = "us"
MARKETS = ["h2h", "spreads", "totals"]

BETS_LOG = "bets_log.csv"
BETS_COLS = [
    "record_id", "timestamp", "sport", "home_team", "away_team", "matchup",
    "game_time", "bet_type", "selection", "opponent",
    "edge_pct", "stake", "status"
]

# -------------------
# HELPERS
# -------------------
def load_or_create_csv(path, cols):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            for c in cols:
                if c not in df.columns:
                    df[c] = pd.NA
            return df[cols]
        except:
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

bets_df = load_or_create_csv(BETS_LOG, BETS_COLS)

def odds_to_prob(odds):
    """Convert decimal odds to implied probability."""
    try:
        return 1.0 / float(odds)
    except:
        return 0.5

def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY_ODDS,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "oddsFormat": "decimal"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.sidebar.error(f"Odds fetch error for {sport_key}: {e}")
        return []

def recommend_bet(game, sport_name, bankroll=1000, kelly_fraction=0.25, min_edge=2):
    """Basic recs using implied probability vs 50/50 baseline."""
    try:
        home, away = game.get("home_team"), game.get("away_team")
        commence = game.get("commence_time")
        game_time = datetime.fromisoformat(commence.replace("Z", "+00:00")) if commence else None

        bookmakers = game.get("bookmakers", [])
        if not bookmakers: return None
        first = bookmakers[0]
        markets = {m["key"]: m.get("outcomes", []) for m in first.get("markets", [])}

        edges = {}
        if "h2h" in markets and len(markets["h2h"]) >= 2:
            o0, o1 = markets["h2h"][0]["price"], markets["h2h"][1]["price"]
            p_home, p_away = odds_to_prob(o0), odds_to_prob(o1)
            edges["ML Home"] = p_home - 0.5
            edges["ML Away"] = p_away - 0.5

        if "spreads" in markets:
            edges["Spread Home"] = 0.02
            edges["Spread Away"] = 0.02

        if "totals" in markets:
            edges["Over"] = 0.01
            edges["Under"] = 0.01

        if not edges: return None

        best_key = max(edges, key=lambda k: edges[k])
        edge_pct = edges[best_key] * 100
        if edge_pct < min_edge: return None

        if "ML" in best_key:
            bt = "Moneyline"
            sel = home if "Home" in best_key else away
            opp = away if "Home" in best_key else home
        elif "Spread" in best_key:
            bt = "Spread"
            sel = home if "Home" in best_key else away
            opp = away if "Home" in best_key else home
        else:
            bt = "Totals"
            sel = best_key
            opp = f"{away} @ {home}"

        stake = round(bankroll * kelly_fraction * max(0, edges[best_key]), 2)

        return {
            "record_id": f"{sport_name}_{int(datetime.utcnow().timestamp())}",
            "timestamp": datetime.utcnow(),
            "sport": sport_name,
            "home_team": home, "away_team": away,
            "matchup": f"{away} @ {home}", "game_time": game_time,
            "bet_type": bt, "selection": sel, "opponent": opp,
            "edge_pct": round(edge_pct, 2), "stake": stake, "status": "PENDING"
        }
    except:
        return None

def build_all_recs(bankroll=1000, kelly_fraction=0.25, min_edge=2):
    rows = []
    for s in SPORTS:
        games = fetch_odds(SPORTS[s])
        for g in games:
            r = recommend_bet(g, s, bankroll, kelly_fraction, min_edge)
            if r: rows.append(r)
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=BETS_COLS)

# -------------------
# STREAMLIT UI
# -------------------
st.set_page_config(layout="wide", page_title="Smart Betting Assistant v3.0")
st.title("Smart Betting Assistant v3.0 — Phase 1")

# Sidebar settings
st.sidebar.header("Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge %", 0.0, 100.0, 2.0, step=0.5)

# Fetch new recs
with st.spinner("Fetching odds and building recommendations..."):
    new = build_all_recs(bankroll, fractional_kelly, min_edge_pct)
    if not new.empty:
        bets_df = pd.concat([bets_df, new]).drop_duplicates(subset=["record_id"], keep="first")

# Parlays
st.subheader("Best Parlays (Pick-3 to Pick-8)")
top = bets_df[bets_df["status"] == "PENDING"].sort_values("edge_pct", ascending=False).head(12)
if len(top) >= 3:
    parlays = []
    for r in range(3, min(8, len(top)) + 1):
        for combo in itertools.combinations(top.index, r):
            sel = [top.loc[i, "selection"] for i in combo]
            parlays.append({"Parlay": " + ".join(sel)})
    st.dataframe(pd.DataFrame(parlays))
else:
    st.write("Not enough bets yet.")

# All bets
st.header("All Bets")
def style_row(row):
    e = float(row["edge_pct"]) if not pd.isna(row["edge_pct"]) else 0
    stt = row["status"].upper()
    if stt == "WON": return ["background-color:#ADD8E6"] * len(row)
    if stt == "LOST": return ["background-color:#D3D3D3"] * len(row)
    if e >= 5: return ["background-color:#9AFF99"] * len(row)
    if e >= 2: return ["background-color:#FFFF99"] * len(row)
    return ["background-color:#FF9999"] * len(row)

st.dataframe(bets_df.style.apply(style_row, axis=1), use_container_width=True)

# Update pending
st.subheader("Update Pending Bets")
pending = bets_df[bets_df["status"] == "PENDING"]
if not pending.empty:
    chosen = st.multiselect("Select pending bets", pending["record_id"].astype(str).tolist())
    result = st.radio("Mark as", ["WON", "LOST"])
    if st.button("Apply"):
        for rid in chosen:
            idx = bets_df[bets_df["record_id"].astype(str) == rid].index
            bets_df.loc[idx, "status"] = result
        bets_df.to_csv(BETS_LOG, index=False)
        st.success("Updated pending bets!")

# Record summary
wins = len(bets_df[bets_df["status"] == "WON"])
losses = len(bets_df[bets_df["status"] == "LOST"])
st.subheader("All-Time Record")
st.write(f"Wins: {wins} | Losses: {losses} | Total: {wins + losses}")