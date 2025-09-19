import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# -------------------
# CONFIG
# -------------------
API_KEY = "YOUR_API_KEY_HERE"
SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}
REGIONS = "us"
MARKETS = ["h2h", "spreads", "totals"]

# -------------------
# APP TITLE
# -------------------
st.title("Sports Betting Assistant 2.1")
st.markdown("Pulls NFL, NCAA, and MLB odds and gives recommended bets automatically.")

# -------------------
# BANKROLL SETTINGS
# -------------------
st.sidebar.header("Settings")
bankroll = st.sidebar.number_input("Your Bankroll ($)", min_value=10, value=1000, step=50)
unit_size = bankroll * 0.02  # 2% of bankroll per bet

# -------------------
# FETCH ODDS FUNCTION
# -------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "oddsFormat": "decimal"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except:
        return []

# -------------------
# RECOMMEND BET FUNCTION
# -------------------
def recommend_bets(games):
    recs = []
    for game in games:
        try:
            home = game["home_team"]
            away = game["away_team"]
            commence = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
            
            markets = {m['key']: m for m in game.get("bookmakers", [])[0].get("markets", [])}
            moneyline = markets.get("h2h", {}).get("outcomes", [])
            spread = markets.get("spreads", {}).get("outcomes", [])
            total = markets.get("totals", {}).get("outcomes", [])

            # Simple rule: Favor home team if odds close, otherwise dog if heavy value
            if moneyline:
                best_team = min(moneyline, key=lambda x: x["price"])["name"]
                recs.append({
                    "Game": f"{away} @ {home}",
                    "Kickoff": commence,
                    "Pick": best_team,
                    "Market": "Moneyline",
                    "Odds": min(moneyline, key=lambda x: x["price"])["price"]
                })

            if spread:
                best_spread = min(spread, key=lambda x: abs(x["point"]))
                recs.append({
                    "Game": f"{away} @ {home}",
                    "Kickoff": commence,
                    "Pick": best_spread["name"],
                    "Market": "Spread",
                    "Odds": best_spread["price"]
                })

            if total:
                best_total = min(total, key=lambda x: abs(x["point"]))
                recs.append({
                    "Game": f"{away} @ {home}",
                    "Kickoff": commence,
                    "Pick": best_total["name"],
                    "Market": "Over/Under",
                    "Odds": best_total["price"]
                })

        except:
            pass
    return pd.DataFrame(recs)

# -------------------
# DISPLAY RESULTS
# -------------------
for league, sport_key in SPORTS.items():
    st.header(f"{league} Upcoming Games")
    games = fetch_odds(sport_key)
    if not games:
        st.warning(f"No data for {league} right now.")
        continue
    bets_df = recommend_bets(games)
    if bets_df.empty:
        st.warning(f"No bets found for {league}.")
    else:
        st.dataframe(bets_df.sort_values("Kickoff"))
        st.success(f"Recommended unit size: ${unit_size:.2f}")