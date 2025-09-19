# sports_betting_assistant_v2_5_display_only.py
import random
from itertools import combinations
import streamlit as st
import pandas as pd

# ------------------------
# Example Game Data
# ------------------------
NFL_games = [
    {"team1": "Packers", "team2": "Browns", "ml1": -150, "ml2": +130, "spread1": -3, "spread2": +3, "ou": 42.5},
    {"team1": "Cowboys", "team2": "Eagles", "ml1": +180, "ml2": -200, "spread1": -3, "spread2": +3, "ou": 45.5},
]

NCAA_games = [
    {"team1": "Ohio St", "team2": "Michigan", "ml1": -200, "ml2": +170, "spread1": -6, "spread2": +6, "ou": 52.0},
]

MLB_games = [
    {"team1": "Yankees", "team2": "Red Sox", "ml1": -120, "ml2": +110},
]

Fantasy_NFL_players = [
    {"position": "QB", "player": "Aaron Rodgers", "stat": "Passing Yards", "projection": 280},
    {"position": "RB", "player": "Aaron Jones", "stat": "Rushing Yards", "projection": 85},
    {"position": "WR", "player": "Davante Adams", "stat": "Rec Yards", "projection": 105},
    {"position": "TE", "player": "Robert Tonyan", "stat": "Rec Yards", "projection": 65},
    {"position": "FLEX", "player": "Allen Lazard", "stat": "Rec Yards", "projection": 70},
]

# ------------------------
# Functions
# ------------------------
def calculate_probability(ml):
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def calculate_parlay_payout(parlay, stake=100):
    total_multiplier = 1
    for pick in parlay:
        if pick["type"] == "ML":
            odds = pick["value"]
            total_multiplier *= (odds / 100 + 1) if odds > 0 else (100 / -odds + 1)
        else:
            total_multiplier *= 1.91
    return round(stake * total_multiplier, 2)

def select_pick(game):
    pick_type = random.choice(["ML", "Spread", "OU"])
    if pick_type == "ML":
        team = random.choice(["team1","team2"])
        return {"type":"ML", "team":game[team], "value":game[f"ml{1 if team=='team1' else 2}"]}
    elif pick_type=="Spread" and "spread1" in game:
        team = random.choice(["team1","team2"])
        return {"type":"Spread","team":game[team],"value":game[f"spread{1 if team=='team1' else 2}"]}
    elif pick_type=="OU" and "ou" in game:
        side=random.choice(["Over","Under"])
        return {"type":"OU","value":f"{side} {game['ou']}"}
    else:
        return select_pick(game)

def generate_recommended_parlays(all_games, min_pick=3, max_pick=8, stake=100, display_count=5):
    parlays=[]
    for pick_count in range(min_pick,max_pick+1):
        combos=list(combinations(all_games,pick_count))
        top_combos=combos[:display_count]
        for combo in top_combos:
            parlay=[select_pick(g) for g in combo]
            payout=calculate_parlay_payout(parlay,stake)
            parlays.append({"parlay":parlay,"payout":payout})
    return parlays

def generate_random_cross_sport_parlays(NFL,NCAA,MLB,num_parlays=5,stake=100):
    parlays=[]
    for _ in range(num_parlays):
        picks=[
            select_pick(random.choice(NFL)),
            select_pick(random.choice(NCAA)),
            select_pick(random.choice(MLB))
        ]
        payout=calculate_parlay_payout(picks,stake)
        parlays.append({"parlay":picks,"payout":payout})
    return parlays

def format_parlay_text(parlay):
    text=""
    for pick in parlay:
        team=pick.get("team","")
        text+=f"{pick['type']} | {team} | {pick['value']}\n"
    return text

def format_parlay_html(parlay):
    html_text=""
    for pick in parlay:
        team=pick.get("team","")
        color="green" if pick["type"]=="ML" else "orange"
        html_text+=f"<span style='color:{color}'>{pick['type']} | {team} | {pick['value']}</span><br>"
    return html_text

# ------------------------
# Streamlit Layout
# ------------------------
st.set_page_config(page_title="Sports Betting Assistant v2.5", layout="wide")
st.title("Sports Betting Assistant v2.5 — Full Automation, Cross-Sport & Fantasy")

stake = 100
display_count = 5
num_random = 5
all_games = NFL_games + NCAA_games + MLB_games

# ------------------------
# Recommended Parlays
st.markdown("## Recommended Parlays (Pick-3 to Pick-8)")
recommended=generate_recommended_parlays(all_games,stake=stake,display_count=display_count)
for idx,p in enumerate(recommended):
    st.markdown(f"**Parlay {idx+1}:**",unsafe_allow_html=True)
    st.markdown(format_parlay_html(p["parlay"]),unsafe_allow_html=True)
    st.write(f"Potential Payout: ${p['payout']}")

# ------------------------
# Random Cross-Sport Parlays
st.markdown("## Random Cross-Sport Parlays (MLB + NCAA + NFL)")
random_parlays=generate_random_cross_sport_parlays(NFL_games,NCAA_games,MLB_games,num_parlays=num_random,stake=stake)
for idx,p in enumerate(random_parlays):
    st.markdown(f"**Parlay {idx+1}:**",unsafe_allow_html=True)
    st.markdown(format_parlay_html(p["parlay"]),unsafe_allow_html=True)
    st.write(f"Potential Payout: ${p['payout']}")

# ------------------------
# All-Time Bets Overview
st.markdown("## All-Time Bets Overview")
if "tracker" not in st.session_state:
    st.session_state["tracker"]=pd.DataFrame(columns=["Parlay","Stake","Payout","Result"])
st.dataframe(st.session_state["tracker"])

# ------------------------
# NFL Fantasy Picks
st.markdown("## NFL Fantasy Picks")
stat_avg={"Passing Yards":280,"Rushing Yards":80,"Rec Yards":90,"Points Allowed":22,"Field Goals Made":2}
for f in Fantasy_NFL_players:
    rec="Over" if f["projection"]>stat_avg.get(f["stat"],0) else "Under"
    color="green" if rec=="Over" else "red"
    st.markdown(f"<span style='color:{color}'>{f['position']} | {f['player']} | {f['stat']} {f['projection']} | {rec}</span>",unsafe_allow_html=True)