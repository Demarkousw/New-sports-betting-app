# elo.py
import math
import pandas as pd

DEFAULT_K = 20  # adjust sensitivity

def initialize_elo(teams, base_elo=1500):
    return {team: base_elo for team in teams}

def expected_prob(elo_a, elo_b):
    """Win probability for A vs B given Elo ratings"""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))

def update_elo(elo, team_a, team_b, score_a, score_b, kfactor=DEFAULT_K):
    ea = expected_prob(elo[team_a], elo[team_b])
    eb = 1.0 - ea
    if score_a > score_b:
        sa, sb = 1.0, 0.0
    elif score_a < score_b:
        sa, sb = 0.0, 1.0
    else:
        sa, sb = 0.5, 0.5
    elo[team_a] = elo[team_a] + kfactor * (sa - ea)
    elo[team_b] = elo[team_b] + kfactor * (sb - eb)
    return elo

def build_elos_from_history(df_history, team_col_A='home_team', team_col_B='away_team',
                            scoreA_col='home_score', scoreB_col='away_score',
                            base_elo=1500, kfactor=DEFAULT_K):
    """
    df_history: pandas DataFrame with required columns:
      home_team, away_team, home_score, away_score
    Optional: date column (YYYY-MM-DD) — function sorts by date if present.
    """
    teams = pd.unique(df_history[[team_col_A, team_col_B]].values.ravel('K'))
    elos = initialize_elo(teams, base_elo=base_elo)
    if 'date' in df_history.columns:
        df_history = df_history.sort_values('date')
    for _, row in df_history.iterrows():
        tA = row[team_col_A]
        tB = row[team_col_B]
        sA = float(row[scoreA_col])
        sB = float(row[scoreB_col])
        if tA not in elos:
            elos[tA] = base_elo
        if tB not in elos:
            elos[tB] = base_elo
        update_elo(elos, tA, tB, sA, sB, kfactor=kfactor)
    return elos

# Odds helpers
def american_to_decimal(odds):
    odds = int(odds)
    if odds > 0:
        return odds / 100.0 + 1.0
    else:
        return 100.0 / abs(odds) + 1.0

def implied_prob_from_american(odds):
    d = american_to_decimal(odds)
    return 1.0 / d

def kelly_fraction(decimal_odds, p):
    b = decimal_odds - 1.0
    q = 1.0 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(kelly, 0.0)
