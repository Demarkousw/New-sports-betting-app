# App.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("NFL Betting App — Live Odds + ML / Spread / O/U Recommendations")

# -------------------------
# Sidebar: settings
# -------------------------
st.sidebar.header("Settings")
bankroll = st.sidebar.number_input("Bankroll ($)", min_value=0, value=1000, step=50)
fractional_kelly = st.sidebar.slider("Fractional Kelly", 0.0, 1.0, 0.25, step=0.05)
min_edge_pct = st.sidebar.slider("Minimum Edge % to show", 0.0, 50.0, 1.0, step=0.5)
lookback_weeks = st.sidebar.number_input("O/U model lookback (weeks)", min_value=1, max_value=12, value=4)
use_team_stats = st.sidebar.checkbox("Use nfl_data_py team performance (recommended)", value=True)

# -------------------------
# API & markets
# -------------------------
API_KEY = "8a264564e3a5d2a556d475e547e1c417"
SPORT = "americanfootball_nfl"
MARKETS = "h2h,spreads,totals"  # ask for all markets

st.info("Fetching odds and building recommendations...")

# -------------------------
# Try to import nfl_data_py for team weekly stats
# -------------------------
nfl_stats_available = False
if use_team_stats:
    try:
        import nfl_data_py as nfl
        nfl_stats_available = True
    except Exception as e:
        st.warning("nfl_data_py not available — O/U model will use fallback averages. "
                   "To enable stronger O/U predictions, add 'nfl_data_py' to requirements.txt.")
        nfl_stats_available = False

# -------------------------
# Helper: fetch odds safely (with fallback if combined markets cause issues)
# -------------------------
def fetch_odds_with_fallback():
    base_url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    # try full markets first
    params = {"apiKey": API_KEY, "regions": "us", "markets": MARKETS}
    try:
        r = requests.get(base_url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        # If 422 or similar, try smaller requests
        st.warning(f"Full markets request failed ({e}). Trying fallback market requests...")
        for m in ["h2h,spreads", "h2h,totals", "h2h", "spreads", "totals"]:
            try:
                r = requests.get(base_url, params={"apiKey": API_KEY, "regions":"us", "markets": m}, timeout=15)
                r.raise_for_status()
                st.info(f"Using markets='{m}' (fallback).")
                return r.json()
            except Exception:
                continue
        # final fail
        st.error("Unable to fetch odds from the API (all market combos failed).")
        return []

data = fetch_odds_with_fallback()
if not data:
    st.stop()

# -------------------------
# Convert API JSON into DataFrame with unified fields
# -------------------------
games = []
for game in data:
    home = game.get("home_team")
    away = game.get("away_team")
    # convert time safely
    ct = game.get("commence_time")
    try:
        game_time = datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except Exception:
        game_time = ct
    # initialize
    ml_home = ml_away = None
    spread_home = spread_away = None
    total_over = total_under = None

    # pick first bookmaker available (common approach)
    bookmakers = game.get("bookmakers") or []
    if bookmakers:
        markets = bookmakers[0].get("markets") or []
        for m in markets:
            key = m.get("key")
            outcomes = m.get("outcomes") or []
            if key == "h2h" and len(outcomes) >= 2:
                # outcomes ordering can vary by bookmaker; use team names to assign if available
                # many providers use outcomes[0]['name'] matching team name
                try:
                    # find by team name
                    names = [o.get("name","") for o in outcomes]
                    # map to home/away if possible
                    if home in names and away in names:
                        # match positions
                        if outcomes[0].get("name") == home:
                            ml_home = outcomes[0].get("price")
                            ml_away = outcomes[1].get("price")
                        else:
                            ml_home = outcomes[1].get("price")
                            ml_away = outcomes[0].get("price")
                    else:
                        # fallback: assign first outcome to home, second to away (common)
                        ml_home = outcomes[0].get("price")
                        ml_away = outcomes[1].get("price")
                except Exception:
                    ml_home = outcomes[0].get("price")
                    ml_away = outcomes[1].get("price")
            elif key == "spreads" and len(outcomes) >= 2:
                # outcomes usually have 'point' and 'name'
                try:
                    # assign by team name if possible
                    if outcomes[0].get("name") == home or home in outcomes[0].get("name",""):
                        spread_home = outcomes[0].get("point")
                        spread_away = outcomes[1].get("point")
                    else:
                        spread_home = outcomes[1].get("point")
                        spread_away = outcomes[0].get("point")
                except Exception:
                    spread_home = outcomes[0].get("point")
                    spread_away = outcomes[1].get("point")
            elif key == "totals" and len(outcomes) >= 2:
                # totals often come as one number (point) repeated for over/under
                # We'll use the 'point' value (same for over/under)
                try:
                    total_over = outcomes[0].get("point")
                    total_under = outcomes[1].get("point")
                except Exception:
                    total_over = total_under = None

    games.append({
        "home": home,
        "away": away,
        "game_time": game_time,
        "ml_home": ml_home,
        "ml_away": ml_away,
        "spread_home": spread_home,
        "spread_away": spread_away,
        "total_over": total_over,
        "total_under": total_under
    })

df = pd.DataFrame(games)

# Show games wide table (left)
st.subheader("All Upcoming Games & Lines")
st.dataframe(df)

# -------------------------
# Get team weekly scoring from nfl_data_py (if available)
# -------------------------
team_stats = None
if nfl_stats_available:
    try:
        # import weekly data for current season(s)
        current_year = datetime.utcnow().year
        # nfl.import_weekly_data returns weekly game-level stats — function name comes from package docs
        weekly = nfl.import_weekly_data([current_year])  # may raise if function not present
        # expected columns: 'team', 'week', 'points_for', 'points_against' or similar
        # We'll try to create a table of recent points scored and allowed by team
        # normalize column names (best effort)
        col_candidates = weekly.columns.tolist()
        # find likely points-for and points-against column names
        pf_col = next((c for c in col_candidates if c.lower().startswith('points') or 'points' in c.lower() and 'for' in c.lower()), None)
        if not pf_col:
            pf_col = next((c for c in col_candidates if c.lower().endswith('pts') or 'team_score' in c.lower()), None)
        pa_col = next((c for c in col_candidates if ('against' in c.lower() or 'opp' in c.lower() or 'allow' in c.lower()) and ('points' in c.lower() or 'pts' in c.lower())), None)
        # fallback common names used: 'team', 'week', 'points_for', 'points_against'
        if 'team' in col_candidates and 'week' in col_candidates:
            # compute per-team recent averages using available score columns
            if 'points_for' in col_candidates and 'points_against' in col_candidates:
                weekly_small = weekly[['team','week','points_for','points_against']].copy()
                weekly_small.rename(columns={'points_for':'pf','points_against':'pa'}, inplace=True)
            else:
                # attempt to find generic scoring columns
                # try common names
                possible_pf = next((c for c in col_candidates if 'points' in c.lower() and 'for' in c.lower()), None)
                possible_pa = next((c for c in col_candidates if 'points' in c.lower() and 'against' in c.lower()), None)
                if possible_pf and possible_pa:
                    weekly_small = weekly[['team','week',possible_pf,possible_pa]].copy()
                    weekly_small.columns = ['team','week','pf','pa']
                else:
                    # if we cannot find scoring columns, disable advanced mode
                    st.warning("Could not find points-for/against columns in nfl_data_py weekly data; falling back.")
                    nfl_stats_available = False
                    weekly_small = None
            if nfl_stats_available and weekly_small is not None:
                team_stats = weekly_small.copy()
        else:
            st.warning("nfl_data_py data format unexpected; falling back to simple model.")
            nfl_stats_available = False
    except Exception as e:
        st.warning(f"Failed to load team weekly stats from nfl_data_py (error: {e}). Falling back to simple averages.")
        nfl_stats_available = False

# -------------------------
# Build simple fallback team stats from last N games (if no nfl_data_py)
# We'll approximate using: if no historical data available, we'll use league-average points
# -------------------------
league_avg_total = 45  # default average total points (fallback)
team_recent = {}  # mapping team -> (avg_points_for, avg_points_against)

if nfl_stats_available and team_stats is not None:
    # compute rolling averages over lookback_weeks for each team
    now_week = team_stats['week'].max()
    for team in team_stats['team'].unique():
        team_df = team_stats[team_stats['team'] == team].sort_values('week', ascending=False)
        recent = team_df.head(lookback_weeks)
        if recent.shape[0] >= 1:
            avg_pf = recent['pf'].mean()
            avg_pa = recent['pa'].mean()
            team_recent[team] = (avg_pf, avg_pa)
else:
    # fallback: use league averages derived from recent games in 'data' if any scores present (rare)
    # Without historical scores we will estimate expected total from the market total directly
    team_recent = {}

# -------------------------
# Helper: compute expected total for a matchup
# Approach:
#  - If we have team_recent (pf, pa) for both teams -> use average of (home_pf + away_pf) adjusted by opponent pa
#  - Else fallback to using market total (if present) or league average
# -------------------------
def expected_total_from_stats(home, away):
    # if stats available for both teams:
    if home in team_recent and away in team_recent:
        home_pf, home_pa = team_recent[home]
        away_pf, away_pa = team_recent[away]
        # simple model: expected team points = (team_pf + opponent_pa) / 2
        exp_home = (home_pf + away_pa) / 2
        exp_away = (away_pf + home_pa) / 2
        return exp_home + exp_away
    # fallback: return None to signal no stat-based prediction
    return None

# -------------------------
# Convert odds to implied probability helper
# -------------------------
def odds_implied_prob(odds):
    if odds is None:
        return None
    try:
        odds = float(odds)
    except Exception:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return -odds / (-odds + 100)

# -------------------------
# Build recommendations combining ML/spread/OU edges and O/U prediction
# -------------------------
recommendations = []
for i, row in df.iterrows():
    home = row['home']
    away = row['away']
    market_total = row['total_over'] or row['total_under'] or None

    # implied probabilities for ML (simple)
    ml_home_prob = odds_implied_prob(row['ml_home'])
    ml_away_prob = odds_implied_prob(row['ml_away'])

    # Edge estimate approach:
    # - For ML: edge = model_prob - implied_prob
    # - For spread: since we don't have model spread, we'll approximate based on ML-implied or 0
    # - For O/U: compare model expected total to market_total
    edges = {}

    # ML edges: (very simple) assume fair coin 50% unless we have a model; so edge = 0.5 - implied (positive only if implied < 0.5)
    edges['ML Home'] = 0.5 - (ml_home_prob or 0.5)
    edges['ML Away'] = 0.5 - (ml_away_prob or 0.5)

    # Spread edges placeholder: derived from imbalance between implied ml probabilities (not perfect)
    # If implied ml favors home strongly, we expect home - away margin; try to convert ml odds to margin (simple mapping)
    def ml_to_margin(p_home, p_away):
        # crude mapping: margin proportional to log-odds difference
        if p_home is None or p_away is None or p_home<=0 or p_away<=0:
            return 0
        import math
        logodds = math.log(p_home/(1-p_home)) - math.log(p_away/(1-p_away))
        # scale factor to map to points (tuned by experience) — small factor to avoid huge numbers
        return logodds * 7.0

    p_home = ml_home_prob or 0.5
    p_away = ml_away_prob or 0.5
    predicted_margin = ml_to_margin(p_home, p_away)

    # if spread available, edge = predicted_margin - market_spread (positive means model predicts home by more than market)
    try:
        market_spread_home = float(row['spread_home']) if row['spread_home'] is not None else None
    except Exception:
        market_spread_home = None
    # edge for home spread: predicted_margin - market_spread_home
    edges['Spread Home'] = (predicted_margin - market_spread_home) if market_spread_home is not None else 0
    edges['Spread Away'] = (-predicted_margin - (row['spread_away'] or 0)) if row['spread_away'] is not None else 0

    # O/U edges:
    ou_model = expected_total_from_stats(home, away)
    if ou_model is None:
        # fallback: use implied total (market_total) as model (so edge = 0)
        ou_edge_over = 0
        ou_edge_under = 0
    else:
        if market_total is not None:
            # if model > market -> over positive
            ou_edge_over = ou_model - market_total
            ou_edge_under = market_total - ou_model
        else:
            ou_edge_over = ou_edge_under = 0

    edges['Over'] = ou_edge_over
    edges['Under'] = ou_edge_under

    # choose best edge
    best = max(edges, key=edges.get)
    best_edge = edges[best]
    stake = bankroll * fractional_kelly * max(0, best_edge)

    # Make readable bet type and selection
    if best.startswith("ML"):
        if "Home" in best:
            selection = home
            opponent = away
            bet_type = "Moneyline"
        else:
            selection = away
            opponent = home
            bet_type = "Moneyline"
    elif best.startswith("Spread"):
        if "Home" in best:
            selection = f"{home} - spread"
            opponent = away
            bet_type = "Spread"
        else:
            selection = f"{away} - spread"
            opponent = home
            bet_type = "Spread"
    else:
        # Over/Under
        bet_type = "Totals"
        selection = best  # 'Over' or 'Under'
        opponent = f"{away} @ {home}"

    # Only add if edge percent meets threshold
    edge_pct = best_edge * 100
    if edge_pct >= min_edge_pct:
        recommendations.append({
            "Matchup": f"{away} @ {home}",
            "Game Time": row['game_time'],
            "Bet Type": bet_type,
            "Selection": selection,
            "Opponent": opponent,
            "Edge %": round(edge_pct, 2),
            "Stake $": round(stake, 2),
            "Market Total": market_total,
            "Model Total": round(ou_model,2) if ou_model is not None else None
        })

# show recommended bets table
st.subheader("Recommended Value Bets (sorted by Edge %)")
if recommendations:
    rec_df = pd.DataFrame(recommendations).sort_values(by="Edge %", ascending=False)
    st.dataframe(rec_df)
else:
    st.write("No bets meet the minimum edge threshold.")

# Save log
try:
    log_file = "bets_log.csv"
    existing = pd.read_csv(log_file)
    updated = pd.concat([existing, pd.DataFrame(recommendations)], ignore_index=True)
    updated.to_csv(log_file, index=False)
except FileNotFoundError:
    pd.DataFrame(recommendations).to_csv("bets_log.csv", index=False)
except Exception:
    # don't crash the app on logging errors
    pass

st.success("Done — app produced recommendations.")