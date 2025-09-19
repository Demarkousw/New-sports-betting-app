import streamlit as st
import pandas as pd

st.title("Step 1: Display Upcoming Games")

# --- Load Upcoming Games ---
try:
    upcoming_games = pd.read_csv("upcoming_games.csv")
    upcoming_games["game_time"] = pd.to_datetime(upcoming_games["game_time"])
    st.success("Upcoming games loaded ✅")
except FileNotFoundError:
    st.error("upcoming_games.csv not found!")
    st.stop()

# --- Display Table ---
st.subheader("Upcoming Games")
st.dataframe(upcoming_games)