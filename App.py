import streamlit as st
import pandas as pd
from datetime import datetime

st.title("Full Sports Betting App — Self-Contained Version")

# --- Sidebar Settings ---
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
base_elo = st.sidebar.number_input("Base Elo", 1000, 2000, 1500)
k_factor = st.sidebar.number_input("K-Factor", 1, 50, 20)

# --- Sample Historical Games (for Elo) ---
historical_games = pd.DataFrame([
    {"home_team": "Bills", "away_team": "Dolphins", "home_score": 31, "away_score": 24},
    {"home_team": "Jets", "away_team": "Patriots", "home_score": 17, "away_score": 20},
    {"home_team": "Cowboys", "away_team": "Giants", "home_score": 28, "away_score": 21},
    {"home_team": "Packers", "away_team": "Bears", "home_score": 21, "away_score": 17},
    {"home_team": "Ravens", "away_team": "Steelers", "home_score": 24, "away_score": 20},
    {"home_team": "Seahawks", "away_team": "49ers", "home_score": 27, "away_score": 23},
])

# --- Initialize Elo Ratings ---
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

# --- Full Week of Sample Upcoming Games ---
upcoming_games = pd.DataFrame([
    {"week": 1, "home_team": "Bills", "away_team": "Jets", "game_time": "2025-09-21 13:00",
     "moneyline_home": -150, "moneyline_away": 130, "spread_home": -7, "spread_away": 7, "total_points": 45},
    {"week": 1, "home_team": "Dolphins", "away_team": "Patriots", "game_time": "2025-09-21 16:25",
     "moneyline_home": -120, "moneyline_away": 110, "spread_home": -3, "spread_away": 3, "total_points": 42},
    {"week": 1, "home_team": "Cowboys", "away_team": "Giants", "game_time": "2025-09-21 20:20",
     "moneyline_home": -140, "moneyline_away": 120, "spread_home": -6, "spread_away": 6, "total_points": 44},
    {"week": 1, "home_team": "Packers", "away_team": "Bears", "game_time": "2025-09-22 13:00",
     "moneyline_home": -130, "moneyline_away": 110, "spread_home": -4, "spread_away": 4, "total_points": 41},
    {"week": 1, "home_team": "Ravens", "away_team": "Steelers", "game_time": "2025-09-22 16:25",
     "moneyline_home": -125, "moneyline_away": 105, "spread_home": -3, "spread_away": 3, "total_points": 40},
    {"week": 1, "home_team": "Seahawks", "away_team": "49ers", "game_time": "2025-09-22 20:15",
     "moneyline_home": -135, "moneyline_away": 115, "spread_home": -5, "spread_away": 5, "total_points": 43},
    {"week": 1, "home_team": "Falcons", "away_team": "Saints", "game_time": "2025-09-23 13:00",
     "moneyline_home": -110, "moneyline_away": 100, "spread_home": -2, "spread_away": 2, "total_points": 39},
    {"week": 1, "home_team": "Broncos", "away_team": "Raiders", "game_time": "2025-09-23 16:25",
     "moneyline_home": -145, "moneyline_away": 125, "spread_home": -6, "spread_away": 6, "total_points": 46},
])

upcoming_games["game_time"] = pd.to_datetime(upcoming_games["game_time"])

# --- Week Filter ---
weeks = sorted(upcoming_games["week"].unique())
selected_week = st.sidebar.selectbox("Select Week", weeks)
upcoming_games = upcoming_games[upcoming_games["week"] == selected_week]

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

    edge_home_ml = ml_to_prob(row["moneyline_home"]) - 0.5
    edge_away_ml = ml_to_prob(row["moneyline_away"]) - 0.5
    edge_home_spread = predicted_margin - row["spread_home"]
    edge_away_spread = -predicted_margin - row["spread_away"]
    edge_over = predicted_margin - row["total_points"]/2
    edge_under = row["total_points"]/2 - predicted_margin

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
        "Week": row["week"],
        "Matchup": f"{away} @ {home}",
        "Home": home,
        "Away": away,
        "Time": row["game_time"].strftime("%Y-%m-%d %H:%M"),
        "Selection": selection,
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