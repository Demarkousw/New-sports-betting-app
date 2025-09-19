import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
import itertools
import random
import math

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

BETS_LOG = "bets_log.csv"
BETS_COLS = [
    "record_id","timestamp","sport","home_team","away_team","matchup",
    "game_time","bet_type","selection","opponent","edge_pct","stake","weather","status"
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
st.title("Sports Betting Assistant — Weather-Adjusted")

# -------------------
# SIDEBAR SETTINGS
# -------------------
st.sidebar.header("Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, 0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge %", 0.0, 100.0, 1.0, 0.5)
use_weather = st.sidebar.checkbox("Adjust edges for weather", value=True)

# -------------------
# FUNCTIONS
# -------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": API_KEY_ODDS, "regions":"us","markets":"h2h","oddsFormat":"decimal"}
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

def build_recommendations(games, sport_name):
    recs = []
    for i, g in enumerate(games):
        try:
            home = g["home_team"]
            away = g["away_team"]
            time = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00"))
            markets = g.get("bookmakers",[{}])[0].get("markets",[])
            h2h = next((m for m in markets if m["key"]=="h2h"), None)
            if not h2h: continue
            p_home = odds_to_prob(h2h["outcomes"][0]["price"])
            p_away = odds_to_prob(h2h["outcomes"][1]["price"])
            edge_home = p_home - 0.5
            edge_away = p_away - 0.5

            # --- WEATHER ADJUSTMENTS ---
            weather_str = "N/A"
            if use_weather:
                lat, lon = 40.0, -75.0
                weather_str, temp, wind, desc = fetch_weather(lat, lon)
                if wind and wind > 15:
                    edge_home *= 0.9
                    edge_away *= 0.9
                if desc and ("rain" in desc or "snow" in desc):
                    edge_home *= 0.85
                    edge_away *= 0.85
                if temp and temp > 95:
                    edge_home *= 0.95
                    edge_away *= 0.95

            best_edge = max(edge_home, edge_away)
            if best_edge*100 < min_edge_pct:
                continue
            selection = home if best_edge==edge_home else away
            opponent = away if best_edge==edge_home else home
            stake = bankroll * fractional_kelly * max(0,best_edge)
            recs.append({
                "record_id": f"{sport_name}_{i}_{int(datetime.utcnow().timestamp())}",
                "timestamp": datetime.utcnow(),
                "sport": sport_name,
                "home_team": home,
                "away_team": away,
                "matchup": f"{away} @ {home}",
                "game_time": time,
                "bet_type": "Moneyline",
                "selection": selection,
                "opponent": opponent,
                "edge_pct": round(best_edge*100,2),
                "stake": round(stake,2),
                "weather": weather_str,
                "status": "PENDING"
            })
        except:
            continue
    return pd.DataFrame(recs)

# -------------------
# FETCH & BUILD
# -------------------
all_games = []
for s in SPORTS:
    g = fetch_odds(SPORTS[s])
    if g:
        rec_df = build_recommendations(g, s)
        if not rec_df.empty:
            all_games.extend(rec_df.to_dict("records"))

if all_games:
    new_df = pd.DataFrame(all_games)
    bets_df = pd.concat([bets_df, new_df]).drop_duplicates(subset=["record_id"]).reset_index(drop=True)

# -------------------
# STYLE FUNCTION (SAFE)
# -------------------
def style_row(row):
    status = str(row.get("status",""))
    edge = row.get("edge_pct",0) if not pd.isna(row.get("edge_pct",0)) else 0
    if status=="WON": return ["background-color:#ADD8E6"]*len(row)
    if status=="LOST": return ["background-color:#D3D3D3"]*len(row)
    if edge>=5: return ["background-color:#9AFF99"]*len(row)
    if edge>=2: return ["background-color:#FFFF99"]*len(row)
    return ["background-color:#FF9999"]*len(row)

# -------------------
# DISPLAY ALL-TIME BETS
# -------------------
st.header("All-Time Bets Overview")
if not bets_df.empty:
    st.dataframe(bets_df.style.apply(style_row, axis=1), use_container_width=True)

# -------------------
# RANDOM PICK 3-8 CROSS-SPORT PARLAYS (SAFE)
# -------------------
st.subheader("Random Pick 3-8 Cross-Sport Parlays")
eligible_bets = bets_df[(bets_df["status"]=="PENDING") & (bets_df["edge_pct"]>=2)]
if eligible_bets.empty:
    st.write("Not enough bets to create parlays.")
else:
    for pick_count in range(3,9):
        st.markdown(f"**Pick-{pick_count} Parlays**")
        parlays_list=[]
        for _ in range(5):
            # Sample at most available bets safely
            sample_count = min(pick_count, len(eligible_bets))
            combo = eligible_bets.sample(sample_count)
            expected_edge = 1
            for val in combo["edge_pct"].fillna(0):
                expected_edge *= val/100
            expected_edge *= 100
            parlays_list.append({
                "Parlay": " + ".join(combo["selection"]),
                "Games": " + ".join(combo["matchup"]),
                "Expected Edge %": round(expected_edge,2),
                "Pick Count": len(combo)
            })
        st.dataframe(pd.DataFrame(parlays_list).sort_values("Expected Edge %",ascending=False), use_container_width=True)

# -------------------
# SAVE CSV
# -------------------
bets_df.to_csv(BETS_LOG,index=False)