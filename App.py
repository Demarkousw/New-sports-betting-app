# app.py
import streamlit as st
import pandas as pd
import requests
from elo import build_elos_from_history, expected_prob, american_to_decimal, implied_prob_from_american, kelly_fraction
from io import StringIO

st.set_page_config(page_title="Elo Value Bets (NFL & College)", layout="wide")
st.title("Elo Value Bets — NFL & College (auto odds)")

# Sidebar: settings + API key
st.sidebar.header("Settings & API")
api_key = st.sidebar.text_input("TheOddsAPI Key (paste here)", type="password")
sport_choice = st.sidebar.selectbox("Sport for auto-odds", ["NFL", "College Football (NCAAF)"])
base_elo = st.sidebar.number_input("Base Elo", value=1500, step=50)
kfactor = st.sidebar.number_input("K-factor", value=20, step=1)
bankroll = st.sidebar.number_input("Starting Bankroll $", value=1000.0, step=50.0)
fractional_kelly_pct = st.sidebar.number_input("Fractional Kelly % (recommended)", value=0.5, min_value=0.0, max_value=1.0, step=0.1)
regions = "us"  # odds region

# Upload historical CSV
st.sidebar.header("Upload historical CSV")
st.sidebar.markdown("CSV columns: date (YYYY-MM-DD, optional), home_team, away_team, home_score, away_score")
history_file = st.sidebar.file_uploader("Historical results CSV", type=["csv"])

# Build elos
if history_file is not None:
    try:
        df_hist = pd.read_csv(history_file)
        elos = build_elos_from_history(df_hist, base_elo=base_elo, kfactor=kfactor)
        st.sidebar.success(f"Loaded history: {len(df_hist)} rows; teams: {len(elos)}")
    except Exception as e:
        st.sidebar.error("Error reading history CSV: " + str(e))
        elos = {}
else:
    elos = {}
    st.sidebar.info("No history uploaded yet — app will use base Elo for unknown teams.")

# Auto-fetch odds button
st.header("1) Fetch today's odds automatically")
st.markdown("Press the button to fetch odds from The Odds API for the chosen sport.")
fetch_button = st.button("Fetch odds (auto)")

# Map sport_choice to TheOddsAPI sport keys
sport_key_map = {
    "NFL": "americanfootball_nfl",
    "College Football (NCAAF)": "americanfootball_ncaaf"
}
sport_key = sport_key_map[sport_choice]

def fetch_odds_from_theoddsapi(api_key, sport_key, regions="us", markets="h2h", oddsFormat="american"):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": regions, "markets": markets, "oddsFormat": oddsFormat}
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return {"error": f"Status {r.status_code}: {r.text}"}
    return r.json()

odds_data = None
if fetch_button:
    if not api_key:
        st.error("Paste your TheOddsAPI key in the sidebar first.")
    else:
        with st.spinner("Fetching odds..."):
            odds_data = fetch_odds_from_theoddsapi(api_key, sport_key, regions=regions, markets="h2h,spreads,totals", oddsFormat="american")
            if isinstance(odds_data, dict) and odds_data.get("error"):
                st.error("Odds fetch error: " + odds_data["error"])
                odds_data = None
            else:
                st.success(f"Fetched {len(odds_data)} events (may include in-play).")

# Manual paste fallback
st.header("2) Or paste / upload upcoming games (manual)")
st.markdown("CSV columns: home_team,away_team,home_odds,away_odds (American odds integers).")
upcoming_file = st.file_uploader("Upload upcoming games CSV", type=["csv"])
manual_text = st.text_area("Or paste CSV rows here (same columns)", height=120)

# Build unified upcoming games list
upcoming_rows = []
if odds_data:
    for ev in odds_data:
        if not ev.get("bookmakers"):
            continue
        home = ev.get("home_team") or ev.get("home")
        away = ev.get("away_team") or ev.get("away")
        bk = ev["bookmakers"][0]
        markets = {m["key"]: m for m in bk.get("markets", [])}
        if "h2h" in markets:
            outcomes = markets["h2h"]["outcomes"]
            home_odds = None
            away_odds = None
            for o in outcomes:
                name = o.get("name", "").lower()
                price = o.get("price")
                if not price:
                    continue
                if home.lower() in name:
                    home_odds = price
                if away.lower() in name:
                    away_odds = price
            if home_odds is None or away_odds is None:
                if len(outcomes) >= 2:
                    home_odds = outcomes[0].get("price")
                    away_odds = outcomes[1].get("price")
            if home and away and home_odds is not None and away_odds is not None:
                try:
                    upcoming_rows.append({
                        "home": home, "away": away, "home_odds": int(home_odds), "away_odds": int(away_odds)
                    })
                except:
                    # if casting to int fails, try float->int
                    upcoming_rows.append({
                        "home": home, "away": away, "home_odds": int(float(home_odds)), "away_odds": int(float(away_odds))
                    })

# manual CSV upload or paste
if upcoming_file is not None:
    try:
        df_up = pd.read_csv(upcoming_file)
        for _, r in df_up.iterrows():
            upcoming_rows.append({
                "home": r["home_team"],
                "away": r["away_team"],
                "home_odds": int(r["home_odds"]),
                "away_odds": int(r["away_odds"])
            })
    except Exception as e:
        st.warning("Problem reading an uploaded row: " + str(e))

if manual_text:
    try:
        df_manual = pd.read_csv(StringIO(manual_text))
        for _, r in df_manual.iterrows():
            upcoming_rows.append({
                "home": r["home_team"],
                "away": r["away_team"],
                "home_odds": int(r["home_odds"]),
                "away_odds": int(r["away_odds"])
            })
    except Exception as e:
        st.warning("Could not parse pasted CSV: " + str(e))

# If we have upcoming rows, assess them
if len(upcoming_rows) > 0:
    st.header("3) Model assessment — recommended bets")
    rows_out = []
    for r in upcoming_rows:
        home = r["home"]
        away = r["away"]
        elo_home = elos.get(home, base_elo)
        elo_away = elos.get(away, base_elo)
        phome = expected_prob(elo_home, elo_away)
        paway = 1.0 - phome
        home_odds = r["home_odds"]
        away_odds = r["away_odds"]
        dec_home = american_to_decimal(home_odds)
        dec_away = american_to_decimal(away_odds)
        imp_home = implied_prob_from_american(home_odds)
        imp_away = implied_prob_from_american(away_odds)
        edge_home = phome - imp_home
        edge_away = paway - imp_away
        kelly_home = kelly_fraction(dec_home, phome) * fractional_kelly_pct
        kelly_away = kelly_fraction(dec_away, paway) * fractional_kelly_pct
        rows_out.append({
            "home": home, "away": away,
            "elo_home": round(elo_home,1), "elo_away": round(elo_away,1),
            "p_home": round(phome,3), "p_away": round(paway,3),
            "home_odds": home_odds, "away_odds": away_odds,
            "imp_home": round(imp_home,3), "imp_away": round(imp_away,3),
            "edge_home": round(edge_home,3), "edge_away": round(edge_away,3),
            "kelly_home_frac": round(kelly_home,3), "kelly_away_frac": round(kelly_away,3),
            "kelly_home_$": round(kelly_home * bankroll,2), "kelly_away_$": round(kelly_away * bankroll,2)
        })
    df_results = pd.DataFrame(rows_out)
    st.subheader("All upcoming games (model vs market)")
    st.dataframe(df_results, width=1100)

    # Recommended bets
    bet_list = []
    for _, r in df_results.iterrows():
        if r["edge_home"] > 0:
            bet_list.append({
                "selection": f"{r['home']} (home)",
                "prob": r["p_home"],
                "odds": r["home_odds"],
                "edge": r["edge_home"],
                "kelly_frac": r["kelly_home_frac"],
                "stake_$": r["kelly_home_$"]
            })
        if r["edge_away"] > 0:
            bet_list.append({
                "selection": f"{r['away']} (away)",
                "prob": r["p_away"],
                "odds": r["away_odds"],
                "edge": r["edge_away"],
                "kelly_frac": r["kelly_away_frac"],
                "stake_$": r["kelly_away_$"]
            })
    if len(bet_list) == 0:
        st.info("No positive-edge bets found. Try adjusting K-factor, upload more history, or use a different bookmaker.")
    else:
        df_bets = pd.DataFrame(bet_list).sort_values("edge", ascending=False).reset_index(drop=True)
        df_bets["edge_pct"] = (df_bets["edge"] * 100).round(2)
        st.subheader("Recommended Value Bets (sorted by edge)")
        st.dataframe(df_bets[["selection","prob","odds","edge_pct","kelly_frac","stake_$"]], width=800)

st.markdown("---")
st.markdown("Notes: Press 'Fetch odds' to load the day's lines (The Odds API key required). The app uses the first bookmaker returned; you can later modify to choose best line.")
