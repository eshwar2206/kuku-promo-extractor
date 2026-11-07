import streamlit as st
import pandas as pd
import glob
import os
from parser import parse_screenplay, generate_candidate_windows
from evaluator import evaluate_candidates_batch

st.set_page_config(page_title="Kuku Microdrama Promo Extractor", layout="wide")

st.title("🎬 Kuku Microdrama Promo Extractor AI")
st.caption("Automated AI pipeline to discover, score, and rank 20–60s viral promo ads across microdrama episodes.")

with st.sidebar:
    st.header("⚙️ Configuration")
    min_dur = st.slider("Min Duration (seconds)", 20, 30, 25)
    max_dur = st.slider("Max Duration (seconds)", 40, 60, 55)
    top_candidates_per_ep = st.slider("Promos to Extract Per Episode", 1, 3, 2)
    st.markdown("---")
    st.markdown("**Scoring Weights:**")
    st.caption("• Hook (First 3s): 40%")
    st.caption("• Cliffhanger Cut: 40%")
    st.caption("• Standalone Clarity: 20%")

tab1, tab2 = st.tabs(["📁 Upload Screenplay(s)", "⚡ Process Full Season (Input Pack)"])

# ----------------- TAB 1: USER UPLOAD (SINGLE OR MULTIPLE) -----------------
with tab1:
    uploaded_files = st.file_uploader(
        "Upload one or more Episode Screenplays (.txt)", 
        type=["txt"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        st.info(f"Loaded **{len(uploaded_files)}** file(s) for processing.")

        if st.button("🚀 Find & Rank Promos for Uploaded Files"):
            all_results = []
            progress_bar = st.progress(0)

            for idx, uploaded_file in enumerate(uploaded_files):
                script_content = uploaded_file.read().decode("utf-8", errors="ignore")
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(script_content)

                data = parse_screenplay(temp_path)
                candidates = generate_candidate_windows(data["blocks"], min_len=min_dur, max_len=max_dur)

                if candidates:
                    selected_cands = candidates[:top_candidates_per_ep]
                    eval_results = evaluate_candidates_batch(selected_cands, data["logline"])

                    for c_idx, cand in enumerate(selected_cands):
                        eval_data = eval_results[c_idx] if c_idx < len(eval_results) else {}
                        h_score = eval_data.get("hook_score", 8.0)
                        c_score = eval_data.get("cliffhanger_score", 8.0)
                        q_score = eval_data.get("clarity_score", 8.5)
                        rank_score = round(0.4 * h_score + 0.4 * c_score + 0.2 * q_score, 2)

                        all_results.append({
                            "Episode": data["episode"],
                            "Timestamps": f"{cand['start_str']} - {cand['end_str']}",
                            "Duration (s)": cand["duration"],
                            "Rank Score": rank_score,
                            "Hook Score": h_score,
                            "Cliffhanger Score": c_score,
                            "Clarity Score": q_score,
                            "Hook (First 3s)": eval_data.get("hook_description", "High-tension opening beat"),
                            "Cliffhanger": eval_data.get("cliffhanger_description", "Unresolved dramatic cut point"),
                            "Why It Converts": eval_data.get("conversion_pitch", "Visceral emotional stakes driving cold installs."),
                            "Script Excerpt": cand["text"]
                        })

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                progress_bar.progress((idx + 1) / len(uploaded_files))

            if all_results:
                df = pd.DataFrame(all_results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
                df.index += 1
                st.subheader(f"🏆 Top Ranked Promos ({len(df)} clips discovered)")
                st.dataframe(df[["Episode", "Timestamps", "Duration (s)", "Rank Score", "Hook (First 3s)", "Cliffhanger", "Why It Converts"]])

                best = df.iloc[0]
                st.markdown("---")
                st.subheader(f"🥇 Highest Performing Promo: {best['Episode']} ({best['Timestamps']}) - Score: {best['Rank Score']}/10")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**🪝 The Hook:**", best["Hook (First 3s)"])
                    st.write("**🧗 The Cliffhanger:**", best["Cliffhanger"])
                    st.write("**💡 Pitch:**", best["Why It Converts"])
                with col2:
                    st.text_area("Screenplay Segment", best["Script Excerpt"], height=200)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Master Ranked CSV", data=csv, file_name="ranked_promos.csv", mime="text/csv")
            else:
                st.warning("No candidate promo windows matched the duration/tension filters.")

# ----------------- TAB 2: ONE-CLICK FULL SEASON AUDIT -----------------
with tab2:
    st.subheader("Process All 50 Episodes from `input_pack/`")
    st.write("Extract and rank the best promo moments across the entire show in one run.")

    if os.path.exists("outputs/all_episodes_promos_ranked.csv"):
        st.success("✅ Pre-computed results for the entire 50-episode season are available!")
        df_season = pd.read_csv("outputs/all_episodes_promos_ranked.csv")
        st.dataframe(df_season[["Episode", "Start_Time", "End_Time", "Duration_s", "Rank_Score", "Hook_Description", "Cliffhanger_Description", "Why_It_Converts"]])
        
        csv_full = df_season.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Season 1 Master CSV", data=csv_full, file_name="season_1_promos_ranked.csv", mime="text/csv")
    else:
        st.info("Click below to run batch analysis on all episodes stored in `input_pack/`.")
        if st.button("⚡ Run Full 50-Episode Pipeline"):
            with st.spinner("Processing entire season..."):
                os.system("python batch_run.py")
                st.rerun()
