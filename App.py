import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import kagglehub
import zipfile
import os

st.title("NFL Betting App — Live Odds & Elo Recommendations")

# --- Sidebar Settings ---
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
base_elo = st.sidebar.number_input("Base Elo", 1000, 2000, 1500)
k_factor = st.sidebar.number_input("K-Factor", 1, 50, 20)

# --- Load Historical NFL Scores from Kaggle ---
st.info("Downloading historical NFL scores...")
dataset_path = kagglehub.dataset_download("flynn28/1926-2024-nfl-scores")
zip_path = os.path.join(dataset_path, os.listdir(dataset_path)[0])

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall("historical_data")

csv_files = [f for f in os.listdir("historical_data") if f.endswith(".csv")]
historical_games = pd.read_csv(os.path.join("historical_data", csv_files[0]))

# Keep only necessary columns
historical_games = historical_games[['home_team', 'away_team', 'home_score', 'away_score']].dropna()

# --- Calculate Elo Ratings ---
elo_ratings = {}
for idx, row in historical_games.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    home_score = row["home_score"]
    away_score = row["away_score"]

    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)

    expected_home = 1 / (1 + 10 ** ((away_elo - home_elo)/400))
    score_home = 1 if home_score > away_score else 0 if home_score < away_score else 0.5
    score_away = 1 - score_home

    home_elo += k_factor * (score_home - expected_home)
    away_elo += k_factor * (score_away - (1 - expected_home))

    elo_ratings[home] = home_elo
    elo_ratings[away] = away_elo

st.success("Elo ratings calculated from historical data.")

# --- Fetch Upcoming NFL Odds ---
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT = "americanfootball_nfl"

st.info("Fetching upcoming NFL games and odds...")

response = requests.get(
    f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds",
    params={"apiKey": API_KEY, "regions": "us", "markets": "spreads,totals,headtohead"}
)

if response.status_code != 200:
    st.error(f"Error fetching odds: {response.status_code}")
    st.stop()

data = response.json()

# --- Convert API JSON to DataFrame ---
games = []
for game in data:
    home = game['home_team']
    away = game['away_team']
    game_time = datetime.fromisoformat(game['commence_time'].replace("Z",""))
    moneyline_home = None
    moneyline_away = None
    spread_home = None
    spread_away = None
    total_points = None

    for market in game['bookmakers'][0]['markets']:
        if market['key'] == "spreads":
            spread_home = market['outcomes'][0]['point']
            spread_away = market['outcomes'][1]['point']
        elif market['key'] == "totals":
            total_points = market['outcomes'][0]['point']
        elif market['key'] == "h2h":
            moneyline_home = market['outcomes'][0]['price']
            moneyline_away = market['outcomes'][1]['price']

    games.append({
        "home_team": home,
        "away_team": away,
        "game_time": game_time,
        "moneyline_home": moneyline_home,
        "moneyline_away": moneyline_away,
        "spread_home": spread_home,
        "spread_away": spread_away,
        "total_points": total_points
    })

upcoming_games = pd.DataFrame(games)

# --- Show All Upcoming Games ---
st.subheader("All Upcoming Games")
st.dataframe(upcoming_games)

# --- Calculate Recommendations ---
recommendations = []
for idx, row in upcoming_games.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)
    predicted_margin = home_elo - away_elo

    # --- Edge Calculations ---
    def ml_to_prob(ml):
        if ml > 0:
            return 100 / (ml + 100)
        else:
            return -ml / (-ml + 100)

    edge_home_ml = ml_to_prob(row["moneyline_home"]) - 0.5 if row["moneyline_home"] else 0
    edge_away_ml = ml_to_prob(row["moneyline_away"]) - 0.5 if row["moneyline_away"] else 0
    edge_home_spread = predicted_margin - row["spread_home"] if row["spread_home"] else 0
    edge_away_spread = -predicted_margin - row["spread_away"] if row["spread_away"] else 0
    edge_over = predicted_margin - row["total_points"]/2 if row["total_points"] else 0
    edge_under = row["total_points"]/2 - predicted_margin if row["total_points"] else 0

    edges = {
        "ML Home": edge_home_ml,
        "ML Away": edge_away_ml,
        "Spread Home": edge_home_spread,
        "Spread Away": edge_away_spread,
        "Over": edge_over,
        "Under": edge_under
    }

    best_bet_type = max(edges, key=edges.get)
    best_edge = edges[best_bet_type]
    stake = bankroll * fractional_kelly * max(0,best_edge)

    # --- Selection & Opponent ---
    if "Home" in best_bet_type:
        selection = home
        opponent = away
        display_bet = best_bet_type.replace("Home","")
    elif "Away" in best_bet_type:
        selection = away
        opponent = home
        display_bet = best_bet_type.replace("Away","")
    elif best_bet_type in ["Over","Under"]:
        selection = "Total Points"
        opponent = f"{away} @ {home}"
        display_bet = best_bet_type

    recommendations.append({
        "Matchup": f"{away} @ {home}",
        "Selection": selection,
        "Opponent": opponent,
        "Best Bet": display_bet,
        "Edge %": round(best_edge*100,2),
        "Stake $": round(stake,2)
    })

# --- Display Recommendations ---
st.subheader("Recommended Bets")
rec_df = pd.DataFrame(recommendations)
st.dataframe(rec_df)

# --- Log Bets ---
log_file = "bets_log.csv"
try:
    existing_log = pd.read_csv(log_file)
    updated_log = pd.concat([existing_log, rec_df])
except FileNotFoundError:
    updated_log = rec_df

updated_log.to_csv(log_file, index=False)
st.success(f"{len(rec_df)} bets logged to {log_file}")