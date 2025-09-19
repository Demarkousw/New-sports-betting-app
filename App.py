import streamlit as st
import pandas as pd
from datetime import datetime
import requests

# --- Sidebar Settings ---
st.sidebar.title("Settings")
sport = st.sidebar.selectbox("Select Sport", ["NFL", "NCAAF"])
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
base_elo = st.sidebar.number_input("Base Elo", 1000, 2000, 1500)
k_factor = st.sidebar.number_input("K-Factor", 1, 50, 20)

# API keys
odds_api_key = st.secrets["THE_ODDS_API_KEY"]
weather_api_key = st.secrets.get("WEATHER_API_KEY", None)

# --- Load Historical Games CSV ---
@st.cache_data(ttl=3600)
def load_historical_games():
    return pd.read_csv("historical_games.csv")

historical_games = load_historical_games()

# --- Initialize Elo Ratings ---
elo_ratings = {}
for idx, row in historical_games.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    home_score = row["home_score"]
    away_score = row["away_score"]

    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)

    # Simple Elo update
    expected_home = 1 / (1 + 10 ** ((away_elo - home_elo)/400))
    expected_away = 1 - expected_home
    if home_score > away_score:
        score_home = 1
    elif home_score < away_score:
        score_home = 0
    else:
        score_home = 0.5
    score_away = 1 - score_home

    home_elo += k_factor * (score_home - expected_home)
    away_elo += k_factor * (score_away - expected_away)

    elo_ratings[home] = home_elo
    elo_ratings[away] = away_elo

# --- Fetch Upcoming Odds from Odds API ---
@st.cache_data(ttl=3600)
def fetch_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport.lower()}/odds/?regions=us&markets=spreads,totals,ml&apiKey={odds_api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        st.error(f"Failed to fetch odds: {response.status_code}")
        return pd.DataFrame()
    data = response.json()
    
    rows = []
    for game in data:
        home = game["home_team"]
        away = game["away_team"]
        game_time = pd.to_datetime(game["commence_time"])
        venue = game.get("venue", "")
        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue
        markets = {m["key"]: m for m in bookmakers[0]["markets"]}
        moneyline = markets.get("moneyline", {}).get("outcomes", [])
        spreads = markets.get("spreads", {}).get("outcomes", [])
        totals = markets.get("totals", {}).get("outcomes", [])

        rows.append({
            "home_team": home,
            "away_team": away,
            "game_time": game_time,
            "venue": venue,
            "moneyline_home": moneyline[0]["price"] if moneyline else 0,
            "moneyline_away": moneyline[1]["price"] if len(moneyline) > 1 else 0,
            "spread_home": spreads[0]["point"] if spreads else 0,
            "spread_away": spreads[1]["point"] if len(spreads) > 1 else 0,
            "total_points": totals[0]["total"] if totals else 0
        })
    return pd.DataFrame(rows)

odds_df = fetch_odds(sport)
if odds_df.empty:
    st.stop()

# --- Add Week & Matchup ---
odds_df["Week"] = odds_df["game_time"].dt.isocalendar().week
odds_df["Matchup"] = odds_df["away_team"] + " @ " + odds_df["home_team"]

# --- Sidebar Week Filter ---
selected_week = st.sidebar.selectbox("Select Week", sorted(odds_df["Week"].unique()))
odds_df = odds_df[odds_df["Week"] == selected_week]

# --- Weather & Injuries ---
def fetch_weather(venue):
    if not weather_api_key:
        return {"temp": 70, "wind": 5, "rain": 0}
    # Call weather API
    return {"temp": 70, "wind": 5, "rain": 0}

def fetch_injuries(team):
    # Return list of injured key players
    return []

# --- Calculate Recommendations ---
recommendations = []
for idx, row in odds_df.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    game_time = row["game_time"]

    weather = fetch_weather(row.get("venue", ""))
    home_injuries = fetch_injuries(home)
    away_injuries = fetch_injuries(away)

    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)

    # Predicted margin
    predicted_margin = home_elo - away_elo

    # Adjust for injuries
    if home_injuries: predicted_margin -= 3
    if away_injuries: predicted_margin += 3

    # Adjust for weather
    if weather["rain"] > 0 or weather["wind"] > 20:
        predicted_margin *= 0.9

    # --- Calculate Edge ---
    def ml_to_prob(ml):
        if ml > 0:
            return 100 / (ml + 100)
        else:
            return -ml / (-ml + 100)

    edge_home_ml = ml_to_prob(row["moneyline_home"]) - 0.5
    edge_away_ml = ml_to_prob(row["moneyline_away"]) - 0.5
    edge_home_spread = predicted_margin - row["spread_home"]
    edge_away_spread = -predicted_margin - row["spread_away"]
    edge_over = (predicted_margin + 42)/2 - row["total_points"]  # example total
    edge_under = row["total_points"] - (predicted_margin + 42)/2

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
        selection_team = home
        opponent = away
        display_bet = best_bet_type.replace("Home","")
    elif "Away" in best_bet_type:
        selection_team = away
        opponent = home
        display_bet = best_bet_type.replace("Away","")
    elif best_bet_type in ["Over","Under"]:
        selection_team = "Total Points"
        opponent = f"{away} @ {home}"
        display_bet = best_bet_type

    recommendations.append({
        "Week": row["Week"],
        "Matchup": row["Matchup"],
        "Home": home,
        "Away": away,
        "Time": game_time.strftime("%Y-%m-%d %H:%M"),
        "Selection": selection_team,
        "Opponent": opponent,
        "Best Bet": display_bet,
        "Edge %": round(best_edge*100,2),
        "Stake $": round(stake,2)
    })

# --- Display Recommendations ---
rec_df = pd.DataFrame(recommendations)
st.subheader(f"Recommended Bets — Week {selected_week}")
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