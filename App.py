import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os

# -------------------
# CONFIG
# -------------------
API_KEY = "YOUR_API_KEY_HERE"
SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA Football": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}
REGIONS = "us"
MARKETS = ["h2h", "spreads", "totals"]

BETS_LOG = "bets_log.csv"
RESULTS_LOG = "results.csv"

# -------------------
# UTILITIES
# -------------------
def load_or_create_csv(path, cols):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            for c in cols:
                if c not in df.columns:
                    df[c] = pd.NA
            df = df[cols + [c for c in df.columns if c not in cols]]
            return df
        except:
            os.rename(path, path + ".bak")
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

BETS_COLS = ["record_id","timestamp","sport","matchup","game_time","bet_type","selection","opponent","edge_pct","stake","market_total","model_total","predicted_margin","status"]
RESULTS_COLS = ["record_id","timestamp","sport","matchup","bet_type","selection","stake","edge_pct","result"]

bets_df = load_or_create_csv(BETS_LOG, BETS_COLS)
results_df = load_or_create_csv(RESULTS_LOG, RESULTS_COLS)

# -------------------
# APP HEADER
# -------------------
st.set_page_config(layout="wide", page_title="Sports Betting Assistant v2.1")
st.title("Sports Betting Assistant v2.1 — Visual Edge & Tracking")

# -------------------
# SIDEBAR SETTINGS
# -------------------
st.sidebar.header("Settings")
sport_choice = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
bankroll = st.sidebar.number_input("Your Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly Fraction", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]

# -------------------
# FETCH ODDS
# -------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": API_KEY, "regions": REGIONS, "markets": ",".join(MARKETS), "oddsFormat": "decimal"}
    try:
        r = requests.get(url, params=params)
        if r.status_code == 200:
            return r.json()
        return []
    except:
        return []

# -------------------
# RECOMMENDATION LOGIC
# -------------------
def build_recommendations(games):
    recs = []
    for i, game in enumerate(games):
        try:
            home = game["home_team"]
            away = game["away_team"]
            game_time = datetime.fromisoformat(game["commence_time"].replace("Z","+00:00"))
            bookmakers = game.get("bookmakers", [])
            markets = {}
            if bookmakers:
                for m in bookmakers[0].get("markets", []):
                    markets[m["key"]] = m.get("outcomes", [])

            # Simple edge logic
            def odds_to_prob(odds):
                try:
                    o = float(odds)
                    if o > 1:
                        return 1/o
                    return -o/(1-o)
                except:
                    return 0.5

            p_home = odds_to_prob(markets.get("h2h",[{"price":2}])[0]["price"]) if markets.get("h2h") else 0.5
            p_away = odds_to_prob(markets.get("h2h",[{"price":2}])[1]["price"]) if markets.get("h2h") else 0.5
            import math
            predicted_margin = math.log(max(min(p_home,0.9999),0.0001)/(1-max(min(p_home,0.9999),0.0001))) - \
                               math.log(max(min(p_away,0.9999),0.0001)/(1-max(min(p_away,0.9999),0.0001)))

            edges = {}
            if markets.get("h2h"):
                edges["ML Home"] = p_home - 0.5
                edges["ML Away"] = p_away - 0.5
            if markets.get("spreads"):
                edges["Spread Home"] = predicted_margin
                edges["Spread Away"] = -predicted_margin
            if markets.get("totals"):
                edges["Over"] = 0.5
                edges["Under"] = 0.5

            if edges:
                best_key = max(edges, key=lambda x: edges[x])
                edge_pct = edges[best_key]*100
                if best_key.startswith("ML"):
                    bet_type = "Moneyline"
                    selection = home if "Home" in best_key else away
                    opponent = away if "Home" in best_key else home
                elif best_key.startswith("Spread"):
                    bet_type = "Spread"
                    selection = home if "Home" in best_key else away
                    opponent = away if "Home" in best_key else home
                else:
                    bet_type = "Totals"
                    selection = best_key
                    opponent = f"{away} @ {home}"

                if bet_type in bet_type_filter and edge_pct>=min_edge_pct:
                    stake = bankroll * fractional_kelly * max(0, edges[best_key])
                    recs.append({
                        "ID": f"{i}_{int(datetime.utcnow().timestamp())}",
                        "Matchup": f"{away} @ {home}",
                        "Game Time": game_time,
                        "Bet Type": bet_type,
                        "Selection": selection,
                        "Opponent": opponent,
                        "Edge %": round(edge_pct,2),
                        "Stake $": round(stake,2),
                        "Predicted Margin": round(predicted_margin,2)
                    })
        except:
            continue
    return pd.DataFrame(recs)

# -------------------
# DISPLAY RECOMMENDATIONS
# -------------------
st.header(f"{sport_choice} Recommended Bets")
games = fetch_odds(SPORTS[sport_choice])
if not games:
    st.warning("No odds data available.")
    st.stop()

recs_df = build_recommendations(games)
if recs_df.empty:
    st.write("No recommendations available.")
else:
    # Color code edges
    def color_edges(val):
        if val >= 5: return 'background-color: #9AFF99' # green strong
        elif val >= 2: return 'background-color: #FFFF99' # yellow moderate
        else: return 'background-color: #FF9999' # red weak

    styled = recs_df.style.applymap(color_edges, subset=["Edge %"])
    st.dataframe(styled, use_container_width=True)
    st.download_button("Download Recommendations CSV", data=recs_df.to_csv(index=False).encode('utf-8'), file_name="recommendations.csv", mime="text/csv")
    st.info(f"Recommended unit size (2% of bankroll * fractional Kelly): ${bankroll * 0.02 * fractional_kelly:.2f}")

# -------------------
# BET TRACKER (PLACE & MARK RESULTS)
# -------------------
st.header("Record & Track Bets")
# load bets
bets_df = load_or_create_csv(BETS_LOG,BETS_COLS)
pending = bets_df[bets_df.get("status","PENDING")=="PENDING"] if not bets_df.empty else pd.DataFrame(columns=BETS_COLS)
if not pending.empty:
    st.subheader("Pending Bets")
    st.dataframe(pending)
    pending_opts = pending["record_id"].astype(str).tolist()
    chosen_pending = st.multiselect("Select pending bets to mark", pending_opts)
    result_choice = st.radio("Mark as", ["WON","LOST"],index=1)
    if st.button("Apply Result"):
        for rid in chosen_pending:
            idx = bets_df[bets_df["record_id"].astype(str)==str(rid)].index
            if len(idx)==0: continue
            bets_df.loc[idx,"status"] = result_choice
        bets_df.to_csv(BETS_LOG,index=False)
        st.success("Updated pending bets.")

# Display all-time record
results_df = load_or_create_csv(RESULTS_LOG,RESULTS_COLS)
if not results_df.empty:
    wins = len(results_df[results_df["result"]=="WON"])
    losses = len(results_df[results_df["result"]=="LOST"])
    st.subheader("All-Time Record")
    st.write(f"Wins: {wins} | Losses: {losses} | Total: {wins+losses}")
else:
    st.write("No resolved bets yet.")

# -------------------
# INSTRUCTIONS
# -------------------
with st.expander("Instructions"):
    st.markdown("""
1. Choose sport and adjust bankroll settings.
2. Review recommended bets (green = strong edge, yellow = moderate, red = weak).
3. Record bets you placed manually.
4. Mark pending bets as WON or LOST to track your record.
5. Download CSVs for offline review.
""")