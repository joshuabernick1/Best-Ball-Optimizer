import streamlit as st
import pandas as pd

st.title("Best Ball Optimizer")

page = st.sidebar.radio(
    "Choose Page",
    ["Draft Optimizer", "Simulation Stats"]
)

player_col = "Player"
pos_col = "Position"
adp_col = "ADP"


def run_simple_draft(df, random_pool, locked_picks):
    drafted = []
    df = df.copy()
    df[adp_col] = pd.to_numeric(df[adp_col], errors="coerce")

    for round_num in range(1, 21):
        if round_num in locked_picks:
            locked_name = locked_picks[round_num]
            locked_player = df[df[player_col].str.upper() == locked_name.upper()]

            if not locked_player.empty:
                player = locked_player.iloc[0]
                drafted.append({
                    "Round": round_num,
                    "Player": player[player_col],
                    "Position": player[pos_col],
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

        if candidates.empty:
            candidates = df[~df[player_col].isin(drafted_names)]

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


def meets_minimums(draft_result, position_minimums):
    counts = draft_result["Position"].value_counts().to_dict()

    for pos, minimum in position_minimums.items():
        if counts.get(pos, 0) < minimum:
            return False

    return True


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


if page == "Draft Optimizer":

    st.subheader("Player Data")
    player_start_col = df.columns.get_loc("Player")
    st.dataframe(df.iloc[:, player_start_col:])

    st.subheader("Draft Settings")
    st.write("Optional: choose minimums by position. Leave blank for no minimum.")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        qb_min = st.number_input("QB Minimum", min_value=0, max_value=10, value=None, placeholder="Any")

    with col2:
        rb_min = st.number_input("RB Minimum", min_value=0, max_value=15, value=None, placeholder="Any")

    with col3:
        wr_min = st.number_input("WR Minimum", min_value=0, max_value=15, value=None, placeholder="Any")

    with col4:
        te_min = st.number_input("TE Minimum", min_value=0, max_value=10, value=None, placeholder="Any")

    position_minimums = {
        "QB": qb_min if qb_min is not None else 0,
        "RB": rb_min if rb_min is not None else 0,
        "WR": wr_min if wr_min is not None else 0,
        "TE": te_min if te_min is not None else 0
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

    selected_round = st.selectbox("Round", list(range(1, 21)))

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
        best_result = None
        best_score = 0
        best_weekly_breakdown = None

        attempts = 0
        max_attempts = 1000

        while attempts < max_attempts:
            draft_result = run_simple_draft(df, random_pool, locked_picks)

            if not meets_minimums(draft_result, position_minimums):
                attempts += 1
                continue

            roster = df[df[player_col].isin(draft_result["Player"])]
            score, weekly_breakdown = calculate_best_ball_score(roster, week_cols)

            if score > best_score:
                best_score = score
                best_result = draft_result
                best_weekly_breakdown = weekly_breakdown

            if best_score >= 1800:
                break

            attempts += 1

        if best_result is None:
            st.error("No draft found that meets the position minimums. Try lowering the minimums.")
        else:
            st.subheader("Test Draft")

            left_col, right_col = st.columns([3, 1])

            with left_col:
                st.dataframe(best_result[["Round", "Player", "Position", "ADP"]], hide_index=True)

            with right_col:
                st.subheader("Team Count")
                position_count = best_result["Position"].value_counts().reindex(
                    ["QB", "RB", "WR", "TE"],
                    fill_value=0
                )

                st.dataframe(
                    position_count.reset_index().rename(
                        columns={"index": "Pos", "Position": "#"}
                    ),
                    hide_index=True
                )

            st.subheader("Draft Score")
            st.write(round(best_score, 2))

            if best_score < 1800:
                st.warning("No draft over 1800 was found. Showing the best valid result found.")

            st.subheader("Weekly Lineups")
            st.dataframe(best_weekly_breakdown, hide_index=True)


if page == "Simulation Stats":

    st.header("Simulation Stats")

    sim_count = st.number_input(
        "How many simulations?",
        min_value=10,
        max_value=10000,
        value=1000,
        step=100
    )

    random_pool_stats = st.slider(
        "Random Player Pool",
        min_value=1,
        max_value=20,
        value=10,
        key="stats_random_pool"
    )

    if st.button("Run Simulation Stats"):
        all_drafts = []
        progress = st.progress(0)

        for i in range(sim_count):
            draft_result = run_simple_draft(df, random_pool_stats)
            draft_result["Simulation"] = i + 1
            all_drafts.append(draft_result)

            progress.progress((i + 1) / sim_count)

        results = pd.concat(all_drafts)

        position_by_round = (
            results.groupby(["Round", "Position"])
            .size()
            .reset_index(name="Count")
        )

        position_by_round["Percent"] = (
            position_by_round["Count"] / sim_count * 100
        ).round(1)

        pivot_table = position_by_round.pivot(
            index="Round",
            columns="Position",
            values="Percent"
        ).fillna(0)

        st.subheader("Position Drafted by Round (%)")
        st.dataframe(pivot_table)

        st.subheader("Raw Simulation Results")
        st.dataframe(results)

        csv = results.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Simulation Results",
            data=csv,
            file_name="simulation_results.csv",
            mime="text/csv"
        )