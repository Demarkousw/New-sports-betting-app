import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.title("Football Betting App — NFL Value Bets")

# --- Settings Sidebar ---
st.sidebar.header("Betting Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)

# --- API Setup ---
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT = "americanfootball_nfl"

# --- Function to Fetch Odds Safely ---
def fetch_odds(market):
    try:
        response = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds",
            params={"apiKey": API_KEY, "regions": "us", "markets": market}
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        st.warning(f"Market '{market}' not available: {e}")
        return []

# --- Fetch Odds in Layers ---
st.info("Fetching NFL odds...")

data_h2h = fetch_odds("h2h")
data_spreads = fetch_odds("spreads")
data_totals = fetch_odds("totals")

# Combine data, fallback if needed
data = data_h2h or data_spreads or data_totals
if not data:
    st.error("No odds available. Try again later.")
    st.stop()

# --- Convert API data into DataFrame ---
games = []
for game in data:
    home = game.get('home_team')
    away = game.get('away_team')
    game_time = datetime.fromisoformat(game['commence_time'].replace("Z",""))

    ml_home = ml_away = spread_home = spread_away = total_over = total_under = None

    if game.get('bookmakers'):
        markets = game['bookmakers'][0].get('markets', [])
        for m in markets:
            if m['key'] == "h2h":
                ml_home = m['outcomes'][0]['price']
                ml_away = m['outcomes'][1]['price']
            elif m['key'] == "spreads":
                spread_home = m['outcomes'][0]['point']
                spread_away = m['outcomes'][1]['point']
            elif m['key'] == "totals":
                total_over = m['outcomes'][0]['point']
                total_under = m['outcomes'][1]['point']

    games.append({
        "home": home, "away": away, "game_time": game_time,
        "ml_home": ml_home, "ml_away": ml_away,
        "spread_home": spread_home, "spread_away": spread_away,
        "over": total_over, "under": total_under
    })

df = pd.DataFrame(games)

# --- Simple Edge Calculation ---
def simple_edge(price):
    if price is None:
        return 0
    if price > 0:
        implied = 100 / (price + 100)
    else:
        implied = -price / (-price + 100)
    return 0.5 - implied

# --- Generate Recommendations ---
recommendations = []
for idx, row in df.iterrows():
    edges = {
        "ML Home": simple_edge(row["ml_home"]),
        "ML Away": simple_edge(row["ml_away"]),
        "Over": row["over"] or 0,
        "Under": row["under"] or 0
    }

    best_bet_type = max(edges, key=edges.get)
    best_edge = edges[best_bet_type]
    stake = bankroll * fractional_kelly * max(0, best_edge)

    if "Home" in best_bet_type:
        selection = row["home"]
        opponent = row["away"]
    elif "Away" in best_bet_type:
        selection = row["away"]
        opponent = row["home"]
    else:
        selection = best_bet_type
        opponent = f"{row['away']} @ {row['home']}"

    recommendations.append({
        "Matchup": f"{row['away']} @ {row['home']}",
        "Selection": selection,
        "Opponent": opponent,
        "Recommended Bet": best_bet_type,
        "Edge %": round(best_edge*100, 2),
        "Stake $": round(stake, 2)
    })

# --- Show All Games ---
st.subheader("All Games & Odds")
st.dataframe(df)

# --- Show Recommended Bets ---
st.subheader("Recommended Value Bets (sorted by edge)")
rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
st.dataframe(rec_df)