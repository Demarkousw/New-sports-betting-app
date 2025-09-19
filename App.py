import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.title("NFL Betting App — Best Bets & Edge Calculator")

# --- Sidebar Settings ---
st.sidebar.header("Betting Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=100, value=1000, step=100)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
min_edge = st.sidebar.slider("Minimum Edge % to Show", 0.0, 50.0, 5.0)

# --- API Setup ---
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT = "americanfootball_nfl"
MARKETS = "h2h,spreads,totals"

# --- Function to Fetch Odds ---
def fetch_odds():
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
        params = {"apiKey": API_KEY, "regions": "us", "markets": MARKETS}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error fetching odds: {e}")
        return []

# --- Fetch Odds ---
st.info("Fetching NFL odds...")
data = fetch_odds()
if not data:
    st.error("No odds available right now. Try again later.")
    st.stop()

# --- Convert API Data to DataFrame ---
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

# --- Figure Out Week Number ---
if not df.empty:
    start_date = min(df["game_time"])
    week_num = ((max(df["game_time"]) - start_date).days // 7) + 1
    st.subheader(f"Current NFL Week: {week_num}")

# --- Convert Odds to Probabilities ---
def odds_to_prob(odds):
    if odds is None:
        return 0
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)

# --- Calculate Edges & Recommendations ---
recommendations = []
for idx, row in df.iterrows():
    edges = {
        "ML Home": 0.5 - odds_to_prob(row["ml_home"]),
        "ML Away": 0.5 - odds_to_prob(row["ml_away"]),
        "Spread Home": 0.5 - odds_to_prob(row["spread_home"]),
        "Spread Away": 0.5 - odds_to_prob(row["spread_away"]),
        "Over": 0.5 - odds_to_prob(row["over"]),
        "Under": 0.5 - odds_to_prob(row["under"]),
    }

    best_bet = max(edges, key=edges.get)
    best_edge = edges[best_bet]
    stake = bankroll * fractional_kelly * max(0, best_edge)

    if "Home" in best_bet:
        selection = row["home"]
        opponent = row["away"]
    elif "Away" in best_bet:
        selection = row["away"]
        opponent = row["home"]
    else:
        selection = best_bet
        opponent = f"{row['away']} @ {row['home']}"

    if best_edge * 100 >= min_edge:
        recommendations.append({
            "Matchup": f"{row['away']} @ {row['home']}",
            "Best Bet": best_bet,
            "Selection": selection,
            "Opponent": opponent,
            "Edge %": round(best_edge*100, 2),
            "Stake $": round(stake, 2)
        })

# --- Show All Odds ---
st.subheader("All Games & Odds")
st.dataframe(df)

# --- Show Recommendations ---
st.subheader("Recommended Bets (Sorted by Edge)")
rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
st.dataframe(rec_df)