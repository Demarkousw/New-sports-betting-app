import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(layout="wide")
st.title("NFL Betting App — Simple ML / Spread / O/U Recommendations")

# -------------------------
# Sidebar settings
# -------------------------
st.sidebar.header("Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 50.0, 1.0, step=0.5)
league_avg_total = st.sidebar.number_input("League-average total (for O/U)", value=45, step=1)

# -------------------------
# API setup
# -------------------------
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT = "americanfootball_nfl"
MARKETS = "h2h,spreads,totals"

st.info("Fetching NFL odds...")

# -------------------------
# Fetch odds function
# -------------------------
def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": API_KEY, "regions": "us", "markets": MARKETS}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"Error fetching odds: {e}")
        return []

data = fetch_odds()
if not data:
    st.stop()

# -------------------------
# Convert API JSON to DataFrame
# -------------------------
games = []
for game in data:
    home = game.get("home_team")
    away = game.get("away_team")
    try:
        game_time = datetime.fromisoformat(game.get("commence_time").replace("Z","+00:00"))
    except:
        game_time = game.get("commence_time")

    ml_home = ml_away = None
    spread_home = spread_away = None
    total_over = total_under = None

    bookmakers = game.get("bookmakers") or []
    if bookmakers:
        markets = bookmakers[0].get("markets") or []
        for m in markets:
            key = m.get("key")
            outcomes = m.get("outcomes") or []
            if key == "h2h" and len(outcomes) >= 2:
                ml_home = outcomes[0].get("price")
                ml_away = outcomes[1].get("price")
            elif key == "spreads" and len(outcomes) >= 2:
                spread_home = outcomes[0].get("point")
                spread_away = outcomes[1].get("point")
            elif key == "totals" and len(outcomes) >= 2:
                total_over = outcomes[0].get("point")
                total_under = outcomes[1].get("point")

    games.append({
        "home": home,
        "away": away,
        "game_time": game_time,
        "ml_home": ml_home,
        "ml_away": ml_away,
        "spread_home": spread_home,
        "spread_away": spread_away,
        "total_over": total_over,
        "total_under": total_under
    })

df = pd.DataFrame(games)

# -------------------------
# Helper functions
# -------------------------
def odds_to_prob(odds):
    if odds is None:
        return 0.5  # fallback
    try:
        odds = float(odds)
    except:
        return 0.5
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return -odds / (-odds + 100)

# -------------------------
# Build recommendations
# -------------------------
recommendations = []
for idx, row in df.iterrows():
    edges = {}
    edges["ML Home"] = 0.5 - odds_to_prob(row["ml_home"])
    edges["ML Away"] = 0.5 - odds_to_prob(row["ml_away"])
    edges["Spread Home"] = (0 - (row["spread_home"] or 0))  # simple: home edge = -market spread
    edges["Spread Away"] = (0 - (row["spread_away"] or 0))  # simple: away edge
    # O/U edge: compare league average total vs market
    total_market = row["total_over"] or row["total_under"] or league_avg_total
    edges["Over"] = league_avg_total - total_market
    edges["Under"] = total_market - league_avg_total

    best_bet = max(edges, key=edges.get)
    best_edge = edges[best_bet]
    stake = bankroll * fractional_kelly * max(0, best_edge)

    # selection and opponent
    if best_bet.startswith("ML"):
        selection = row["home"] if "Home" in best_bet else row["away"]
        opponent = row["away"] if "Home" in best_bet else row["home"]
        bet_type = "Moneyline"
    elif best_bet.startswith("Spread"):
        selection = row["home"] + " - spread" if "Home" in best_bet else row["away"] + " - spread"
        opponent = row["away"] if "Home" in best_bet else row["home"]
        bet_type = "Spread"
    else:
        selection = best_bet  # Over/Under
        opponent = f"{row['away']} @ {row['home']}"
        bet_type = "Totals"

    edge_pct = best_edge * 100
    if edge_pct >= min_edge_pct:
        recommendations.append({
            "Matchup": f"{row['away']} @ {row['home']}",
            "Game Time": row["game_time"],
            "Bet Type": bet_type,
            "Selection": selection,
            "Opponent": opponent,
            "Edge %": round(edge_pct, 2),
            "Stake $": round(stake,2)
        })

# -------------------------
# Display tables
# -------------------------
st.subheader("All Games & Odds")
st.dataframe(df)

st.subheader("Recommended Bets (sorted by Edge %)")
if recommendations:
    rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
    st.dataframe(rec_df)
else:
    st.write("No bets meet the minimum edge threshold.")

st.success("App loaded successfully!")