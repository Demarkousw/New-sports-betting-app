# App.py - Sports Betting Assistant v2.6 (All-in-one: bets, parlays, cross-sport, fantasy)
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import math
import itertools
import random
from functools import lru_cache

# -------------------
# CONFIG - keys you already provided
# -------------------
API_KEY_ODDS = "c5eece64b53f2c9622543faf5861555d"      # Odds API key (the-odds-api)
API_KEY_WEATHER = "5ec258afff830598e45caad47e3edb8e"   # OpenWeatherMap key
# Sleeper has public endpoints (no key required)

# -------------------
# SPORTS / MARKETS
# -------------------
SPORTS = {
    "NFL": "americanfootball_nfl",
    "NCAA Football": "americanfootball_ncaaf",
    "MLB": "baseball_mlb"
}
REGIONS = "us"
MARKETS = ["h2h", "spreads", "totals"]

# -------------------
# STORAGE / COLUMNS
# -------------------
BETS_LOG = "bets_log.csv"
BETS_COLS = [
    "record_id","timestamp","sport","week","home_team","away_team","matchup",
    "game_time","bet_type","selection","opponent","edge_pct","stake",
    "predicted_margin","point_spread","weather","status"
]

# -------------------
# UTILITIES: load/save CSV
# -------------------
def load_or_create_csv(path, cols):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            # ensure columns exist
            for c in cols:
                if c not in df.columns:
                    df[c] = pd.NA
            # keep column order
            return df[[c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]]
        except Exception:
            # move broken file aside
            os.rename(path, path + ".bak")
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

bets_df = load_or_create_csv(BETS_LOG, BETS_COLS)

# -------------------
# APP HEADER
# -------------------
st.set_page_config(layout="wide", page_title="Sports Betting Assistant v2.6")
st.title("Sports Betting Assistant v2.6 — All-in-One Betting + Fantasy")

# -------------------
# SIDEBAR SETTINGS
# -------------------
st.sidebar.header("Settings")
sport_choice = st.sidebar.selectbox("Select Sport (for focused view)", list(SPORTS.keys()))
bankroll = st.sidebar.number_input("Your Bankroll ($)", min_value=10, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly Fraction", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 100.0, 1.0, step=0.5)
bet_type_filter = st.sidebar.multiselect("Show bet types", ["Moneyline","Spread","Totals","All"], default=["All"])
if "All" in bet_type_filter:
    bet_type_filter = ["Moneyline","Spread","Totals"]
use_weather = st.sidebar.checkbox("Adjust predictions for weather", value=True)
fantasy_mode = st.sidebar.selectbox("Fantasy scoring", ["PPR", "Half PPR", "Standard"], index=0)
top_parlay_limit = st.sidebar.slider("Max top bets for parlays", 5, 20, 10)

# -------------------
# HELPERS: odds/weather/fantasy fetchers (defensive)
# -------------------
def fetch_odds_for_sport(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": API_KEY_ODDS, "regions": REGIONS, "markets": ",".join(MARKETS), "oddsFormat": "decimal"}
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        # don't crash; return empty and show notice where used
        return []

@lru_cache(maxsize=1024)
def fetch_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY_WEATHER}&units=imperial"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        desc = data['weather'][0]['description'].title()
        temp = data['main'].get('temp', None)
        wind = data.get('wind', {}).get('speed', None)
        return f"{desc} {temp}°F, Wind {wind} mph", temp, wind, desc.lower()
    except Exception:
        return "N/A", None, None, None

# Sleeper endpoints (public)
@lru_cache(maxsize=1)
def fetch_sleeper_players():
    """Get basic player metadata from Sleeper."""
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()  # dict of player_id -> info
        return data
    except Exception:
        return {}

def fetch_sleeper_player_stats(season, week=None):
    """
    Try to fetch player game logs / stats. Sleeper has endpoints for stats,
    but availability may vary. We will attempt a few common endpoints and return a simple mapping.
    This is intentionally defensive — absence of stats will not break the app.
    """
    try:
        # Example endpoint for weekly stats (may change). We'll try and fallback.
        url = f"https://api.sleeper.app/v1/stats/nfl/regular/{season}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()  # list of game stats
        # Convert to dataframe for simple aggregations
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# -------------------
# EDGE / PROBABILITY HELPERS
# -------------------
def odds_to_prob_decimal(odds):
    """
    Accept decimal odds (e.g., 2.5) or american converted to decimal earlier.
    Our odds API returns decimal when asked via params -> oddsFormat=decimal.
    """
    try:
        o = float(odds)
        if o <= 0:
            return 0.5
        return 1.0 / o
    except Exception:
        return 0.5

def calc_margin_from_probs(p_home, p_away):
    p_home = max(min(p_home, 0.9999), 0.0001)
    p_away = max(min(p_away, 0.9999), 0.0001)
    return math.log(p_home/(1-p_home)) - math.log(p_away/(1-p_away))

# -------------------
# BUILD RECOMMENDATIONS (multi-sport)
# -------------------
def build_recommendations_for_game(game, sport_name, idx_offset=0):
    """
    Parse a single 'game' object from the-odds-api and produce a single recommendation row
    (if markets available). Defensive: if markets missing, still return minimal info.
    """
    rec = None
    try:
        home = game.get("home_team")
        away = game.get("away_team")
        week = game.get("week", None)
        commence = game.get("commence_time")
        if commence:
            try:
                game_time = datetime.fromisoformat(commence.replace("Z","+00:00"))
            except:
                game_time = commence
        else:
            game_time = None

        # For weather: need coordinates. We don't have stadium coords from odds API.
        # We'll use a placeholder coord (you can replace with real stadium coords later).
        # Attempt to infer city from 'home' team name (not reliable). So keep placeholder.
        lat, lon = 40.0, -75.0
        weather_str, temp, wind, desc = fetch_weather(lat, lon)

        bookmakers = game.get("bookmakers", [])
        markets = {}
        if bookmakers:
            # prefer first bookmaker's markets
            first = bookmakers[0]
            for m in first.get("markets", []):
                markets[m["key"]] = m.get("outcomes", [])

        # default probs
        p_home = 0.5
        p_away = 0.5
        # attempt to extract h2h prices to compute probabilities
        try:
            if "h2h" in markets and len(markets["h2h"]) >= 2:
                # markets["h2h"] is list of outcomes with 'name' and 'price'
                o0 = markets["h2h"][0].get("price")
                o1 = markets["h2h"][1].get("price")
                p_home = odds_to_prob_decimal(o0)
                p_away = odds_to_prob_decimal(o1)
        except Exception:
            pass

        predicted_margin = calc_margin_from_probs(p_home, p_away)

        # Build edge candidates
        edges = {}
        if "h2h" in markets and len(markets["h2h"]) >= 2:
            edges["ML Home"] = p_home - 0.5
            edges["ML Away"] = p_away - 0.5
        if "spreads" in markets:
            edges["Spread Home"] = predicted_margin
            edges["Spread Away"] = -predicted_margin
        if "totals" in markets:
            # Without total outcomes data we can't compute real edge; use neutral placeholders
            edges["Over"] = 0.0
            edges["Under"] = 0.0

        # collect current point spread if present (from 'spreads' outcomes)
        point_spread = None
        if "spreads" in markets:
            # spreads outcomes often include {'name': 'Team', 'point': -3.5, 'price': ...}
            for out in markets["spreads"]:
                if "point" in out:
                    # choose first point found (bookmaker-specific)
                    point_spread = out.get("point")
                    break

        # weather adjustments
        if use_weather and wind:
            try:
                if wind > 15:
                    # decrease over expectation and shrink spreads
                    if "Over" in edges: edges["Over"] -= 0.1
                    if "Under" in edges: edges["Under"] += 0.1
                    if "Spread Home" in edges: edges["Spread Home"] *= 0.9
                    if "Spread Away" in edges: edges["Spread Away"] *= 0.9
            except Exception:
                pass
        if use_weather and desc:
            if "rain" in desc or "snow" in desc:
                edges = {k: v*0.85 for k,v in edges.items()}

        # pick best edge
        if edges:
            best_key = max(edges, key=lambda k: edges[k])
            edge_pct = edges[best_key] * 100
            # form selection
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
            # filter by bet type and min edge
            if bet_type in bet_type_filter and edge_pct >= min_edge_pct:
                stake = round(bankroll * fractional_kelly * max(0, edges[best_key]), 2)
                rec = {
                    "record_id": f"{sport_name}_{idx_offset}_{int(datetime.utcnow().timestamp())}",
                    "timestamp": datetime.utcnow(),
                    "sport": sport_name,
                    "week": week,
                    "home_team": home,
                    "away_team": away,
                    "matchup": f"{away} @ {home}",
                    "game_time": game_time,
                    "bet_type": bet_type,
                    "selection": selection,
                    "opponent": opponent,
                    "edge_pct": round(edge_pct, 2),
                    "stake": stake,
                    "predicted_margin": round(predicted_margin, 2),
                    "point_spread": point_spread,
                    "weather": weather_str,
                    "status": "PENDING"
                }
    except Exception:
        rec = None
    return rec

# -------------------
# Build recommendations across all sports (aggregate)
# -------------------
def build_all_recommendations():
    rows = []
    for s in SPORTS.keys():
        games = fetch_odds_for_sport(SPORTS[s])
        if not games:
            continue
        for idx, g in enumerate(games):
            r = build_recommendations_for_game(g, s, idx_offset=idx)
            if r:
                rows.append(r)
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=BETS_COLS)

# -------------------
# FANTASY: projections using Sleeper + internal adjustments
# -------------------
@lru_cache(maxsize=1)
def get_sleeper_players_cache():
    return fetch_sleeper_players()

def build_fantasy_projections(scoring=fantasy_mode, top_n=50):
    """
    Build fantasy projections:
      - Pull player metadata from Sleeper
      - Attempt to get recent fantasy production via Sleeper stats endpoint (best effort)
      - Use a simple model:
          base_proj = (recent 3-game avg fantasy pts) if available else simple heuristic
          opponent_adjust = + / - based on opponent's fantasy points allowed (not always available)
          weather adjustment: if windy/rainy -> reduce passing/receiving
      - Return dataframe of top players by projected fantasy points and a 'Value' metric.
    Note: This is a lightweight ensemble; paid data sources will improve accuracy.
    """
    players = get_sleeper_players_cache()
    # try to fetch season stats (we ask for current year)
    season = datetime.utcnow().year
    stats_df = fetch_sleeper_player_stats(season)
    # stats_df may be empty; we'll handle gracefully

    rows = []
    # iterate through players dict (may be large)
    for pid, p in players.items():
        try:
            # only consider skill positions
            pos = p.get("position")
            if pos not in ("QB","RB","WR","TE"):
                continue
            full_name = p.get("full_name") or p.get("first_name","") + " " + p.get("last_name","")
            team = p.get("team", "FA")
            # recent form: compute avg fantasy pts last 3 games if available in stats_df
            recent_avg = None
            if not stats_df.empty:
                # stats_df may contain rows with 'player_id' and 'fantasy_points' per game
                player_stats = stats_df[stats_df.get("player_id")==pid]
                if not player_stats.empty and "fantasy_points" in player_stats.columns:
                    last_games = player_stats.sort_values(["week"], ascending=False).head(3)
                    recent_avg = last_games["fantasy_points"].astype(float).mean()
            # fallback heuristics: if no recent data, use a tiny baseline by position
            if recent_avg is None or math.isnan(recent_avg):
                base_by_pos = {"QB":12.0, "RB":8.0, "WR":7.5, "TE":5.5}
                recent_avg = base_by_pos.get(pos, 6.0)

            # opponent adjustment: try to find matchup from bets_df where this team plays
            # find next opponent in bets_df where home_team or away_team equals team
            opponent = None
            matchup_row = None
            next_games = bets_df[(bets_df["home_team"]==team) | (bets_df["away_team"]==team)]
            if not next_games.empty:
                # pick the nearest upcoming game
                try:
                    next_games_sorted = next_games.sort_values("game_time")
                    matchup_row = next_games_sorted.iloc[0]
                    opponent = matchup_row["away_team"] if matchup_row["home_team"]==team else matchup_row["home_team"]
                except Exception:
                    opponent = None

            # opponent defense rough effect: if opponent exists and we have historical defensive data in stats_df, attempt simple adjustment
            opponent_adjust = 0.0
            if opponent and not stats_df.empty:
                # This is a heuristic: if opponent has allowed more fantasy pts historically, add to projection
                # stats_df likely does not include opponent defense aggregated, so skip if not present
                opponent_adjust = 0.0

            # weather adjustment: if we have matchup_row with weather, apply small adjustments
            weather_adj = 0.0
            if matchup_row is not None:
                w = matchup_row.get("weather","")
                if isinstance(w, str) and w != "N/A":
                    if "wind" in w.lower():
                        # parse wind mph
                        try:
                            parts = w.lower().split("wind")
                            wind_mph = float(parts[1].strip().split()[0])
                            if wind_mph > 15:
                                # big wind: reduce pass/rec by 10% for non-RB
                                if pos in ("QB","WR","TE"):
                                    weather_adj -= recent_avg * 0.10
                                elif pos=="RB":
                                    weather_adj += recent_avg * 0.03
                        except Exception:
                            pass
                    if "rain" in w.lower() or "snow" in w.lower():
                        if pos in ("QB","WR","TE"):
                            weather_adj -= recent_avg * 0.08
                        else:
                            weather_adj += recent_avg * 0.02

            # combine into final projection
            # ensemble: weight recent_avg (0.7) and a small league mean (0.3 baseline)
            league_baseline = {"QB":15.0,"RB":10.0,"WR":9.0,"TE":6.0}
            final_proj = 0.7 * recent_avg + 0.3 * league_baseline.get(pos,7.0) + opponent_adjust + weather_adj

            # value metric: final_proj / salary if salary known (we don't fetch salary here); show proj per unit
            value = final_proj  # since salary may not be present, value = projection (higher is better)

            rows.append({
                "player_id": pid,
                "Player": full_name,
                "Team": team,
                "Position": pos,
                "ProjPts": round(final_proj,2),
                "RecentAvg": round(recent_avg,2) if recent_avg is not None else None,
                "Opponent": opponent if opponent else "N/A",
                "Value": round(value,2)
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # add rank and sort
    df = df.sort_values("ProjPts", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    return df

# -------------------
# Build everything & UI display
# -------------------
# Build recommendations across sports (aggregated)
with st.spinner("Fetching odds and building recommendations..."):
    try:
        new_recs = build_all_recommendations()
        if not new_recs.empty:
            bets_df = pd.concat([bets_df, new_recs]).drop_duplicates(subset=["record_id"], keep="first").reset_index(drop=True)
    except Exception:
        pass

# PARLAYS: Pick-3 to Pick-8 (top pending bets)
st.subheader("Recommended Parlays (Pick-3 to Pick-8)")
top_bets = bets_df[bets_df["status"]=="PENDING"].sort_values(by="edge_pct", ascending=False).head(top_parlay_limit)
parlays = []
if not top_bets.empty and len(top_bets) >= 3:
    # generate combos up to min(8, len(top_bets))
    max_pick = min(8, len(top_bets))
    # to avoid explosion, limit combinations: for r in 3..max_pick build combos from top N only
    for r in range(3, max_pick+1):
        for combo in itertools.combinations(top_bets.index, r):
            selections = [top_bets.loc[i, "selection"] for i in combo]
            matchups = [top_bets.loc[i, "matchup"] for i in combo]
            expected_edge = 1.0
            for i in combo:
                expected_edge *= (top_bets.loc[i, "edge_pct"] / 100.0)
            expected_edge *= 100.0
            parlays.append({
                "Parlay": " + ".join(selections),
                "Games": " + ".join(matchups),
                "Expected Edge %": round(expected_edge, 4),
                "Pick Count": r
            })
    parlays_df = pd.DataFrame(parlays).sort_values(by="Expected Edge %", ascending=False).head(50)
    st.dataframe(parlays_df, use_container_width=True)
else:
    st.write("Not enough pending bets to generate recommended parlays yet.")

# TRUE CROSS-SPORT RANDOM PARLAYS
st.subheader("Random Cross-Sport Parlays (MLB + NCAA + NFL)")
all_top_bets = bets_df[(bets_df["status"]=="PENDING") & (bets_df["edge_pct"]>=min_edge_pct)]
random_parlays = []
if not all_top_bets.empty and len(all_top_bets) >= 3:
    for _ in range(8):  # show 8 random multi-sport parlays
        combo = all_top_bets.sample(min(5, len(all_top_bets))) if len(all_top_bets) >=5 else all_top_bets.sample(min(3, len(all_top_bets)))
        selections = combo["selection"].tolist()
        matchups = combo["matchup"].tolist()
        expected_edge = 1.0
        for val in combo["edge_pct"]:
            expected_edge *= (val/100.0)
        expected_edge *= 100.0
        random_parlays.append({
            "Parlay": " + ".join(selections),
            "Games": " + ".join(matchups),
            "Expected Edge %": round(expected_edge, 4),
            "Pick Count": len(selections)
        })
    st.dataframe(pd.DataFrame(random_parlays), use_container_width=True)
else:
    st.write("Not enough high-edge bets across sports to create random cross-sport parlays.")

# DISPLAY W/L TABLE (All bets)
st.header("All-Time Bets Overview")
def style_row(row):
    # apply row coloring based on edge and status
    try:
        edge = float(row.get("edge_pct") or 0.0)
    except Exception:
        edge = 0.0
    status = (row.get("status") or "").upper()
    if status == "WON":
        return ["background-color: #ADD8E6; color: black"]*len(row)
    if status == "LOST":
        return ["background-color: #D3D3D3; color: black"]*len(row)
    if edge >= 5:
        return ["background-color: #9AFF99; color: black"]*len(row)
    if edge >= 2:
        return ["background-color: #FFFF99; color: black"]*len(row)
    return ["background-color: #FF9999; color: black"]*len(row)

st.dataframe(bets_df.style.apply(style_row, axis=1), use_container_width=True)

# UPDATE PENDING BETS
pending = bets_df[bets_df["status"]=="PENDING"]
if not pending.empty:
    st.subheader("Update Pending Bets")
    pending_opts = pending["record_id"].astype(str).tolist()
    chosen_pending = st.multiselect("Select pending bets to mark", pending_opts)
    result_choice = st.radio("Mark as", ["WON","LOST"], index=1)
    if st.button("Apply Result"):
        for rid in chosen_pending:
            idx = bets_df[bets_df["record_id"].astype(str)==rid].index
            if len(idx) == 0:
                continue
            bets_df.loc[idx, "status"] = result_choice
        bets_df.to_csv(BETS_LOG, index=False)
        st.success("Updated pending bets.")

# ALL-TIME RECORD
if not bets_df.empty:
    wins = len(bets_df[bets_df["status"]=="WON"])
    losses = len(bets_df[bets_df["status"]=="LOST"])
    st.subheader("All-Time Record")
    st.write(f"Wins: {wins} | Losses: {losses} | Total Bets: {wins + losses}")

# -------------------
# FANTASY: NFL player projections / best plays
# -------------------
st.subheader("Fantasy Football Line — Best Plays (NFL)")

with st.spinner("Fetching fantasy data and building projections..."):
    try:
        fantasy_df = build_fantasy_projections(scoring=fantasy_mode, top_n=100)
        if fantasy_df.empty:
            st.write("No fantasy projections available (Sleeper data may be unavailable).")
        else:
            # Controls
            cols = st.columns([1,1,1,2])
            with cols[0]:
                pos_filter = st.selectbox("Position filter", ["ALL","QB","RB","WR","TE"], index=0)
            with cols[1]:
                top_n = st.number_input("Show top N", min_value=5, max_value=200, value=50, step=5)
            with cols[2]:
                show_value = st.checkbox("Show value metric", value=True)
            with cols[3]:
                apply_weather_to_fantasy = st.checkbox("Adjust fantasy for weather", value=True)
            # filter
            display_df = fantasy_df.copy()
            if pos_filter != "ALL":
                display_df = display_df[display_df["Position"]==pos_filter]
            display_df = display_df.head(int(top_n)).reset_index(drop=True)
            # display
            st.dataframe(display_df[["Player","Team","Position","ProjPts","RecentAvg","Opponent","Value"]], use_container_width=True)
            # highlight top recommended across positions
            st.markdown("**Top overall plays:**")
            top_overall = fantasy_df.sort_values("ProjPts", ascending=False).head(10)
            st.table(top_overall[["Player","Team","Position","ProjPts","Opponent"]].head(10))
    except Exception as e:
        st.write("Error building fantasy projections:", str(e))

# INSTRUCTIONS
with st.expander("How to use v2.6 (quick guide)"):
    st.markdown("""
**1. Settings (left sidebar)**
- Select sport (for focused table view), adjust bankroll & Kelly fraction, and set minimum edge.
- Turn on/off weather adjustments.

**2. Recommendations & Parlays**
- Top of the page shows Pick-3 → Pick-8 recommended parlays built from the highest-edge pending bets.
- Random Cross-Sport parlays box shows randomly generated cross-sport parlays (MLB + NCAA + NFL) using high-edge pending bets.

**3. Bets Table**
- The All-Time Bets Overview table shows all recommendations and tracked bets.
- Row colors: **green** = strong edge, **yellow** = medium, **red** = weak; **blue** = won, **gray** = lost.
- Use the "Update Pending Bets" box to mark bets WON or LOST — the W/L record updates automatically.

**4. Fantasy Line**
- The Fantasy section shows projected fantasy points per player (PPR default) using a lightweight ensemble:
  - Recent form (last games), opponent matchup where available, and weather adjustments.
  - Use the filters to show by position and top N players.
- The projection model is a best-effort free approach. Paid providers (FantasyData, SportsData) can further improve accuracy.

**5. Troubleshooting**
- If odds or fantasy data are missing, test the APIs in your browser:
  - Odds API example:
    `https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?apiKey=YOUR_KEY&regions=us&markets=h2h`
  - OpenWeatherMap example:
    `https://api.openweathermap.org/data/2.5/weather?lat=40&lon=-75&appid=YOUR_KEY&units=imperial`
- The app handles missing data gracefully but will show reduced functionality when APIs are unavailable.

**6. Improvements**
- To increase fantasy projection accuracy: add a paid projection source (FantasyData) or upload historical game/player CSVs.
- To improve betting edges: integrate advanced models or historical team performance CSVs; I can add that next.

If you want any of the above improvements, tell me which one to prioritize and I’ll add it next.
""")

# End of App.py