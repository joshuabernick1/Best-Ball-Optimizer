import streamlit as st
import pandas as pd

st.title("Best Ball Optimizer")

player_col = "Player"
pos_col = "Position"
adp_col = "ADP"


def run_simple_draft(df, random_pool, locked_picks, position_limits):
    drafted = []

    df = df.copy()
    df[adp_col] = pd.to_numeric(df[adp_col], errors="coerce")

    for round_num in range(1, 21):
        drafted_counts = pd.Series([p["Position"] for p in drafted]).value_counts().to_dict()

        if round_num in locked_picks:
            locked_name = locked_picks[round_num]
            locked_player = df[df[player_col].str.upper() == locked_name.upper()]

            if not locked_player.empty:
                player = locked_player.iloc[0]
                player_pos = player[pos_col]

                if drafted_counts.get(player_pos, 0) < position_limits.get(player_pos, 99):
                    drafted.append({
                        "Round": round_num,
                        "Player": player[player_col],
                        "Position": player_pos,
                        "ADP": player[adp_col]
                    })
                continue

        low_adp = ((round_num - 1) * 12) + 1
        high_adp = round_num * 12

        drafted_names = [p["Player"] for p in drafted]

        candidates = df[
            (df[adp_col] >= low_adp) &
            (df[adp_col] <= high_adp) &
            (~df[player_col].isin(drafted_names))
        ]

        candidates = candidates[
            candidates[pos_col].apply(
                lambda p: drafted_counts.get(p, 0) < position_limits.get(p, 99)
            )
        ]

        if candidates.empty:
            continue

        candidates = candidates.sort_values(by=adp_col)
        top_players = candidates.head(min(random_pool, len(candidates)))
        pick = top_players.sample(1).iloc[0]

        drafted.append({
            "Round": round_num,
            "Player": pick[player_col],
            "Position": pick[pos_col],
            "ADP": pick[adp_col]
        })

    return pd.DataFrame(drafted)


def calculate_best_ball_score(roster, week_cols):
    total_score = 0
    weekly_results = []

    for week in week_cols:
        players = roster.copy()
        players[week] = pd.to_numeric(players[week], errors="coerce").fillna(0)

        qb = players[players[pos_col] == "QB"].nlargest(1, week)
        rb = players[players[pos_col] == "RB"].nlargest(2, week)
        wr = players[players[pos_col] == "WR"].nlargest(2, week)
        te = players[players[pos_col] == "TE"].nlargest(1, week)

        used_players = pd.concat([qb, rb, wr, te])

        flex_pool = players[
            (players[pos_col].isin(["RB", "WR", "TE"])) &
            (~players[player_col].isin(used_players[player_col]))
        ]

        flex = flex_pool.nlargest(2, week)
        lineup = pd.concat([qb, rb, wr, te, flex])

        weekly_score = lineup[week].sum()
        total_score += weekly_score

        weekly_results.append({
            "Week": week,
            "Score": weekly_score,
            "Players": ", ".join(lineup[player_col].tolist())
        })

    return total_score, pd.DataFrame(weekly_results)


excel_file = pd.ExcelFile("Best Ball Optimizer.xlsx")

hidden_sheets = ["Sheet2", "26 WR"]

visible_sheets = [
    s for s in excel_file.sheet_names
    if s not in hidden_sheets
]

sheet = st.selectbox(
    "Choose a draft format",
    visible_sheets
)

df = pd.read_excel("Best Ball Optimizer.xlsx", sheet_name=sheet)
df.columns = df.columns.astype(str)

week_cols = [str(i) for i in range(1, 18) if str(i) in df.columns]

df = df.dropna(subset=[player_col, pos_col, adp_col])
df[adp_col] = pd.to_numeric(df[adp_col], errors="coerce")
df = df.dropna(subset=[adp_col])

if "POS Rank" in df.columns:
    df["POS Rank"] = pd.to_numeric(df["POS Rank"], errors="coerce")
    df["Label"] = df[pos_col] + df["POS Rank"].fillna(0).astype(int).astype(str)

st.success(f"Loaded {len(df)} players from {sheet}!")

st.subheader("Player Data")
player_start_col = df.columns.get_loc("Player")
st.dataframe(df.iloc[:, player_start_col:])

st.subheader("Draft Settings")
st.write("Choose how many players to draft by position:")

col1, col2, col3, col4 = st.columns(4)

with col1:
    qb_limit = st.number_input("QB", min_value=0, max_value=10, value=2)

with col2:
    rb_limit = st.number_input("RB", min_value=0, max_value=15, value=6)

with col3:
    wr_limit = st.number_input("WR", min_value=0, max_value=15, value=7)

with col4:
    te_limit = st.number_input("TE", min_value=0, max_value=10, value=3)

position_limits = {
    "QB": qb_limit,
    "RB": rb_limit,
    "WR": wr_limit,
    "TE": te_limit
}

random_pool = st.slider(
    "Random Player Pool",
    min_value=1,
    max_value=20,
    value=10
)

st.subheader("Locked Picks")

if "locked_picks" not in st.session_state:
    st.session_state.locked_picks = {}

selected_round = st.selectbox(
    "Round",
    list(range(1, 21))
)

selected_player = st.selectbox(
    "Player",
    [""] + sorted(df[player_col].tolist())
)

if st.button("Add Locked Pick"):
    if selected_player:
        st.session_state.locked_picks[selected_round] = selected_player

locked_picks = st.session_state.locked_picks

if locked_picks:
    locked_df = pd.DataFrame([
        {"Round": r, "Player": p}
        for r, p in sorted(locked_picks.items())
    ])

    st.dataframe(locked_df, hide_index=True)

    if st.button("Clear Locked Picks"):
        st.session_state.locked_picks = {}
        st.rerun()

if st.button("Run Test Draft"):
    draft_result = run_simple_draft(df, random_pool, locked_picks, position_limits)

    roster = df[df[player_col].isin(draft_result["Player"])]

    score, weekly_breakdown = calculate_best_ball_score(roster, week_cols)

    st.subheader("Test Draft")
    st.dataframe(draft_result[["Round", "Player", "Position" "ADP"]], hide_index=True)

    st.subheader("Draft Score")
    st.write(round(score, 2))

    st.subheader("Weekly Lineups")
    st.dataframe(weekly_breakdown, hide_index=True)