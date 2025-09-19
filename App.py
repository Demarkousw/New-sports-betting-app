import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.title("Live Sports Betting App — NFL & College Football")

# --- Sidebar Settings ---
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)
base_elo = st.sidebar.number_input("Base Elo", 1000, 2000, 1500)
k_factor = st.sidebar.number_input("K-Factor", 1, 50, 20)
sport_choice = st.sidebar.selectbox("Select Sport", ["NFL", "College Football"])

# --- Base Elo Ratings ---
# Expand as needed for both NFL and College teams
if sport_choice == "NFL":
    teams = ["Bills","Jets","Dolphins","Patriots","Cowboys","Giants",
             "Packers","Bears","Ravens","Steelers","Seahawks","49ers",
             "Falcons","Saints","Broncos","Raiders"]
else:  # College Football
    teams = ["Alabama","Georgia","Ohio State","Michigan","Texas","LSU",
             "Oklahoma","Florida","Penn State","Notre Dame","Clemson","Iowa"]

elo_ratings = {team: base_elo for team in teams}

# --- Fetch Upcoming Odds ---
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT_API_MAP = {"NFL":"americanfootball_nfl", "College Football":"americanfootball_ncaaf"}
SPORT = SPORT_API_MAP[sport_choice]

st.info(f"Fetching upcoming {sport_choice} games and odds...")

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

    if game['bookmakers']:
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

# --- Show All Games ---
st.subheader(f"All Upcoming {sport_choice} Games")
st.dataframe(upcoming_games)

# --- Calculate Recommendations ---
recommendations = []
for idx, row in upcoming_games.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    home_elo = elo_ratings.get(home, base_elo)
    away_elo = elo_ratings.get(away, base_elo)
    predicted_margin = home_elo - away_elo

    def ml_to_prob(ml):
        if ml is None:
            return 0
        if ml > 0:
            return 100 / (ml + 100)
        else:
            return -ml / (-ml + 100)

    edge_home_ml = ml_to_prob(row["moneyline_home"]) - 0.5
    edge_away_ml = ml_to_prob(row["moneyline_away"]) - 0.5
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