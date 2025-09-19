import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
import math
import itertools
import random

# -------------------
# CONFIG
# -------------------
API_KEY_ODDS = "YOUR_ODDS_API_KEY"
API_KEY_WEATHER = "YOUR_WEATHER_API_KEY"

SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA Football": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}

REGIONS = "us"
MARKETS = ["h2h", "spreads", "totals"]

BETS_LOG = "bets_log.csv"
BETS_COLS = [
    "record_id","timestamp","sport","week","home_team","away_team","matchup",
    "game_time","bet_type","selection","opponent","edge_pct","stake",
    "predicted_margin","point_spread","weather","status"
]

# -------------------
# UTILITIES
# -------------------
def load_or_create_csv(path, cols):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            for c in cols:
                if c not in df.columns:
                    df[c] = pd.NA
            return df[cols]
        except:
            os.rename(path, path + ".bak")
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

bets_df = load_or_create_csv(BETS_LOG, BETS_COLS)

# -------------------
# STREAMLIT HEADER
# -------------------
st.set_page_config(layout="wide", page_title="Sports Betting Assistant")
st.title("Sports Betting Assistant v2.5 — Full Automation, Cross-Sport & Fantasy")

# -------------------
# SIDEBAR SETTINGS
# -------------------
st.sidebar.header("Settings")
sport_choice = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
bankroll = st.sidebar.number_input("Your Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly Fraction", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect(
    "Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"]
)
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]
use_weather = st.sidebar.checkbox("Adjust predictions for weather", value=True)

# -------------------
# FUNCTIONS
# -------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": API_KEY_ODDS, "regions": REGIONS, "markets": ",".join(MARKETS), "oddsFormat": "decimal"}
    try:
        r = requests.get(url, params=params)
        if r.status_code == 200:
            return r.json()
        return []
    except:
        return []

def fetch_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY_WEATHER}&units=imperial"
        r = requests.get(url)
        data = r.json()
        desc = data['weather'][0]['description'].title()
        temp = data['main']['temp']
        wind = data['wind']['speed']
        return f"{desc} {temp}°F, Wind {wind} mph", temp, wind, desc.lower()
    except:
        return "N/A", None, None, None

def odds_to_prob(odds):
    try:
        o = float(odds)
        if o > 1: return 1 / o
        return -o / (1 - o)
    except:
        return 0.5

def calc_margin(p_home, p_away):
    p_home = max(min(p_home, 0.9999), 0.0001)
    p_away = max(min(p_away, 0.9999), 0.0001)
    return math.log(p_home/(1-p_home)) - math.log(p_away/(1-p_away))

# -------------------
# BUILD RECOMMENDATIONS
# -------------------
def build_recommendations(games, sport_choice):
    recs = []
    for i, game in enumerate(games):
        try:
            home = game.get("home_team")
            away = game.get("away_team")
            week = game.get("week", None)
            game_time = datetime.fromisoformat(game["commence_time"].replace("Z","+00:00"))

            # Placeholder coordinates (replace with real stadium coords)
            lat, lon = 40.0, -75.0
            weather_str, temp, wind, desc = fetch_weather(lat, lon)

            bookmakers = game.get("bookmakers", [])
            markets = {}
            if bookmakers:
                for m in bookmakers[0].get("markets", []):
                    markets[m["key"]] = m.get("outcomes", [])

            p_home = odds_to_prob(markets.get("h2h",[{"price":2}])[0]["price"]) if markets.get("h2h") else 0.5
            p_away = odds_to_prob(markets.get("h2h",[{"price":2}])[1]["price"]) if markets.get("h2h") else 0.5
            predicted_margin = calc_margin(p_home, p_away)

            edges = {}
            if markets.get("h2h"):
                edges["ML Home"] = p_home - 0.5
                edges["ML Away"] = p_away - 0.5
            if markets.get("spreads"):
                edges["Spread Home"] = predicted_margin
                edges["Spread Away"] = -predicted_margin
            if markets.get("totals"):
                edges["Over"] = 0.5
                edges["Under"] = 0.5

            point_spread = None
            if markets.get("spreads"):
                for outcome in markets["spreads"]:
                    if "point" in outcome:
                        point_spread = outcome["point"]

            # Adjust for weather
            if use_weather:
                if wind and wind > 15:
                    if "Over" in edges: edges["Over"] -= 0.1
                    if "Under" in edges: edges["Under"] += 0.1
                    edges["Spread Home"] *= 0.9
                    edges["Spread Away"] *= 0.9
                if "rain" in (desc or "") or "snow" in (desc or ""):
                    edges = {k: v*0.85 for k,v in edges.items()}
                if temp and temp > 95:
                    edges = {k: v*0.95 for k,v in edges.items()}

            if edges:
                best_key = max(edges, key=lambda x: edges[x])
                edge_pct = edges[best_key]*100

                if best_key.startswith("ML"):
                    bet_type = "Moneyline"
                    selection = home if "Home" in best_key else away
                    opponent = away if "Home" in best_key else home
                elif best_key.startswith("Spread"):
                    bet_type = "Spread"
                    selection = home if "Home" in best_key else away
                    opponent = away if "Home" in best_key else home
                else:
                    bet_type = "Totals"
                    selection = best_key
                    opponent = f"{away} @ {home}"

                if bet_type in bet_type_filter and edge_pct >= min_edge_pct:
                    stake = bankroll * fractional_kelly * max(0, edges[best_key])
                    recs.append({
                        "record_id": f"{sport_choice}_{i}_{int(datetime.utcnow().timestamp())}",
                        "timestamp": datetime.utcnow(),
                        "sport": sport_choice,
                        "week": week,
                        "home_team": home,
                        "away_team": away,
                        "matchup": f"{away} @ {home}",
                        "game_time": game_time,
                        "bet_type": bet_type,
                        "selection": selection,
                        "opponent": opponent,
                        "edge_pct": round(edge_pct,2),
                        "stake": round(stake,2),
                        "predicted_margin": round(predicted_margin,2),
                        "point_spread": point_spread,
                        "weather": weather_str,
                        "status": "PENDING"
                    })
        except:
            continue
    return pd.DataFrame(recs)

# -------------------
# FETCH ODDS & BUILD RECOMMENDATIONS
# -------------------
all_games = []
for s in SPORTS.keys():
    games = fetch_odds(SPORTS[s])
    if games:
        rec_df = build_recommendations(games, s)
        if not rec_df.empty:
            all_games.extend(rec_df.to_dict("records"))

if all_games:
    new_df = pd.DataFrame(all_games)
    bets_df = pd.concat([bets_df, new_df]).drop_duplicates(subset=["record_id"], keep="first").reset_index(drop=True)

# -------------------
# DISPLAY ALL-TIME BETS
# -------------------
st.header("All-Time Bets Overview")
def style_row(row):
    edge = row["edge_pct"]
    status = row["status"]
    if status=="WON": return ["background-color: #ADD8E6"]*len(row)
    if status=="LOST": return ["background-color: #D3D3D3"]*len(row)
    if edge >= 5: return ["background-color: #9AFF99"]*len(row)
    if edge >= 2: return ["background-color: #FFFF99"]*len(row)
    return ["background-color: #FF9999"]*len(row)

if not bets_df.empty:
    st.dataframe(bets_df.style.apply(style_row, axis=1), use_container_width=True)