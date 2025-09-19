# app.py
import streamlit as st
import pandas as pd
import numpy as np
import random

st.set_page_config(page_title="Advanced Sports Betting Dashboard", layout="wide")

st.title("Advanced Sports Betting Dashboard")
st.markdown("""
This app allows you to:
- Generate Pick 3, Pick 5, and Pick 8 parlays across MLB, NFL, and NCAA Football
- Include random cross-sport parlays
- Adjust predictions based on home/away, weather, injuries
- View over/under predictions and all-time betting history
- Track confidence percentages for each pick
""")

# -----------------------
# INSTRUCTION KEY
# -----------------------
st.sidebar.header("Instruction Key / Settings")
st.sidebar.markdown("""
**Home Advantage (%):** Boosts confidence for home teams.  
**Weather Impact (%):** Adjusts confidence/over-under for adverse conditions.  
**Min Confidence (%):** Filters eligible picks for parlays.  
**Pick Type:** Choose Pick 3, 5, or 8 for your parlay.  
**Cross-Sport:** Randomized selections from MLB, NFL, NCAA for diverse parlays.  
**Over/Under Calculation:** Based on team scoring averages, opponent allowed, weather, and home/away adjustments.  
**Upload CSV:** Must contain:  
- Date, Sport, HomeTeam, AwayTeam, ML, Spread, O/U, Confidence, HomeAway, Weather, TeamScoreAvg, OpponentAllowedAvg  
""")

# -----------------------
# Upload Historical Data
# -----------------------
st.header("Upload Historical Betting Data")
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.success("Data loaded successfully!")
    st.dataframe(df)
else:
    st.info("Upload your historical games CSV to continue.")

# -----------------------
# Settings Sliders
# -----------------------
st.header("Model Adjustment Settings")
home_advantage = st.slider("Home Team Advantage (%)", 0, 20, 5)
weather_impact = st.slider("Weather Impact (%)", 0, 20, 10)
min_confidence = st.slider("Minimum Confidence (%) for Picks", 40, 80, 55)

# -----------------------
# Prediction Adjustments
# -----------------------
st.header("Adjusted Confidence Predictions")

def adjust_confidence(row):
    conf = row['Confidence']
    if row['HomeAway'] == 'Home':
        conf += home_advantage
    if row['Weather'] in ['Rain', 'Snow', 'Wind']:
        conf -= weather_impact
    return min(max(conf, 0), 100)

if uploaded_file:
    df['AdjustedConfidence'] = df.apply(adjust_confidence, axis=1)
    st.dataframe(df[['Date','Sport','HomeTeam','AwayTeam','ML','Spread','O/U','Weather','AdjustedConfidence']])

# -----------------------
# Over/Under Predictions
# -----------------------
st.header("Over/Under Predictions")

if uploaded_file:
    df['PredictedTotal'] = (df['TeamScoreAvg'] + df['OpponentAllowedAvg']) * (1 - weather_impact/100)
    st.dataframe(df[['HomeTeam','AwayTeam','O/U','PredictedTotal']])

# -----------------------
# Random Cross-Sport Parlay Generator
# -----------------------
st.header("Random Cross-Sport Parlays")

def generate_cross_parlay(df, pick_count):
    eligible = df[df['AdjustedConfidence'] >= min_confidence]
    if len(eligible) < pick_count:
        return pd.DataFrame({"Error":["Not enough eligible games for this parlay."]})
    
    # Ensure at least one game per sport if possible
    sports = ['MLB','NFL','NCAA']
    parlay_list = []
    
    for sport in sports:
        sport_games = eligible[eligible['Sport'] == sport]
        if not sport_games.empty and len(parlay_list) < pick_count:
            parlay_list.append(sport_games.sample(1))
    
    remaining_picks = pick_count - len(parlay_list)
    if remaining_picks > 0:
        remaining_games = eligible.drop(pd.concat(parlay_list).index, errors='ignore')
        if not remaining_games.empty:
            parlay_list.append(remaining_games.sample(remaining_picks))
    
    final_parlay = pd.concat(parlay_list).reset_index(drop=True)
    return final_parlay[['Sport','HomeTeam','AwayTeam','ML','Spread','O/U','AdjustedConfidence']]

pick_choice = st.selectbox("Select Parlay Type", [3,5,8])
if st.button("Generate Parlay"):
    parlay_result = generate_cross_parlay(df, pick_choice)
    st.subheader(f"Random Pick {pick_choice} Parlay")
    st.dataframe(parlay_result)

# -----------------------
# All-Time Betting Overview
# -----------------------
st.header("All-Time Betting Overview")
if uploaded_file:
    st.dataframe(df[['Date','Sport','HomeTeam','AwayTeam','ML','Spread','O/U','Weather','AdjustedConfidence','PredictedTotal']])