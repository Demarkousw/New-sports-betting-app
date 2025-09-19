import streamlit as st
import pandas as pd
from datetime import datetime
import requests

# --- Sidebar Settings ---
st.sidebar.title("Settings")
sport = st.sidebar.selectbox("Select Sport", ["NFL", "NCAAF"])
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.1, 1.0, 0.5)

# API keys stored in Streamlit secrets
odds_api_key = st.secrets["THE_ODDS_API_KEY"]

# --- Fetch Upcoming Odds from The Odds API ---
@st.cache_data(ttl=3600)
def fetch_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport.lower()}/odds/?regions=us&markets=spreads,totals,ml&apiKey={odds_api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        st.error(f"Failed to fetch odds: {response.status_code}")
        return pd.DataFrame()
    data = response.json()
    
    # Parse API data into DataFrame
    rows = []
    for game in data:
        home = game["home_team"]
        away = game["away_team"]
        game_time = pd.to_datetime(game["commence_time"])
        venue = game.get("venue", "")
        odds = {m["key"]: m for m in game["bookmakers"][0]["markets"]}
        
        rows.append({
            "home_team": home,
            "away_team": away,
            "game_time": game_time,
            "venue": venue,
            "moneyline_home": odds.get("moneyline", {}).get("outcomes", [{}])[0].get("price", 0),
            "moneyline_away": odds.get("moneyline", {}).get("outcomes", [{}])[1].get("price", 0),
            "spread_home": odds.get("spreads", {}).get("outcomes", [{}])[0].get("point", 0),
            "spread_away": odds.get("spreads", {}).get("outcomes", [{}])[1].get("point", 0),
            "total_points": odds.get("totals", {}).get("outcomes", [{}])[0].get("total", 0)
        })
    return pd.DataFrame(rows)

odds_df = fetch_odds(sport)
if odds_df.empty:
    st.stop()

# --- Add Week and Matchup ---
odds_df["Week"] = odds_df["game_time"].dt.isocalendar().week
odds_df["Matchup"] = odds_df["away_team"] + " @ " + odds_df["home_team"]

# --- Sidebar Week Filter ---
selected_week = st.sidebar.selectbox("Select Week", sorted(odds_df["Week"].unique()))
odds_df = odds_df[odds_df["Week"] == selected_week]

# --- Calculate Recommendations ---
recommendations = []
for idx, row in odds_df.iterrows():
    home = row["home_team"]
    away = row["away_team"]
    
    # --- Simplified Edge Calculation ---
    # Convert moneyline to implied probability
    def moneyline_to_prob(ml):
        if ml > 0:
            return 100 / (ml + 100)
        else:
            return -ml / (-ml + 100)
    
    edge_home_ml = moneyline_to_prob(row["moneyline_home"]) - 0.5
    edge_away_ml = moneyline_to_prob(row["moneyline_away"]) - 0.5
    
    edge_home_spread = 0.05  # Placeholder, replace with real model
    edge_away_spread = 0.05
    edge_over = 0.05
    edge_under = 0.05
    
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
    
    # Determine Selection & Opponent
    if "Home" in best_bet_type:
        selection_team = home
        opponent = away
        display_bet = best_bet_type.replace("Home","")
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
        "Time": row["game_time"].strftime("%Y-%m-%d %H:%M"),
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