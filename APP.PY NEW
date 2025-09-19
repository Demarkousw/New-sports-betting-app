# App.py — Betting Dashboard v2.1
# Features: NFL / NCAAF / MLB; color-coded table; simulate bets; track wins/losses; download; logging

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import math
import io
import os

st.set_page_config(layout="wide", page_title="Betting Dashboard v2.1")
st.title("Betting Dashboard v2.1 — Live Odds, Simulator & Tracker")

# -------------------------
# Sidebar: global settings
# -------------------------
st.sidebar.header("Global Settings")
sport_choice = st.sidebar.selectbox("Select sport", ["NFL", "NCAA Football", "MLB"])
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000, step=50)
use_flat = st.sidebar.checkbox("Use flat stake instead of Kelly", value=False)
flat_stake = st.sidebar.number_input("Flat stake amount ($)", min_value=0, value=25, step=5)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]

# API key (you provided earlier)
API_KEY = "8a264564e3a5d2a556d475e547e1c417"

# sport mapping and league averages (fallback)
SPORT_MAP = {
    "NFL": ("americanfootball_nfl", 45.0),
    "NCAA Football": ("americanfootball_ncaaf", 56.0),
    "MLB": ("baseball_mlb", 8.5)
}
SPORT_API_KEY, default_league_total = SPORT_MAP[sport_choice]
st.sidebar.markdown(f"**League avg total (fallback):** {default_league_total}")

# Files for persistent storage
BETS_LOG = "bets_log.csv"        # records bets placed (pending + recorded)
RESULTS_LOG = "results.csv"      # records resolved bets (won/lost)
APP_LOG = "app_log.txt"

# -------------------------
# Utility: fetch odds with fallback
# -------------------------
def fetch_odds_with_fallback(sport_api_key):
    base_url = f"https://api.the-odds-api.com/v4/sports/{sport_api_key}/odds"
    combos = ["h2h,spreads,totals", "h2h,spreads", "h2h,totals", "spreads,totals", "h2h"]
    last_err = None
    for markets in combos:
        try:
            r = requests.get(base_url, params={"apiKey": API_KEY, "regions":"us", "markets": markets}, timeout=15)
            r.raise_for_status()
            st.info(f"Using markets: {markets}")
            return r.json()
        except requests.HTTPError as e:
            last_err = f"{markets} -> {e}"
            st.warning(f"Markets '{markets}' not available or returned error.")
            continue
        except Exception as e:
            last_err = str(e)
            st.error(f"Error fetching odds: {e}")
            return []
    st.error(f"All market combos failed. Last error: {last_err}")
    return []

# -------------------------
# Fetch and normalize data
# -------------------------
st.info(f"Fetching upcoming {sport_choice} odds...")
data = fetch_odds_with_fallback(SPORT_API_KEY)
if not data:
    st.stop()

games = []
for game in data:
    home = game.get("home_team")
    away = game.get("away_team")
    ct = game.get("commence_time")
    try:
        game_time = datetime.fromisoformat(ct.replace("Z","+00:00"))
    except Exception:
        game_time = ct
    ml_home = ml_away = None
    spread_home = spread_away = None
    total_market = None

    bookmakers = game.get("bookmakers") or []
    if bookmakers:
        markets = bookmakers[0].get("markets") or []
        for m in markets:
            key = m.get("key")
            outcomes = m.get("outcomes") or []
            if key == "h2h" and len(outcomes) >= 2:
                names = [o.get("name","") for o in outcomes]
                # try map by name
                if home in names and away in names:
                    if outcomes[0].get("name") == home:
                        ml_home = outcomes[0].get("price"); ml_away = outcomes[1].get("price")
                    else:
                        ml_home = outcomes[1].get("price"); ml_away = outcomes[0].get("price")
                else:
                    ml_home = outcomes[0].get("price"); ml_away = outcomes[1].get("price")
            elif key == "spreads" and len(outcomes) >= 2:
                # assign by ordering or name
                try:
                    if outcomes[0].get("name") and home in outcomes[0].get("name"):
                        spread_home = outcomes[0].get("point"); spread_away = outcomes[1].get("point")
                    else:
                        spread_home = outcomes[0].get("point"); spread_away = outcomes[1].get("point")
                except:
                    spread_home = outcomes[0].get("point"); spread_away = outcomes[1].get("point")
            elif key == "totals" and len(outcomes) >= 1:
                total_market = outcomes[0].get("point")
    games.append({
        "home": home, "away": away, "game_time": game_time,
        "ml_home": ml_home, "ml_away": ml_away,
        "spread_home": spread_home, "spread_away": spread_away,
        "total_market": total_market
    })

df = pd.DataFrame(games)

# show games
st.subheader("All Upcoming Games & Market Lines")
if not df.empty:
    df_display = df.copy()
    df_display["game_time"] = df_display["game_time"].astype(str)
    st.dataframe(df_display)
else:
    st.write("No games available.")

# -------------------------
# helpers: odds -> prob, margin mapping
# -------------------------
def odds_to_implied_prob(odds):
    if odds is None:
        return None
    try:
        o = float(odds)
    except:
        return None
    if o > 0:
        return 100.0 / (o + 100.0)
    else:
        return (-o) / ((-o) + 100.0)

def ml_probs_to_margin(p_home, p_away):
    p_home = max(min(p_home, 0.9999), 0.0001)
    p_away = max(min(p_away, 0.9999), 0.0001)
    logit_home = math.log(p_home/(1-p_home))
    logit_away = math.log(p_away/(1-p_away))
    diff = logit_home - logit_away
    scale = 7.0
    return diff * scale

# -------------------------
# build recommendations (simple model, consistent scaling)
# -------------------------
recommendations = []
for i, row in df.iterrows():
    home = row["home"]; away = row["away"]
    market_total = row["total_market"] if row["total_market"] is not None else default_league_total

    p_home = odds_to_implied_prob(row["ml_home"]) or 0.5
    p_away = odds_to_implied_prob(row["ml_away"]) or 0.5
    predicted_margin = ml_probs_to_margin(p_home, p_away)

    scale_for_prob = 13.5
    model_p_home = 1.0 / (1.0 + math.exp(-predicted_margin / scale_for_prob))
    model_p_away = 1.0 - model_p_home

    edge_ml_home = model_p_home - (p_home or 0.5)
    edge_ml_away = model_p_away - (p_away or 0.5)

    market_spread_home = None
    try:
        market_spread_home = float(row["spread_home"]) if row["spread_home"] is not None else None
    except:
        market_spread_home = None
    market_spread_away = None
    try:
        market_spread_away = float(row["spread_away"]) if row["spread_away"] is not None else None
    except:
        market_spread_away = None

    spread_edge_home = (predicted_margin - market_spread_home)/10.0 if market_spread_home is not None else 0
    spread_edge_away = ((-predicted_margin) - market_spread_away)/10.0 if market_spread_away is not None else 0

    model_total = default_league_total + (predicted_margin * 0.05)
    over_edge = model_total - market_total
    under_edge = market_total - model_total

    edges = {
        "ML Home": edge_ml_home,
        "ML Away": edge_ml_away,
        "Spread Home": spread_edge_home,
        "Spread Away": spread_edge_away,
        "Over": over_edge,
        "Under": under_edge
    }

    best_key = max(edges, key=edges.get)
    best_edge = edges[best_key]
    edge_pct = best_edge * 100

    if use_flat:
        stake = float(flat_stake)
    else:
        stake = bankroll * fractional_kelly * max(0.0, best_edge)

    if best_key.startswith("ML"):
        bet_type = "Moneyline"
        selection = home if "Home" in best_key else away
        opponent = away if "Home" in best_key else home
    elif best_key.startswith("Spread"):
        bet_type = "Spread"
        selection = f"{home} - spread" if "Home" in best_key else f"{away} - spread"
        opponent = away if "Home" in best_key else home
    else:
        bet_type = "Totals"
        selection = best_key  # Over or Under
        opponent = f"{away} @ {home}"

    if bet_type in bet_type_filter and edge_pct >= min_edge_pct:
        recommendations.append({
            "id": f"{i}_{int(datetime.utcnow().timestamp())}",
            "Matchup": f"{away} @ {home}",
            "Game Time": row["game_time"],
            "Bet Type": bet_type,
            "Selection": selection,
            "Opponent": opponent,
            "Edge %": round(edge_pct,2),
            "Stake $": round(stake,2),
            "Market Total": market_total,
            "Model Total": round(model_total,2),
            "Predicted Margin": round(predicted_margin,2)
        })

# -------------------------
# Display recommendations with color coding
# -------------------------
st.subheader("Recommended Value Bets (sorted by Edge %)")
if recommendations:
    rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
    # convert game time to str
    rec_df_display = rec_df.copy()
    rec_df_display["Game Time"] = rec_df_display["Game Time"].astype(str)

    # styling function
    def color_edge(val):
        try:
            v = float(val)
        except:
            return ""
        if v >= 10:
            color = 'background-color: #2ECC71'  # green
        elif v >= 3:
            color = 'background-color: #F1C40F'  # yellow
        elif v > 0:
            color = 'background-color: #F7DC6F'  # light yellow
        else:
            color = 'background-color: #E74C3C'  # red
        return color

    styled = rec_df_display.style.applymap(color_edge, subset=["Edge %"])
    st.dataframe(rec_df_display)  # also show plain dataframe for reliability

    # Download button
    csv_bytes = rec_df_display.to_csv(index=False).encode('utf-8')
    st.download_button("Download recommendations CSV", data=csv_bytes, file_name="recommendations.csv", mime="text/csv")

    # Selection for recording bets
    st.markdown("## Record bets you placed (simulate)")
    rec_df_select = rec_df_display.copy()
    rec_df_select["choose"] = False
    # show a multiselect with Matchup + Bet Type
    options = [f"{r['Matchup']} | {r['Bet Type']} | {r['Selection']} | Edge {r['Edge %']}%" for _, r in rec_df.iterrows()]
    chosen = st.multiselect("Select recommendations you actually placed", options)

    if st.button("Record Selected Bets"):
        to_record = []
        timestamp = datetime.utcnow().isoformat()
        for opt in chosen:
            # find row
            idx = options.index(opt)
            row = rec_df.iloc[idx].to_dict()
            record = {
                "record_id": row["id"],
                "timestamp": timestamp,
                "sport": sport_choice,
                "matchup": row["Matchup"],
                "game_time": str(row["Game Time"]),
                "bet_type": row["Bet Type"],
                "selection": row["Selection"],
                "opponent": row["Opponent"],
                "edge_pct": row["Edge %"],
                "stake": row["Stake $"],
                "market_total": row["Market Total"],
                "model_total": row["Model Total"],
                "predicted_margin": row["Predicted Margin"],
                "status": "PENDING"
            }
            to_record.append(record)
        # append to bets_log.csv
        if to_record:
            df_new = pd.DataFrame(to_record)
            if os.path.exists(BETS_LOG):
                df_old = pd.read_csv(BETS_LOG)
                df_all = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df_all = df_new
            df_all.to_csv(BETS_LOG, index=False)
            st.success(f"Recorded {len(to_record)} bets to {BETS_LOG}")
        else:
            st.info("No bets selected to record.")
else:
    st.write("No recommendations available for your filters.")

# -------------------------
# Bet Tracker: view pending bets and mark as won/lost
# -------------------------
st.header("Bet Tracker — mark results (Wins / Losses)")
if os.path.exists(BETS_LOG):
    bets_df = pd.read_csv(BETS_LOG)
    # show pending bets first
    pending = bets_df[bets_df["status"] == "PENDING"]
    st.subheader("Pending Bets")
    if not pending.empty:
        pending_display = pending.copy()
        st.dataframe(pending_display)
        # allow marking by selecting record_id
        pending_options = pending["record_id"].tolist()
        chosen_pending = st.multiselect("Select pending bets to mark result", pending_options)
        result_choice = st.radio("Mark selected as:", ["WON", "LOST"], index=1)
        if st.button("Apply Result to Selected"):
            if not chosen_pending:
                st.info("No pending bets selected.")
            else:
                # move selected to results log and update bets_log status
                results = []
                for rid in chosen_pending:
                    row = pending[pending["record_id"] == rid].iloc[0].to_dict()
                    res = {
                        "record_id": row["record_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "sport": row.get("sport"),
                        "matchup": row.get("matchup"),
                        "bet_type": row.get("bet_type"),
                        "selection": row.get("selection"),
                        "stake": row.get("stake"),
                        "edge_pct": row.get("edge_pct"),
                        "result": result_choice
                    }
                    results.append(res)
                    # update bets_df status
                    bets_df.loc[bets_df["record_id"] == rid, "status"] = result_choice
                # save updated bets_log
                bets_df.to_csv(BETS_LOG, index=False)
                # append to RESULTS_LOG
                if os.path.exists(RESULTS_LOG):
                    old_res = pd.read_csv(RESULTS_LOG)
                    new_res = pd.concat([old_res, pd.DataFrame(results)], ignore_index=True)
                else:
                    new_res = pd.DataFrame(results)
                new_res.to_csv(RESULTS_LOG, index=False)
                st.success(f"Marked {len(results)} bets as {result_choice} and updated logs.")
    else:
        st.write("No pending bets.")
    # show historic results summary
    if os.path.exists(RESULTS_LOG):
        res_df = pd.read_csv(RESULTS_LOG)
        total = len(res_df)
        wins = len(res_df[res_df["result"] == "WON"])
        losses = len(res_df[res_df["result"] == "LOST"])
        roi = None
        # compute simple ROI if stakes and wins known
        try:
            res_df["stake"] = pd.to_numeric(res_df["stake"], errors='coerce').fillna(0.0)
            # assume payout equal to stake * (1 + implied avg ROI) — impossible to compute without odds; skip ROI accuracy
            roi = None
        except:
            roi = None
        st.subheader("All-time Record")
        st.write(f"Total resolved bets: {total} — Wins: {wins} — Losses: {losses}")
else:
    st.write("No bets recorded yet. Use the 'Record Selected Bets' button above to add bets.")

# -------------------------
# Extras: Injury / Weather Hooks (placeholders)
# -------------------------
st.header("Injury & Weather (hooks)")
st.info("This area is a placeholder for future integration. You can paste API keys and enable hooks later.")
with st.expander("Injury / Weather Settings (placeholder)"):
    st.text_input("Weather API Key (paste here when available)", key="weather_key")
    st.text_input("Injury API Key (paste here when available)", key="injury_key")
    st.write("When an API is connected, the app will fetch game weather and injury alerts and show them in the game table.")

# -------------------------
# Instructions / Help
# -------------------------
with st.expander("How to use this app — Quick Instructions"):
    st.markdown("""
    **Quick Start**
    1. Use the sidebar to pick sport, set bankroll, choose stake method (flat or Kelly), and filters.
    2. The app fetches live odds (Moneyline, Spread, Totals). If some market types are not available for a sport, a fallback is used.
    3. Review the **Recommended Value Bets** table. Green = high edge, yellow = moderate, red = low/negative.
    4. Select the recommendations you actually placed using the multiselect, then click **Record Selected Bets**. This logs them to `bets_log.csv`.
    5. When results come in, go to **Bet Tracker**, select pending bets and mark them **WON** or **LOST**. This records them to `results.csv` and updates the all-time record.
    6. Use **Download recommendations CSV** to save current picks.

    **Files saved on the server**
    - `bets_log.csv` — all bets you recorded (pending + marked)
    - `results.csv` — resolved bets (WON / LOST)
    - You can download these from the app or retrieve them from your Streamlit Cloud app storage (if available).

    **Notes & Tips**
    - This app is a simulator/tracker only. It does not place real bets.
    - Edge calculations are simplified to keep the app reliable and fast. For higher accuracy, we can integrate historical team stats, weather, and injury feeds.
    - If a sport returns no markets in combined mode, the app automatically tries reduced market sets so it keeps working.
    """)

st.success("v2.1 loaded. Read the instructions if you need help.")