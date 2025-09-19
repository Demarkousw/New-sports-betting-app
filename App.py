import streamlit as st
import pandas as pd
import requests

st.title("Step 1: Odds Test")

# --- Sidebar ---
sport = st.sidebar.selectbox("Select Sport", ["NFL", "NCAAF"])
odds_api_key = st.secrets["THE_ODDS_API_KEY"]

# --- Fetch Odds ---
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
        rows.append({
            "Home": home,
            "Away": away,
            "Time": game_time
        })
    return pd.DataFrame(rows)

odds_df = fetch_odds(sport)

if odds_df.empty:
    st.warning("No odds data fetched.")
else:
    st.subheader("Upcoming Games")
    st.dataframe(odds_df)