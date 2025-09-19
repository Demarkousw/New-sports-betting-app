# App.py - Version 2.0 (NFL, NCAAF, MLB) — live odds, recommendations, download, logging
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import math
import io

st.set_page_config(layout="wide", page_title="Betting Dashboard v2.0")
st.title("Betting Dashboard v2.0 — NFL / NCAAF / MLB")

# -------------------------
# Sidebar: global settings
# -------------------------
st.sidebar.header("Global Settings")
sport_choice = st.sidebar.selectbox("Select sport", ["NFL", "NCAA Football", "MLB"])
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000, step=50)
use_flat = st.sidebar.checkbox("Use flat stake instead of Kelly", value=False)
flat_stake = st.sidebar.number_input("Flat stake amount ($)", min_value=0, value=25, step=5)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 50.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]

# API key (you provided earlier)
API_KEY = "8a264564e3a5d2a556d475e547e1c417"

# Map sport selection to Odds API sport key and default league total
SPORT_MAP = {
    "NFL": ("americanfootball_nfl", 45.0),
    "NCAA Football": ("americanfootball_ncaaf", 56.0),
    "MLB": ("baseball_mlb", 8.5)
}
SPORT_API_KEY, league_avg_total = SPORT_MAP[sport_choice]

st.sidebar.markdown(f"**League avg total (used for O/U fallback):** {league_avg_total}")

# -------------------------
# Utility: fetch odds with fallback for market combos
# -------------------------
def fetch_odds_with_fallback(sport_api_key):
    base_url = f"https://api.the-odds-api.com/v4/sports/{sport_api_key}/odds"
    # Try the combined markets; if it fails (422) try reduced sets
    combos = ["h2h,spreads,totals", "h2h,spreads", "h2h,totals", "spreads,totals", "h2h"]
    for markets in combos:
        try:
            r = requests.get(base_url, params={"apiKey": API_KEY, "regions":"us", "markets": markets}, timeout=15)
            r.raise_for_status()
            st.info(f"Using markets: {markets}")
            return r.json()
        except requests.HTTPError as e:
            # 422 or similar for unsupported markets — try next combo
            st.warning(f"Markets '{markets}' not available or returned error: {e}")
            continue
        except Exception as e:
            st.error(f"Error fetching odds: {e}")
            return []
    return []

st.info(f"Fetching upcoming {sport_choice} odds...")
data = fetch_odds_with_fallback(SPORT_API_KEY)
if not data:
    st.error("No odds could be fetched. Check API key, the sport selection, or try again later.")
    st.stop()

# -------------------------
# Normalize API JSON -> flat DataFrame
# -------------------------
games = []
for game in data:
    home = game.get("home_team")
    away = game.get("away_team")
    ct = game.get("commence_time")
    try:
        game_time = datetime.fromisoformat(ct.replace("Z","+00:00"))
    except Exception:
        game_time = ct
    # defaults
    ml_home = ml_away = None
    spread_home = spread_away = None
    total_market = None

    # Use first bookmaker if present
    bookmakers = game.get("bookmakers") or []
    if bookmakers:
        markets = bookmakers[0].get("markets") or []
        for m in markets:
            key = m.get("key")
            outcomes = m.get("outcomes") or []
            if key == "h2h" and len(outcomes) >= 2:
                # try to map by team name if possible, else default indexing
                names = [o.get("name","") for o in outcomes]
                if home in names and away in names:
                    # find which outcome corresponds to home
                    if outcomes[0].get("name") == home:
                        ml_home = outcomes[0].get("price")
                        ml_away = outcomes[1].get("price")
                    else:
                        ml_home = outcomes[1].get("price")
                        ml_away = outcomes[0].get("price")
                else:
                    ml_home = outcomes[0].get("price")
                    ml_away = outcomes[1].get("price")
            elif key == "spreads" and len(outcomes) >= 2:
                # outcomes may label names—attempt to assign by team name
                if outcomes[0].get("name") and home in outcomes[0].get("name"):
                    spread_home = outcomes[0].get("point")
                    spread_away = outcomes[1].get("point")
                else:
                    spread_home = outcomes[0].get("point")
                    spread_away = outcomes[1].get("point")
            elif key == "totals" and len(outcomes) >= 1:
                # totals typically have point for both over/under entries (same number)
                total_market = outcomes[0].get("point")

    games.append({
        "home": home,
        "away": away,
        "game_time": game_time,
        "ml_home": ml_home,
        "ml_away": ml_away,
        "spread_home": spread_home,
        "spread_away": spread_away,
        "total_market": total_market
    })

df = pd.DataFrame(games)

# Show basic games table
st.subheader("All Upcoming Games & Market Lines")
# format time and show
if not df.empty:
    df_display = df.copy()
    df_display["game_time"] = df_display["game_time"].astype(str)
    st.dataframe(df_display)
else:
    st.write("No games available.")

# -------------------------
# Helpers: odds -> implied prob, margin mapping, etc.
# -------------------------
def odds_to_implied_prob(odds):
    """
    Convert American odds to implied probability.
    Returns a float between 0 and 1 (or None if odds None)
    """
    if odds is None:
        return None
    try:
        o = float(odds)
    except Exception:
        return None
    if o > 0:
        return 100.0 / (o + 100.0)
    else:
        return (-o) / ((-o) + 100.0)

def ml_probs_to_margin(p_home, p_away):
    """
    Convert implied probabilities to an estimated point margin.
    This is a crude mapping using log-odds scaled to points.
    """
    # avoid zeros
    p_home = max(min(p_home, 0.9999), 0.0001)
    p_away = max(min(p_away, 0.9999), 0.0001)
    # logit difference
    logit_home = math.log(p_home / (1 - p_home))
    logit_away = math.log(p_away / (1 - p_away))
    diff = logit_home - logit_away
    # scale factor chosen empirically; adjust if you want different sensitivity
    scale = 7.0
    margin = diff * scale
    return margin

# -------------------------
# Build recommendations per game
# -------------------------
recommendations = []
for i, row in df.iterrows():
    home = row["home"]
    away = row["away"]
    market_total = row["total_market"] if row["total_market"] is not None else league_avg_total

    # implied ML probabilities
    p_home = odds_to_implied_prob(row["ml_home"]) or 0.5
    p_away = odds_to_implied_prob(row["ml_away"]) or 0.5

    # predicted margin from ML implied probs
    predicted_margin = ml_probs_to_margin(p_home, p_away)  # positive => home favored by X points

    # compute model_total: base league avg adjusted slightly by predicted_margin
    # idea: if predicted_margin positive (home expected to score more), total can shift slightly
    model_total = league_avg_total + (predicted_margin * 0.05)  # 5% of margin added to league average

    # compute edges:
    # ML edge: estimate model win prob from predicted margin using logistic mapping
    # scale_factor chosen to map points to win% roughly (tuneable)
    scale_for_prob = 13.5  # larger = flatter mapping
    model_p_home = 1.0 / (1.0 + math.exp(-predicted_margin / scale_for_prob))
    model_p_away = 1.0 - model_p_home

    implied_p_home = p_home
    implied_p_away = p_away

    edge_ml_home = model_p_home - (implied_p_home or 0.5)
    edge_ml_away = model_p_away - (implied_p_away or 0.5)

    # Spread edge: model margin - market spread (we expect spread_home to be positive number if home favored by X)
    market_spread_home = row["spread_home"]
    market_spread_away = row["spread_away"]
    # Edge expressed in points; convert to crude "edge units" by dividing by 10 to map to betting stake scale
    spread_edge_home = 0
    spread_edge_away = 0
    if market_spread_home is not None:
        try:
            spread_edge_home = (predicted_margin - float(market_spread_home)) / 10.0
        except Exception:
            spread_edge_home = 0
    if market_spread_away is not None:
        try:
            # predicted margin negative from away perspective
            spread_edge_away = ((-predicted_margin) - float(market_spread_away)) / 10.0
        except Exception:
            spread_edge_away = 0

    # O/U edge: model_total - market_total (positive => Over)
    over_edge = model_total - market_total
    under_edge = market_total - model_total

    # Put into uniform "edge" metric (we'll use these to pick best)
    edges = {
        "ML Home": edge_ml_home,
        "ML Away": edge_ml_away,
        "Spread Home": spread_edge_home,
        "Spread Away": spread_edge_away,
        "Over": over_edge,
        "Under": under_edge
    }

    # pick best edge
    best_key = max(edges, key=edges.get)
    best_edge = edges[best_key]
    # Convert edge to percentage-ish for display (scale depending on metric)
    # For ML/spread we use best_edge directly (it's already in fraction for ML or small units for spread)
    # For consistency, we compute "Edge %" = best_edge * 100, but note spread edges are scaled down earlier.
    edge_pct = best_edge * 100

    # stake calculation: flat vs fractional Kelly-like
    if use_flat:
        stake = float(flat_stake)
    else:
        # ensure stake non-negative
        stake = bankroll * fractional_kelly * max(0.0, best_edge)

    # format readable bet selection
    if best_key.startswith("ML"):
        bet_type = "Moneyline"
        selection = home if "Home" in best_key else away
        opponent = away if "Home" in best_key else home
    elif best_key.startswith("Spread"):
        bet_type = "Spread"
        selection = f"{home} (home)" if "Home" in best_key else f"{away} (away)"
        opponent = away if "Home" in best_key else home
    else:
        bet_type = "Totals"
        selection = best_key  # "Over" or "Under"
        opponent = f"{away} @ {home}"

    # Apply bet type filter and min edge threshold
    if bet_type in bet_type_filter and edge_pct >= min_edge_pct:
        recommendations.append({
            "Matchup": f"{away} @ {home}",
            "Game Time": row["game_time"],
            "Bet Type": bet_type,
            "Selection": selection,
            "Opponent": opponent,
            "Edge %": round(edge_pct, 2),
            "Stake $": round(stake, 2),
            "Market Total": market_total,
            "Model Total": round(model_total, 2),
            "Predicted Margin": round(predicted_margin, 2)
        })

# -------------------------
# Display recommendations & download / logging
# -------------------------
st.subheader("Recommended Value Bets (sorted by Edge %)")
if recommendations:
    rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
    # convert datetimes to string for download display
    rec_df_display = rec_df.copy()
    rec_df_display["Game Time"] = rec_df_display["Game Time"].astype(str)
    st.dataframe(rec_df_display)

    # download button
    csv_bytes = rec_df_display.to_csv(index=False).encode("utf-8")
    st.download_button("Download recommendations CSV", data=csv_bytes, file_name="recommendations.csv", mime="text/csv")

    # append to bets_log.csv (non-fatal)
    try:
        log_file = "bets_log.csv"
        existing = pd.read_csv(log_file)
        updated = pd.concat([existing, rec_df], ignore_index=True)
        updated.to_csv(log_file, index=False)
    except FileNotFoundError:
        pd.DataFrame(recommendations).to_csv("bets_log.csv", index=False)
    except Exception:
        # don't crash on logging errors
        pass
else:
    st.write("No recommendations meet your filters (bet type / minimum edge).")

st.success("Recommendations generated.")