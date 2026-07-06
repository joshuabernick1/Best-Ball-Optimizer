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


def meets_maximums(draft_result, position_maximums):
    counts = draft_result["Position"].value_counts().to_dict()

    for pos, maximum in position_maximums.items():
        if maximum is not None and counts.get(pos, 0) > maximum:
            return False

    return True


def get_lineup(roster, week, sheet):
    players = roster.copy()
    players[week] = pd.to_numeric(players[week], errors="coerce").fillna(0)

    qb = players[players[pos_col] == "QB"].nlargest(1, week)
    rb = players[players[pos_col] == "RB"].nlargest(2, week)
    te = players[players[pos_col] == "TE"].nlargest(1, week)

    sheet_lower = sheet.lower()

    if "super" in sheet_lower:
        wr = players[players[pos_col] == "WR"].nlargest(2, week)
        used = pd.concat([qb, rb, wr, te])

        superflex_pool = players[
            ~players[player_col].isin(used[player_col])
        ]
        superflex = superflex_pool.nlargest(1, week)

        used = pd.concat([used, superflex])

        flex_pool = players[
            (players[pos_col].isin(["RB", "WR", "TE"])) &
            (~players[player_col].isin(used[player_col]))
        ]
        flex = flex_pool.nlargest(1, week)

        return {
            "QB": qb,
            "RB1": rb.head(1),
            "RB2": rb.iloc[1:2],
            "WR1": wr.head(1),
            "WR2": wr.iloc[1:2],
            "TE": te,
            "SUPERFLEX": superflex,
            "FLEX": flex
        }

    elif "ffpc" in sheet_lower:
        wr = players[players[pos_col] == "WR"].nlargest(2, week)
        used = pd.concat([qb, rb, wr, te])

        flex_pool = players[
            (players[pos_col].isin(["RB", "WR", "TE"])) &
            (~players[player_col].isin(used[player_col]))
        ]
        flex = flex_pool.nlargest(2, week)

        return {
            "QB": qb,
            "RB1": rb.head(1),
            "RB2": rb.iloc[1:2],
            "WR1": wr.head(1),
            "WR2": wr.iloc[1:2],
            "TE": te,
            "FLEX1": flex.head(1),
            "FLEX2": flex.iloc[1:2]
        }

    else:
        wr = players[players[pos_col] == "WR"].nlargest(3, week)
        used = pd.concat([qb, rb, wr, te])

        flex_pool = players[
            (players[pos_col].isin(["RB", "WR", "TE"])) &
            (~players[player_col].isin(used[player_col]))
        ]
        flex = flex_pool.nlargest(1, week)

        return {
            "QB": qb,
            "RB1": rb.head(1),
            "RB2": rb.iloc[1:2],
            "WR1": wr.head(1),
            "WR2": wr.iloc[1:2],
            "WR3": wr.iloc[2:3],
            "TE": te,
            "FLEX": flex
        }


def calculate_best_ball_score(roster, week_cols, sheet):
    total_score = 0
    weekly_results = []

    for week in week_cols:
        lineup_dict = get_lineup(roster, week, sheet)
        lineup = pd.concat(lineup_dict.values())

        weekly_score = lineup[week].sum()
        total_score += weekly_score

        weekly_results.append({
            "Week": week,
            "Score": round(weekly_score, 2),
            "Players": ", ".join(lineup[player_col].tolist())
        })

    return total_score, pd.DataFrame(weekly_results)


def lineup_totals(roster, week_cols, sheet):
    totals = {}

    for week in week_cols:
        lineup_dict = get_lineup(roster, week, sheet)

        for slot, player_df in lineup_dict.items():
            if slot not in totals:
                totals[slot] = 0

            if not player_df.empty:
                totals[slot] += player_df.iloc[0][week]

    return pd.DataFrame(
        [{"Lineup Spot": k, "Points": round(v, 2)} for k, v in totals.items()]
    )


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

st.caption(f"Draft Format: {sheet}")


if page == "Draft Optimizer":

    st.subheader("Draft Settings")
    st.write("Optional: choose minimums and maximums by position. Leave blank for no restriction.")

    st.write("Minimums")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        qb_min = st.number_input("QB Min", min_value=0, max_value=10, value=None, placeholder="Any")

    with col2:
        rb_min = st.number_input("RB Min", min_value=0, max_value=15, value=None, placeholder="Any")

    with col3:
        wr_min = st.number_input("WR Min", min_value=0, max_value=15, value=None, placeholder="Any")

    with col4:
        te_min = st.number_input("TE Min", min_value=0, max_value=10, value=None, placeholder="Any")

    st.write("Maximums")
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        qb_max = st.number_input("QB Max", min_value=0, max_value=10, value=None, placeholder="Any")

    with col6:
        rb_max = st.number_input("RB Max", min_value=0, max_value=15, value=None, placeholder="Any")

    with col7:
        wr_max = st.number_input("WR Max", min_value=0, max_value=15, value=None, placeholder="Any")

    with col8:
        te_max = st.number_input("TE Max", min_value=0, max_value=10, value=None, placeholder="Any")

    position_minimums = {
        "QB": qb_min if qb_min is not None else 0,
        "RB": rb_min if rb_min is not None else 0,
        "WR": wr_min if wr_min is not None else 0,
        "TE": te_min if te_min is not None else 0
    }

    position_maximums = {
        "QB": qb_max,
        "RB": rb_max,
        "WR": wr_max,
        "TE": te_max
    }

    random_pool = st.slider(
        "Random Player Pool",
        min_value=1,
        max_value=20,
        value=10
    )

    st.info(
        """
**Random Player Pool**

The optimizer first identifies the top available players by ADP for each pick. It then randomly selects one player from this group.

• **1** = Always selects the highest ADP player available  
• **5** = Selects from the top 5 available players  
• **10** = Selects from the top 10 available players  
• **20** = Creates much more variation and unique draft combinations
"""
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
        best_score = -1
        best_weekly_breakdown = None
        best_position_points = None

        attempts = 0
        max_attempts = 1000

        while attempts < max_attempts:
            draft_result = run_simple_draft(df, random_pool, locked_picks)

            if not meets_minimums(draft_result, position_minimums):
                attempts += 1
                continue

            if not meets_maximums(draft_result, position_maximums):
                attempts += 1
                continue

            roster = df[df[player_col].isin(draft_result["Player"])]

            score, weekly_breakdown = calculate_best_ball_score(roster, week_cols, sheet)
            position_points = lineup_totals(roster, week_cols, sheet)

            if score > best_score:
                best_score = score
                best_result = draft_result
                best_weekly_breakdown = weekly_breakdown
                best_position_points = position_points

            if best_score >= 1800:
                break

            attempts += 1

        if best_result is None:
            st.error("No draft found that meets the position minimums/maximums. Try loosening the restrictions.")
        else:
            st.subheader("Test Draft")

            left_col, middle_col, right_col = st.columns([3, 1, 1])

            with left_col:
                st.dataframe(
                    best_result[["Round", "Player", "Position", "ADP"]],
                    hide_index=True
                )

            with middle_col:
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

            with right_col:
                st.subheader("Lineup Points")
                st.dataframe(best_position_points, hide_index=True)

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
    st.write("Minimums")
col1, col2, col3, col4 = st.columns(4)

with col1:
    stats_qb_min = st.number_input("QB Min", min_value=0, max_value=10, value=None, placeholder="Any", key="stats_qb_min")
with col2:
    stats_rb_min = st.number_input("RB Min", min_value=0, max_value=15, value=None, placeholder="Any", key="stats_rb_min")
with col3:
    stats_wr_min = st.number_input("WR Min", min_value=0, max_value=15, value=None, placeholder="Any", key="stats_wr_min")
with col4:
    stats_te_min = st.number_input("TE Min", min_value=0, max_value=10, value=None, placeholder="Any", key="stats_te_min")

st.write("Maximums")
col5, col6, col7, col8 = st.columns(4)

with col5:
    stats_qb_max = st.number_input("QB Max", min_value=0, max_value=10, value=None, placeholder="Any", key="stats_qb_max")
with col6:
    stats_rb_max = st.number_input("RB Max", min_value=0, max_value=15, value=None, placeholder="Any", key="stats_rb_max")
with col7:
    stats_wr_max = st.number_input("WR Max", min_value=0, max_value=15, value=None, placeholder="Any", key="stats_wr_max")
with col8:
    stats_te_max = st.number_input("TE Max", min_value=0, max_value=10, value=None, placeholder="Any", key="stats_te_max")

stats_position_minimums = {
    "QB": stats_qb_min if stats_qb_min is not None else 0,
    "RB": stats_rb_min if stats_rb_min is not None else 0,
    "WR": stats_wr_min if stats_wr_min is not None else 0,
    "TE": stats_te_min if stats_te_min is not None else 0
}

stats_position_maximums = {
    "QB": stats_qb_max,
    "RB": stats_rb_max,
    "WR": stats_wr_max,
    "TE": stats_te_max
}
if page == "Simulation Stats":

    st.header("Simulation Stats")

    sim_count = st.number_input(
        "How many simulations?",
        min_value=10,
        max_value=10000,
        value=1000,
        step=100,
        key="sim_count_input"
    )

    st.subheader("Simulation Restrictions")
    st.write("Optional: lock players and set position minimums/maximums.")

    st.write("Minimums")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sim_qb_min = st.number_input("Sim QB Min", min_value=0, max_value=10, value=None, placeholder="Any")

    with col2:
        sim_rb_min = st.number_input("Sim RB Min", min_value=0, max_value=15, value=None, placeholder="Any")

    with col3:
        sim_wr_min = st.number_input("Sim WR Min", min_value=0, max_value=15, value=None, placeholder="Any")

    with col4:
        sim_te_min = st.number_input("Sim TE Min", min_value=0, max_value=10, value=None, placeholder="Any")

    st.write("Maximums")
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        sim_qb_max = st.number_input("Sim QB Max", min_value=0, max_value=10, value=None, placeholder="Any")

    with col6:
        sim_rb_max = st.number_input("Sim RB Max", min_value=0, max_value=15, value=None, placeholder="Any")

    with col7:
        sim_wr_max = st.number_input("Sim WR Max", min_value=0, max_value=15, value=None, placeholder="Any")

    with col8:
        sim_te_max = st.number_input("Sim TE Max", min_value=0, max_value=10, value=None, placeholder="Any")

    sim_position_minimums = {
        "QB": sim_qb_min if sim_qb_min is not None else 0,
        "RB": sim_rb_min if sim_rb_min is not None else 0,
        "WR": sim_wr_min if sim_wr_min is not None else 0,
        "TE": sim_te_min if sim_te_min is not None else 0
    }

    sim_position_maximums = {
        "QB": sim_qb_max,
        "RB": sim_rb_max,
        "WR": sim_wr_max,
        "TE": sim_te_max
    }

    st.subheader("Simulation Locked Picks")

    if "sim_locked_picks" not in st.session_state:
        st.session_state.sim_locked_picks = {}

    sim_selected_round = st.selectbox(
        "Simulation Round",
        list(range(1, 21)),
        key="sim_round"
    )

    sim_selected_player = st.selectbox(
        "Simulation Player",
        [""] + sorted(df[player_col].tolist()),
        key="sim_player"
    )

    if st.button("Add Simulation Locked Pick"):
        if sim_selected_player:
            st.session_state.sim_locked_picks[sim_selected_round] = sim_selected_player

    sim_locked_picks = st.session_state.sim_locked_picks

    if sim_locked_picks:
        sim_locked_df = pd.DataFrame([
            {"Round": r, "Player": p}
            for r, p in sorted(sim_locked_picks.items())
        ])

        st.dataframe(sim_locked_df, hide_index=True)

        if st.button("Clear Simulation Locked Picks"):
            st.session_state.sim_locked_picks = {}
            st.rerun()

    random_pool_stats = st.slider(
        "Random Player Pool",
        min_value=1,
        max_value=20,
        value=10,
        key="stats_random_pool"
    )

    if st.button("Run Simulation Stats"):

        all_drafts = []
        score_rows = []

        best_score = -1
        best_team = None
        best_weekly_breakdown = None
        best_position_points = None

        valid_simulations = 0
        attempts = 0
        max_attempts = sim_count * 20

        progress = st.progress(0)

        while valid_simulations < sim_count and attempts < max_attempts:

            draft_result = run_simple_draft(
                df,
                random_pool_stats,
                sim_locked_picks
            )

            attempts += 1

            if not meets_minimums(draft_result, sim_position_minimums):
                continue

            if not meets_maximums(draft_result, sim_position_maximums):
                continue

            roster = df[df[player_col].isin(draft_result["Player"])]

            score, weekly_breakdown = calculate_best_ball_score(
                roster,
                week_cols,
                sheet
            )

            position_points = lineup_totals(
                roster,
                week_cols,
                sheet
            )

            valid_simulations += 1

            draft_result["Simulation"] = valid_simulations
            all_drafts.append(draft_result)

            score_rows.append({
                "Simulation": valid_simulations,
                "Score": round(score, 2)
            })

            if score > best_score:
                best_score = score
                best_team = draft_result.copy()
                best_weekly_breakdown = weekly_breakdown
                best_position_points = position_points

            progress.progress(valid_simulations / sim_count)

        if not all_drafts:
            st.error("No valid simulations found. Try loosening the locked picks or position restrictions.")

        else:
            results = pd.concat(all_drafts)
            scores_df = pd.DataFrame(score_rows)

            st.subheader("Simulation Scores")
            st.dataframe(scores_df, hide_index=True)

            st.write(f"Valid simulations completed: **{valid_simulations}**")
            st.write(f"Total attempts used: **{attempts}**")

            if valid_simulations < sim_count:
                st.warning("Not all requested simulations could be completed. Try loosening restrictions.")

            st.subheader("Highest Scoring Team")
            st.write(f"**Score:** {round(best_score, 2)}")

            left_col, middle_col, right_col = st.columns([3, 1, 1])

            with left_col:
                st.dataframe(
                    best_team[["Round", "Player", "Position", "ADP"]],
                    hide_index=True
                )

            with middle_col:
                st.subheader("Roster Count")
                best_position_count = best_team["Position"].value_counts().reindex(
                    ["QB", "RB", "WR", "TE"],
                    fill_value=0
                )

                st.dataframe(
                    best_position_count.reset_index().rename(
                        columns={"index": "Pos", "Position": "#"}
                    ),
                    hide_index=True
                )

            with right_col:
                st.subheader("Lineup Points")
                st.dataframe(best_position_points, hide_index=True)

            st.subheader("Best Team Weekly Lineups")
            st.dataframe(best_weekly_breakdown, hide_index=True)

            position_by_round = (
                results.groupby(["Round", "Position"])
                .size()
                .reset_index(name="Count")
            )

            position_by_round["Percent"] = (
                position_by_round["Count"] / valid_simulations * 100
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

            score_csv = scores_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download Simulation Scores",
                data=score_csv,
                file_name="simulation_scores.csv",
                mime="text/csv"
            )
