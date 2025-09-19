import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.title("Football Betting App — NFL Value Bets with Custom Odds")

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
    except requests.HTTPError:
        return []

# --- Fetch Odds ---
st.info("Fetching NFL odds...")

data = fetch_odds("h2h")  # start with h2h (moneyline)
if not data:
    st.error("No odds available. Try again later.")
    st.stop()

# --- Convert API data into DataFrame ---
games = []
for game in data:
    home = game.get('home_team')
    away = game.get('away_team')
    game_time = datetime.fromisoformat(game['commence_time'].replace("Z",""))

    ml_home = ml_away = None
    if game.get('bookmakers'):
        markets = game['bookmakers'][0].get('markets', [])
        for m in markets:
            if m['key'] == "h2h":
                ml_home = m['outcomes'][0]['price']
                ml_away = m['outcomes'][1]['price']

    games.append({
        "home": home, "away": away, "game_time": game_time,
        "ml_home": ml_home, "ml_away": ml_away
    })

df = pd.DataFrame(games)

# --- Custom Odds Input ---
st.subheader("Add Your Own Odds for Each Team")
custom_odds = {}
for idx, row in df.iterrows():
    matchup = f"{row['away']} @ {row['home']}"
    my_home = st.number_input(f"My Odds for {row['home']} vs {row['away']} (e.g., -110)", value=0, key=f"home_{idx}")
    my_away = st.number_input(f"My Odds for {row['away']} vs {row['home']} (e.g., -110)", value=0, key=f"away_{idx}")
    custom_odds[matchup] = {"home": my_home, "away": my_away}

# --- Edge Calculation ---
def calc_edge(my_odds, market_odds):
    """Positive edge = my line better than sportsbook line"""
    if my_odds == 0 or market_odds is None:
        return 0
    def to_prob(odds):
        return 100/(odds+100) if odds>0 else -odds/(-odds+100)
    my_prob = to_prob(my_odds)
    market_prob = to_prob(market_odds)
    return market_prob - my_prob  # positive = value

# --- Generate Recommendations ---
recommendations = []
for idx, row in df.iterrows():
    matchup = f"{row['away']} @ {row['home']}"
    my_home = custom_odds[matchup]["home"]
    my_away = custom_odds[matchup]["away"]

    edge_home = calc_edge(my_home, row["ml_home"])
    edge_away = calc_edge(my_away, row["ml_away"])

    if edge_home > edge_away:
        selection = row["home"]
        best_edge = edge_home
        opponent = row["away"]
    else:
        selection = row["away"]
        best_edge = edge_away
        opponent = row["home"]

    stake = bankroll * fractional_kelly * max(0, best_edge)

    recommendations.append({
        "Matchup": matchup,
        "Selection": selection,
        "Opponent": opponent,
        "Edge %": round(best_edge*100, 2),
        "Stake $": round(stake, 2)
    })

# --- Show All Games ---
st.subheader("All Games & Market Odds")
st.dataframe(df)

# --- Show Recommended Bets ---
st.subheader("Recommended Bets (Sorted by Edge)")
rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
st.dataframe(rec_df)