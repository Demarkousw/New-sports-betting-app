import streamlit as st
import pandas as pd
from datetime import datetime
from elo import calculate_elo, update_elo, predict_margin

# --- Sidebar Settings ---
st.sidebar.title("Settings")
sport = st.sidebar.selectbox("Select Sport", ["NFL", "NCAAF"])
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
base_elo = st.sidebar.number_input("Base Elo", 1000, 2000, 1500)
k_factor = st.sidebar.number_input("K-Factor", 1, 50, 20)

# API keys stored in Streamlit secrets
odds_api_key = st.secrets["THE_ODDS_API_KEY"]
weather_api_key = st.secrets.get("WEATHER_API_KEY", None)

# --- Load Historical Games CSV ---
@st.cache_data(ttl=3600)
def load_historical_games():
    # CSV should have: date, home_team, away_team, home_score, away_score
    return pd.read_csv("historical_games.csv")

historical_games = load_historical_games()

# --- Initialize Elo Ratings ---
elo_ratings = {}
for idx, row in historical_games.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    home_score = row["home_score"]
    away_score = row["away_score"]
    
    home_elo, away_elo = elo_ratings.get(home, base_elo), elo_ratings.get(away, base_elo)
    home_elo, away_elo = update_elo(home_elo, away_elo, home_score, away_score, k_factor)
    
    elo_ratings[home] = home_elo
    elo_ratings[away] = away_elo

# --- Fetch Upcoming Odds ---
@st.cache_data(ttl=3600)
def fetch_odds(sport):
    # Replace with your Odds API call
    # Must return columns: home_team, away_team, game_time, moneyline_home, moneyline_away,
    # spread_home, spread_away, total_points, venue
    return pd.DataFrame()  # placeholder

odds_df = fetch_odds(sport)

# --- Add Week and Matchup ---
odds_df["game_time"] = pd.to_datetime(odds_df["game_time"])
odds_df["Week"] = odds_df["game_time"].dt.isocalendar().week
odds_df["Matchup"] = odds_df["away_team"] + " @ " + odds_df["home_team"]

# --- Sidebar Week Filter ---
selected_week = st.sidebar.selectbox("Select Week", sorted(odds_df["Week"].unique()))
odds_df = odds_df[odds_df["Week"] == selected_week]

# --- Weather Function ---
def fetch_weather(venue):
    if not weather_api_key:
        return None
    # Call a weather API (OpenWeatherMap, etc.)
    return {"temp": 70, "wind": 5, "rain": 0}

# --- Injury Function ---
def fetch_injuries(team):
    # Return list of injured key players
    return []

# --- Calculate Recommendations ---
recommendations = []

for idx, row in odds_df.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    game_time = row["game_time"]
    
    # Weather and injuries
    weather = fetch_weather(row.get("venue", ""))
    home_injuries = fetch_injuries(home)
    away_injuries = fetch_injuries(away)
    
    # Elo prediction from historical ratings
    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)
    predicted_margin = predict_margin(home_elo, away_elo)
    
    # Adjust for injuries
    if home_injuries: predicted_margin -= 3
    if away_injuries: predicted_margin += 3
    # Adjust for weather
    if weather and (weather["rain"]>0 or weather["wind"]>20):
        predicted_margin *= 0.9
    
    # --- Moneyline Edge ---
    prob_home_win = 1 / (1 + 10 ** ((away_elo - home_elo)/400))
    prob_away_win = 1 - prob_home_win
    implied_home = 0.5  # placeholder conversion from moneyline
    implied_away = 0.5
    edge_home_ml = prob_home_win - implied_home
    edge_away_ml = prob_away_win - implied_away
    
    # --- Spread Edge ---
    edge_home_spread = predicted_margin - row.get("spread_home",0)
    edge_away_spread = -predicted_margin - row.get("spread_away",0)
    
    # --- Over/Under Edge ---
    predicted_total = home_elo/10 + away_elo/10
    over_under_edge = predicted_total - row.get("total_points",0)
    
    # --- Pick Best Bet ---
    edges = {
        "ML Home": edge_home_ml,
        "ML Away": edge_away_ml,
        "Spread Home": edge_home_spread,
        "Spread Away": edge_away_spread,
        "Over": over_under_edge,
        "Under": -over_under_edge
    }
    best_bet_type = max(edges, key=edges.get)
    best_edge = edges[best_bet_type]
    stake = bankroll * fractional_kelly * max(0,best_edge)
    
    # --- Determine Selection & Opponent ---
    if "Home" in best_bet_type:
        selection_team = home
        opponent = away
        display_bet = best_bet_type.replace("Home","")  # ML or Spread
    elif "Away" in best_bet_type:
        selection_team = away
        opponent = home
        display_bet = best_bet_type.replace("Away","")
    elif best_bet_type in ["Over", "Under"]:
        selection_team = "Total Points"
        opponent = f"{away} @ {home}"
        display_bet = best_bet_type
    
    recommendations.append({
        "Week": row["Week"],
        "Matchup": row["Matchup"],
        "Home": home,
        "Away": away,
        "Time": game_time.strftime("%Y-%m-%d %H:%M"),
        "Weather": weather,
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