import streamlit as st
import pandas as pd
import random

st.title("Joshua's FFPC Best Ball Optimizer")

player_col = "Player"
pos_col = "Position"
adp_col = "ADP"
WEEK_COLS = []


def run_simple_draft(df, random_pool, locked_picks):
    drafted = []

    df = df.copy()
    df[adp_col] = pd.to_numeric(df[adp_col], errors="coerce")

    for round_num in range(1, 21):
        if round_num in locked_picks:
            locked_name = locked_picks[round_num]

            locked_player = df[
                df[player_col].str.upper() == locked_name.upper()
            ]

            if not locked_player.empty:
                player = locked_player.iloc[0]

                drafted.append({
                    "Round": round_num,
                    "Player": player[player_col],
                    "ADP": player[adp_col]
                })

                continue

        low_adp = ((round_num - 1) * 12) + 1
        high_adp = round_num * 12

        candidates = df[
            (df[adp_col] >= low_adp) &
            (df[adp_col] <= high_adp) &
            (~df[player_col].isin([p["Player"] for p in drafted]))
        ]

        if candidates.empty:
            continue

        candidates = candidates.sort_values(by=adp_col)
        top_players = candidates.head(min(random_pool, len(candidates)))
        pick = top_players.sample(1).iloc[0]

        drafted.append({
            "Round": round_num,
            "Player": pick[player_col],
            "ADP": pick[adp_col]
        })

    return pd.DataFrame(drafted)


def calculate_best_ball_score(roster):
    total_score = 0
    weekly_results = []

    for week in WEEK_COLS:
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


uploaded_file = st.file_uploader(
    "Upload your Excel workbook",
    type=["xlsx"]
)

if uploaded_file:
    excel_file = pd.ExcelFile(uploaded_file)

    sheet = st.selectbox(
        "Choose a sheet",
        excel_file.sheet_names
    )

    df = pd.read_excel(uploaded_file, sheet_name=sheet)
    df.columns = df.columns.astype(str)
    WEEK_COLS = [str(i) for i in range(1, 18) if str(i) in df.columns]
    st.write("Week columns found:", WEEK_COLS)
    df = df.dropna(subset=[player_col, pos_col, adp_col])
    df[adp_col] = pd.to_numeric(df[adp_col], errors="coerce")
    df = df.dropna(subset=[adp_col])

    if "POS Rank" in df.columns:
        df["POS Rank"] = pd.to_numeric(df["POS Rank"], errors="coerce")
        df["Label"] = df[pos_col] + df["POS Rank"].fillna(0).astype(int).astype(str)

    st.success(f"Loaded {len(df)} rows from {sheet}!")

    st.subheader("Preview of Uploaded Data")
    player_start_col = df.columns.get_loc("Player")
    st.dataframe(df.iloc[:, player_start_col:])

    st.subheader("Draft Settings")

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
        draft_result = run_simple_draft(df, random_pool, locked_picks)

        roster = df[df[player_col].isin(draft_result["Player"])]

        score, weekly_breakdown = calculate_best_ball_score(roster)

        st.subheader("Test Draft")
        st.dataframe(draft_result[["Round", "Player", "ADP"]])

        st.subheader("Draft Score")
        st.write(score)

        st.subheader("Weekly Lineups")
        st.dataframe(weekly_breakdown)