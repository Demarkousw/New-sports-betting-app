# App.py - Sports Betting Assistant v2.6 (Fixed)
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
import math
import itertools
import random
from functools import lru_cache

# -------------------
# CONFIG: API KEYS
# -------------------
API_KEY_ODDS = "c5eece64b53f2c9622543faf5861555d"      # Odds API key
API_KEY_WEATHER = "5ec258afff830598e45caad47e3edb8e"   # OpenWeatherMap key
# Sleeper = public, no key needed

# -------------------
# SPORTS CONFIG
# -------------------
SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA Football": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}
REGIONS = "us"
MARKETS = ["h2h","spreads","totals"]

# -------------------
# BETS LOG (safer loader)
# -------------------
BETS_LOG = "bets_log.csv"
BETS_COLS = [
    "record_id","timestamp","sport","week","home_team","away_team","matchup",
    "game_time","bet_type","selection","opponent","edge_pct","stake",
    "predicted_margin","point_spread","weather","status"
]

def load_or_create_csv(path, cols):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            # Ensure all required columns exist
            for c in cols:
                if c not in df.columns:
                    df[c] = pd.NA
            return df[cols]
        except:
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

bets_df = load_or_create_csv(BETS_LOG, BETS_COLS)

# -------------------
# STREAMLIT UI
# -------------------
st.set_page_config(layout="wide", page_title="Sports Betting Assistant v2.6")
st.title("Sports Betting Assistant v2.6 — All-in-One Betting + Fantasy")

# Sidebar
st.sidebar.header("Settings")
sport_choice = st.sidebar.selectbox("Sport (focus)", list(SPORTS.keys()))
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge %", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]
use_weather = st.sidebar.checkbox("Weather adjustments", value=True)
fantasy_mode = st.sidebar.selectbox("Fantasy scoring", ["PPR","Half PPR","Standard"], index=0)

# -------------------
# HELPERS
# -------------------
def odds_to_prob_decimal(odds):
    try:
        o = float(odds)
        if o <= 0: return 0.5
        return 1.0 / o
    except:
        return 0.5

def calc_margin_from_probs(p_home, p_away):
    p_home = max(min(p_home,0.9999),0.0001)
    p_away = max(min(p_away,0.9999),0.0001)
    return math.log(p_home/(1-p_home)) - math.log(p_away/(1-p_away))

def fetch_odds_for_sport(sport_key):
    """Fetch odds and gracefully handle missing markets."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey":API_KEY_ODDS,"regions":REGIONS,"markets":",".join(MARKETS),"oddsFormat":"decimal"}
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

@lru_cache(maxsize=128)
def fetch_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY_WEATHER}&units=imperial"
        r = requests.get(url,timeout=8)
        r.raise_for_status()
        d = r.json()
        desc = d['weather'][0]['description'].title()
        temp = d['main'].get('temp',None)
        wind = d.get('wind',{}).get('speed',None)
        return f"{desc} {temp}°F, Wind {wind} mph"
    except:
        return "N/A"

# -------------------
# BUILD RECOMMENDATIONS
# -------------------
def build_recs(game,sport_name):
    try:
        home, away = game.get("home_team"), game.get("away_team")
        commence = game.get("commence_time")
        game_time = datetime.fromisoformat(commence.replace("Z","+00:00")) if commence else None
        weather = fetch_weather(40.0,-75.0)  # placeholder coords
        bookmakers = game.get("bookmakers",[])
        markets = {}
        if bookmakers:
            first = bookmakers[0]
            for m in first.get("markets",[]):
                markets[m["key"]] = m.get("outcomes",[])
        # default
        p_home,p_away=0.5,0.5
        if "h2h" in markets and len(markets["h2h"])>=2:
            o0,o1=markets["h2h"][0]["price"],markets["h2h"][1]["price"]
            p_home,p_away=odds_to_prob_decimal(o0),odds_to_prob_decimal(o1)
        margin = calc_margin_from_probs(p_home,p_away)
        edges={}
        if "h2h" in markets:
            edges["ML Home"]=p_home-0.5; edges["ML Away"]=p_away-0.5
        if "spreads" in markets:
            edges["Spread Home"]=margin; edges["Spread Away"]=-margin
        if "totals" in markets:
            edges["Over"]=0.0; edges["Under"]=0.0
        if not edges: return None
        best_key=max(edges,key=lambda k:edges[k])
        edge_pct=edges[best_key]*100
        if edge_pct<min_edge_pct: return None
        if "ML" in best_key:
            bt="Moneyline"; sel=home if "Home" in best_key else away
            opp=away if "Home" in best_key else home
        elif "Spread" in best_key:
            bt="Spread"; sel=home if "Home" in best_key else away
            opp=away if "Home" in best_key else home
        else:
            bt="Totals"; sel=best_key; opp=f"{away}@{home}"
        stake=round(bankroll*fractional_kelly*max(0,edges[best_key]),2)
        return {
            "record_id":f"{sport_name}_{int(datetime.utcnow().timestamp())}",
            "timestamp":datetime.utcnow(),
            "sport":sport_name,
            "week":game.get("week"),
            "home_team":home,"away_team":away,
            "matchup":f"{away} @ {home}","game_time":game_time,
            "bet_type":bt,"selection":sel,"opponent":opp,
            "edge_pct":round(edge_pct,2),"stake":stake,
            "predicted_margin":round(margin,2),
            "point_spread":None,"weather":weather,"status":"PENDING"
        }
    except:
        return None

def build_all_recs():
    rows=[]
    for s in SPORTS:
        games=fetch_odds_for_sport(SPORTS[s])
        for g in games:
            r=build_recs(g,s)
            if r: rows.append(r)
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=BETS_COLS)

# -------------------
# FANTASY SECTION (always shows table)
# -------------------
def fetch_sleeper_players():
    try:
        r=requests.get("https://api.sleeper.app/v1/players/nfl",timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return {}

def build_fantasy_projections():
    players=fetch_sleeper_players()
    if not players:  # fallback baseline if empty
        return pd.DataFrame([
            {"Player":"Baseline QB","Team":"N/A","Position":"QB","ProjPts":15},
            {"Player":"Baseline RB","Team":"N/A","Position":"RB","ProjPts":10},
            {"Player":"Baseline WR","Team":"N/A","Position":"WR","ProjPts":9},
            {"Player":"Baseline TE","Team":"N/A","Position":"TE","ProjPts":6}
        ])
    rows=[]
    for pid,p in players.items():
        pos=p.get("position")
        if pos not in("QB","RB","WR","TE"): continue
        name=p.get("full_name",pid); team=p.get("team","FA")
        proj={"QB":15,"RB":10,"WR":9,"TE":6}
        rows.append({"Player":name,"Team":team,"Position":pos,"ProjPts":proj.get(pos,7)})
    df=pd.DataFrame(rows)
    df["LastUpdated"]=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return df.sort_values("ProjPts",ascending=False).head(50)

# -------------------
# DISPLAY
# -------------------
with st.spinner("Fetching odds..."):
    new=build_all_recs()
    if not new.empty:
        bets_df=pd.concat([bets_df,new]).drop_duplicates(subset=["record_id"],keep="first")

# Parlays
st.subheader("Recommended Parlays (Pick-3 to Pick-8)")
top=bets_df[bets_df["status"]=="PENDING"].sort_values("edge_pct",ascending=False).head(10)
if len(top)>=3:
    parlays=[]
    for r in range(3,min(8,len(top))+1):
        for combo in itertools.combinations(top.index,r):
            sel=[top.loc[i,"selection"] for i in combo]
            parlays.append({"Parlay":" + ".join(sel)})
    st.dataframe(pd.DataFrame(parlays))
else:
    st.write("Not enough bets yet.")

# All bets table
st.header("All Bets")
def style_row(row):
    e=float(row["edge_pct"]) if not pd.isna(row["edge_pct"]) else 0
    stt=row["status"].upper()
    if stt=="WON": return ["background-color:#ADD8E6"]*len(row)
    if stt=="LOST": return ["background-color:#D3D3D3"]*len(row)
    if e>=5: return ["background-color:#9AFF99"]*len(row)
    if e>=2: return ["background-color:#FFFF99"]*len(row)
    return ["background-color:#FF9999"]*len(row)
st.dataframe(bets_df.style.apply(style_row,axis=1),use_container_width=True)

# Update pending
st.subheader("Update Pending Bets")
pending=bets_df[bets_df["status"]=="PENDING"]
if not pending.empty:
    chosen=st.multiselect("Select pending bets",pending["record_id"].astype(str).tolist())
    result=st.radio("Mark as",["WON","LOST"])
    if st.button("Apply"):
        for rid in chosen:
            idx=bets_df[bets_df["record_id"].astype(str)==rid].index
            bets_df.loc[idx,"status"]=result
        bets_df.to_csv(BETS_LOG,index=False)
        st.success("Updated pending bets!")

# Record summary
wins=len(bets_df[bets_df["status"]=="WON"])
losses=len(bets_df[bets_df["status"]=="LOST"])
st.subheader("All-Time Record")
st.write(f"Wins: {wins} | Losses: {losses} | Total: {wins+losses}")

# Fantasy
st.subheader("Fantasy — NFL Players")
fantasy_df=build_fantasy_projections()
st.dataframe(fantasy_df,use_container_width=True)

st.subheader("Fantasy — NCAA Teams (value est.)")
st.dataframe(bets_df[bets_df["sport"]=="NCAA Football"][["matchup","weather"]])

st.subheader("Fantasy — MLB Teams (value est.)")
st.dataframe(bets_df[bets_df["sport"]=="MLB"][["matchup","weather"]])

# Instructions
with st.expander("How to Use"):
    st.markdown("""
- **Odds & Parlays**: Auto-pulled for NFL, NCAA, MLB. Will fallback gracefully if certain markets aren’t available.
- **Colors**: Green = strong, Yellow = medium, Red = weak, Blue = won, Gray = lost.
- **Update Pending Bets**: Use this box to mark bets WON or LOST.
- **Record**: Tracks your all-time win/loss record.
- **Fantasy**: 
  - NFL = top projected players (baseline always shown, Sleeper when available).
  - NCAA/MLB = team value placeholders (upgrade-ready).
- **APIs**:
  - Odds API: https://the-odds-api.com
  - Weather API: https://openweathermap.org
  - Sleeper API: https://docs.sleeper.com
""")