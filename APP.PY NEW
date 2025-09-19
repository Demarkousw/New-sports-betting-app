import random
from itertools import combinations
import tkinter as tk
from tkinter import ttk, scrolledtext

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
            total_multiplier *= 1.91  # Spread/OU assumed -110
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

# ------------------------
# GUI Setup
# ------------------------
def run_dashboard():
    stake = float(stake_entry.get())
    num_random = int(random_entry.get())
    display_count = int(display_entry.get())

    all_games = NFL_games + NCAA_games + MLB_games
    output_box.delete('1.0', tk.END)

    # Recommended Parlays
    recommended = generate_recommended_parlays(all_games, stake=stake, display_count=display_count)
    output_box.insert(tk.END, "=== Recommended Parlays ===\n")
    for idx, p in enumerate(recommended[:display_count]):
        output_box.insert(tk.END, f"Parlay {idx+1}:\n")
        for pick in p["parlay"]:
            output_box.insert(tk.END, f"  {pick['type']} | {pick.get('team','')} | {pick['value']}\n")
        output_box.insert(tk.END, f"  Potential Payout: ${p['payout']}\n\n")

    # Random Cross-Sport Parlays
    random_parlays = generate_random_cross_sport_parlays(NFL_games, NCAA_games, MLB_games, num_parlays=num_random, stake=stake)
    output_box.insert(tk.END, "=== Random Cross-Sport Parlays ===\n")
    for idx, p in enumerate(random_parlays):
        output_box.insert(tk.END, f"Parlay {idx+1}:\n")
        for pick in p["parlay"]:
            output_box.insert(tk.END, f"  {pick['type']} | {pick.get('team','')} | {pick['value']}\n")
        output_box.insert(tk.END, f"  Potential Payout: ${p['payout']}\n\n")

    # Fantasy NFL Recommendations
    fantasy_recs = generate_fantasy_recommendations(Fantasy_NFL_players)
    output_box.insert(tk.END, "=== Fantasy NFL Recommendations ===\n")
    for f in fantasy_recs:
        output_box.insert(tk.END, f"{f['player']} | {f['stat']} {f['projection']} | {f['recommendation']}\n")

# ------------------------
# Tkinter Widgets
# ------------------------
root = tk.Tk()
root.title("Sports Betting Assistant v2.5")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

ttk.Label(frame, text="Stake ($):").grid(row=0, column=0, sticky=tk.W)
stake_entry = ttk.Entry(frame)
stake_entry.grid(row=0, column=1)
stake_entry.insert(0, "100")

ttk.Label(frame, text="Number of Random Parlays:").grid(row=1, column=0, sticky=tk.W)
random_entry = ttk.Entry(frame)
random_entry.grid(row=1, column=1)
random_entry.insert(0, "5")

ttk.Label(frame, text="Top Recommended Parlays to Display:").grid(row=2, column=0, sticky=tk.W)
display_entry = ttk.Entry(frame)
display_entry.grid(row=2, column=1)
display_entry.insert(0, "5")

run_button = ttk.Button(frame, text="Generate Dashboard", command=run_dashboard)
run_button.grid(row=3, column=0, columnspan=2, pady=10)

output_box = scrolledtext.ScrolledText(frame, width=80, height=30)
output_box.grid(row=4, column=0, columnspan=2)

root.mainloop()