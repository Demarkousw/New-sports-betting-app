# ultimate_sports_betting_assistant.py
import random
from itertools import combinations
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ------------------------
# Data Setup
# ------------------------
NFL_games = [
    {"team1": "Cowboys", "team2": "Eagles", "ml1": +180, "ml2": -200, "spread1": -3, "spread2": +3, "ou": 45.5},
    {"team1": "Packers", "team2": "Bears", "ml1": -150, "ml2": +130, "spread1": -4, "spread2": +4, "ou": 42.0},
]

NCAA_games = [
    {"team1": "Ohio St", "team2": "Michigan", "ml1": -200, "ml2": +170, "spread1": -6, "spread2": +6, "ou": 52.0},
    {"team1": "Alabama", "team2": "LSU", "ml1": -250, "ml2": +210, "spread1": -7, "spread2": +7, "ou": 48.0},
]

MLB_games = [
    {"team1": "Yankees", "team2": "Red Sox", "ml1": -120, "ml2": +110},
    {"team1": "Dodgers", "team2": "Giants", "ml1": -150, "ml2": +130},
]

Fantasy_NFL_players = [
    {"player": "Patrick Mahomes", "stat": "Passing Yards", "projection": 320.5},
    {"player": "Justin Jefferson", "stat": "Rec Yards", "projection": 110.5},
    {"player": "Derrick Henry", "stat": "Rushing Yards", "projection": 95.0},
]

# ------------------------
# Core Functions
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
        team = random.choice(["team1", "team2"])
        return {"type": "ML", "team": game[team], "value": game[f"ml{1 if team=='team1' else 2}"]}
    elif pick_type == "Spread":
        if "spread1" not in game:
            return select_pick(game)
        team = random.choice(["team1", "team2"])
        return {"type": "Spread", "team": game[team], "value": game[f"spread{1 if team=='team1' else 2}"]}
    elif pick_type == "OU" and "ou" in game:
        side = random.choice(["Over", "Under"])
        return {"type": "OU", "value": f"{side} {game['ou']}"}
    else:
        return select_pick(game)

def generate_recommended_parlays(all_games, min_pick=3, max_pick=8, stake=100, display_count=5):
    parlays = []
    for pick_count in range(min_pick, max_pick + 1):
        combos = list(combinations(all_games, pick_count))
        top_combos = sorted(combos, key=lambda x: sum(calculate_probability(g["ml1"]) for g in x), reverse=True)[:display_count]
        for combo in top_combos:
            parlay = [select_pick(g) for g in combo]
            payout = calculate_parlay_payout(parlay, stake)
            parlays.append({"parlay": parlay, "payout": payout})
    return parlays

def generate_random_cross_sport_parlays(NFL, NCAA, MLB, num_parlays=5, stake=100):
    parlays = []
    for _ in range(num_parlays):
        picks = [
            select_pick(random.choice(NFL)),
            select_pick(random.choice(NCAA)),
            select_pick(random.choice(MLB))
        ]
        payout = calculate_parlay_payout(picks, stake)
        parlays.append({"parlay": picks, "payout": payout})
    return parlays

def generate_fantasy_recommendations(players):
    stat_avg = {"Passing Yards": 280, "Rec Yards": 95, "Rushing Yards": 80}
    recommendations = []
    for player in players:
        rec = "Over" if player["projection"] > stat_avg.get(player["stat"], 100) else "Under"
        recommendations.append({**player, "recommendation": rec})
    return recommendations

def format_parlay_text(parlay):
    text = ""
    for pick in parlay:
        team = pick.get("team", "")
        text += f"{pick['type']} | {team} | {pick['value']}\n"
    return text

def format_parlay_html(parlay):
    html_text = ""
    for pick in parlay:
        team = pick.get("team","")
        if pick["type"] == "ML":
            prob = calculate_probability(pick["value"])
            color = "green" if prob >= 0.6 else "red"
        else:
            color = "orange"
        html_text += f"<span style='color:{color}'>{pick['type']} | {team} | {pick['value']}</span><br>"
    return html_text

def copy_button(parlay_text, key):
    js = f"""
    <script>
    function copyToClipboard{key}() {{
        navigator.clipboard.writeText(`{parlay_text}`);
        alert('Parlay copied to clipboard!');
    }}
    </script>
    <button onclick="copyToClipboard{key}()">Copy Parlay</button>
    """
    components.html(js, height=50)

# ------------------------
# Streamlit Dashboard
# ------------------------
st.set_page_config(page_title="Ultimate Sports Betting Assistant", layout="wide")
st.title("🏈 Ultimate Sports Betting Assistant")

# Inputs
stake = st.number_input("Stake per Parlay ($):", min_value=1, value=100, step=10)
num_random = st.number_input("Number of Random Cross-Sport Parlays:", min_value=1, value=5)
display_count = st.number_input("Top Recommended Parlays to Display:", min_value=1, value=5)

st.markdown("---")

# Tabs for sections
tabs = st.tabs(["All Games", "Recommended Parlays", "Random Cross-Sport Parlays", "Fantasy NFL", "Win/Loss Tracker"])

# ------------------------
# Tab 1: All Games
with tabs[0]:
    st.subheader("NFL Games")
    st.table(pd.DataFrame(NFL_games))
    st.subheader("NCAA Games")
    st.table(pd.DataFrame(NCAA_games))
    st.subheader("MLB Games")
    st.table(pd.DataFrame(MLB_games))

# ------------------------
# Tab 2: Recommended Parlays
with tabs[1]:
    if st.button("Generate Recommended Parlays", key="rec"):
        all_games = NFL_games + NCAA_games + MLB_games
        recommended = generate_recommended_parlays(all_games, stake=stake, display_count=display_count)
        st.subheader("✅ Recommended Parlays")
        for idx, p in enumerate(recommended[:display_count]):
            st.markdown(f"**Parlay {idx+1}:**", unsafe_allow_html=True)
            st.markdown(format_parlay_html(p["parlay"]), unsafe_allow_html=True)
            st.write(f"**Potential Payout:** ${p['payout']}")
            copy_button(format_parlay_text(p["parlay"]), key=f"rec{idx}")

# ------------------------
# Tab 3: Random Cross-Sport Parlays
with tabs[2]:
    if st.button("Generate Random Cross-Sport Parlays", key="rand"):
        random_parlays = generate_random_cross_sport_parlays(NFL_games, NCAA_games, MLB_games, num_parlays=num_random, stake=stake)
        st.subheader("🎲 Random Cross-Sport Parlays")
        for idx, p in enumerate(random_parlays):
            st.markdown(f"**Parlay {idx+1}:**", unsafe_allow_html=True)
            st.markdown(format_parlay_html(p["parlay"]), unsafe_allow_html=True)
            st.write(f"**Potential Payout:** ${p['payout']}")
            copy_button(format_parlay_text(p["parlay"]), key=f"rand{idx}")

# ------------------------
# Tab 4: Fantasy NFL
with tabs[3]:
    if st.button("Generate Fantasy NFL Recommendations", key="fantasy"):
        fantasy_recs = generate_fantasy_recommendations(Fantasy_NFL_players)
        st.subheader("🏆 Fantasy NFL Recommendations")
        for f in fantasy_recs:
            color = "green" if f["recommendation"]=="Over" else "red"
            st.markdown(f"<span style='color:{color}'>{f['player']} | {f['stat']} {f['projection']} | {f['recommendation']}</span>", unsafe_allow_html=True)

# ------------------------
# Tab 5: Win/Loss Tracker
with tabs[4]:
    st.subheader("Parlay Win/Loss Tracker")
    if "tracker" not in st.session_state:
        st.session_state["tracker"] = pd.DataFrame(columns=["Parlay", "Stake", "Payout", "Result"])
    st.dataframe(st.session_state["tracker"], use_container_width=True)
    
    st.markdown("**Add Parlay Result:**")
    parlay_input = st.text_area("Parlay Text")
    stake_input = st.number_input("Stake ($)", min_value=1, value=100, step=10, key="tracker_stake")
    payout_input = st.number_input("Potential Payout ($)", min_value=1, value=100, step=10, key="tracker_payout")
    result_input = st.selectbox("Result", ["Win", "Loss"], key="tracker_result")
    
    if st.button("Add Result", key="add_result"):
        new_entry = {"Parlay": parlay_input, "Stake": stake_input, "Payout": payout_input, "Result": result_input}
        st.session_state["tracker"] = pd.concat([st.session_state["tracker"], pd.DataFrame([new_entry])], ignore_index=True)
        st.success("Result added!")