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
API_KEY_ODDS = "c5eece64b53f2c9622543faf5861555d"  # Odds API key
API_KEY_WEATHER = "5ec258afff830598e45caad47e3edb8e"  # OpenWeatherMap API key

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
# APP HEADER
# -------------------
st.set_page_config(layout="wide", page_title="Sports Betting Assistant v2.5")
st.title("Sports Betting Assistant v2.5 — Full Automation, Cross-Sport & Fantasy")

# -------------------
# SIDEBAR SETTINGS
# -------------------
st.sidebar.header("Settings")
sport_choice = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
bankroll = st.sidebar.number_input("Your Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly Fraction", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]
use_weather = st.sidebar.checkbox("Adjust predictions for weather", value=True)

# -------------------
# FETCH ODDS
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

# -------------------
# FETCH WEATHER
# -------------------
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

# -------------------
# EDGE CALCULATIONS
# -------------------
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

            # Example stadium coords (replace with real coordinates if available)
            lat, lon = 40.0, -75.0
            weather_str, temp, wind, desc = fetch_weather(lat, lon)

            bookmakers = game.get("bookmakers", [])
            markets = {}
            if bookmakers:
                for m in bookmakers[0].get("markets", []):
                    markets[m["key"]] = m.get("outcomes", [])

            # Probabilities
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

            # Point Spread
            point_spread = None
            if markets.get("spreads"):
                for outcome in markets["spreads"]:
                    if "point" in outcome:
                        point_spread = outcome["point"]

            # Adjust edges for weather if enabled
            if use_weather:
                if wind and wind > 15:
                    if "Over" in edges:
                        edges["Over"] -= 0.1
                    if "Under" in edges:
                        edges["Under"] += 0.1
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
# FETCH & BUILD
# -------------------
all_games = []
for s in SPORTS.keys():
    games = fetch_odds(SPORTS[s])
    all_games.extend(build_recommendations(games, s).to_dict("records") if games else [])

if all_games:
    new_df = pd.DataFrame(all_games)
    bets_df = pd.concat([bets_df, new_df]).drop_duplicates(subset=["record_id"], keep="first").reset_index(drop=True)

# -------------------
# COLOR-CODING
# -------------------
def style_row(row):
    edge = row["edge_pct"]
    status = row["status"]
    if status=="WON":
        return ["background-color: #ADD8E6; color: black"]*len(row)
    elif status=="LOST":
        return ["background-color: #D3D3D3; color: black"]*len(row)
    elif edge >= 5:
        return ["background-color: #9AFF99; color: black"]*len(row)
    elif edge >= 2:
        return ["background-color: #FFFF99; color: black"]*len(row)
    else:
        return ["background-color: #FF9999; color: black"]*len(row)

# -------------------
# RECOMMENDED PARLAYS (Pick-3 to Pick-8)
# -------------------
st.subheader("Recommended Parlays (Pick-3 to Pick-8)")
top_bets = bets_df[bets_df["status"]=="PENDING"].sort_values(by="edge_pct", ascending=False).head(10)
parlays = []

for r in range(3,9):
    for combo in itertools.combinations(top_bets.index, r):
        selections = [top_bets.loc[i, "selection"] for i in combo]
        matchups = [top_bets.loc[i, "matchup"] for i in combo]
        expected_edge = 1
        for i in combo:
            expected_edge *= top_bets.loc[i, "edge_pct"] / 100
        expected_edge *= 100
        parlays.append({
            "Parlay": " + ".join(selections),
            "Games": " + ".join(matchups),
            "Expected Edge %": round(expected_edge,2),
            "Pick Count": r
        })

parlays_df = pd.DataFrame(parlays).sort_values(by="Expected Edge %", ascending=False)
if not parlays_df.empty:
    st.dataframe(parlays_df, use_container_width=True)
else:
    st.write("No parlays available with current settings.")

# -------------------
# TRUE CROSS-SPORT RANDOM PARLAYS
# -------------------
st.subheader("Random Cross-Sport Parlays (MLB + NCAA + NFL)")
all_top_bets = bets_df[(bets_df["status"]=="PENDING") & (bets_df["edge_pct"]>=2)]
random_parlays = []

if not all_top_bets.empty:
    for _ in range(5):
        combo = all_top_bets.sample(min(3, len(all_top_bets)))
        selections = combo["selection"].tolist()
        matchups = combo["matchup"].tolist()
        expected_edge = 1
        for val in combo["edge_pct"]:
            expected_edge *= val/100
        expected_edge *= 100
        random_parlays.append({
            "Parlay": " + ".join(selections),
            "Games": " + ".join(matchups),
            "Expected Edge %": round(expected_edge,2)
        })
    st.dataframe(pd.DataFrame(random_parlays), use_container_width=True)
else:
    st.write("Not enough high-edge bets across sports to create random cross-sport parlays.")

# -------------------
# DISPLAY W/L TABLE
# -------------------
st.header("All-Time Bets Overview")
st.dataframe(bets_df.style.apply(style_row, axis=1), use_container_width=True)

# -------------------
# UPDATE PENDING BETS
# -------------------
pending = bets_df[bets_df["status"]=="PENDING"]
if not pending.empty:
    st.subheader("Update Pending Bets")
    pending_opts = pending["record_id"].astype(str).tolist()
    chosen_pending = st.multiselect("Select pending bets to mark", pending_opts)
    result_choice = st.radio("Mark as", ["WON","LOST"], index=1)
    if st.button("Apply Result"):
        for rid in chosen_pending:
            idx = bets_df[bets_df["record_id"].astype(str)==rid].index
            if len(idx)==0: continue
            bets_df.loc[idx,"status"] = result_choice
        bets_df.to_csv(BETS_LOG,index=False)
        st.success("Updated pending bets.")

# -------------------
# ALL-TIME RECORD
# -------------------
if not bets_df.empty:
    wins = len(bets_df[bets_df["status"]=="WON"])
    losses = len(bets_df[bets_df["status"]=="LOST"])
    st.subheader("All-Time Record")
    st.write(f"Wins: {wins} | Losses: {losses} | Total Bets: {wins + losses}")

# -------------------
# NFL FANTASY PROJECTIONS
# -------------------
st.subheader("NFL Fantasy Player Projections (Top 50)")
def fetch_nfl_fantasy():
    url = "https://api.sleeper.app/v1/players/nfl"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        fantasy_df = pd.DataFrame([
            {
                "Player": p["full_name"],
                "Team": p["team"],
                "Position": p["position"],
                "Fantasy Points": p.get("fantasy_points", None)
            }
            for p in data.values() if p.get("fantasy_points")
        ])
        return fantasy_df
    else:
        return pd.DataFrame()

fantasy_df = fetch_nfl_fantasy()
if not fantasy_df.empty:
    st.dataframe(fantasy_df.sort_values("Fantasy Points", ascending=False).head(50), use_container_width=True)
else:
    st.write("No fantasy data available.")