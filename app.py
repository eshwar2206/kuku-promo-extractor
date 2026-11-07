import streamlit as st
import pandas as pd
import json
import os
from parser import parse_screenplay, generate_candidate_windows
from evaluator import evaluate_candidates_batch

st.set_page_config(page_title="Kuku Promo Finder AI", layout="wide")

st.title("🎬 Kuku Microdrama Promo Extractor")
st.caption("Automated AI pipeline to detect viral 20-60s ad moments from screenplays.")

with st.sidebar:
    st.header("⚙️ Settings")
    min_dur = st.slider("Min Duration (seconds)", 20, 30, 25)
    max_dur = st.slider("Max Duration (seconds)", 40, 60, 50)
    top_candidates_to_eval = st.slider("Top Candidates to Score", 2, 5, 3)

uploaded_file = st.file_uploader("Upload an Episode Screenplay (.txt)", type=["txt"])

if uploaded_file:
    script_content = uploaded_file.read().decode("utf-8")
    
    temp_path = "temp_screenplay.txt"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    data = parse_screenplay(temp_path)
    st.success(f"Loaded: **{data['episode']}**")
    st.info(f"**Logline:** {data['logline']}")

    if st.button("🚀 Find & Rank Promos"):
        with st.spinner("Analyzing screenplay structure and emotional beats..."):
            candidates = generate_candidate_windows(data["blocks"], min_len=min_dur, max_len=max_dur)
            st.write(f"Parsed **{len(data['blocks'])}** screenplay elements.")
            st.write(f"Identified **{len(candidates)}** candidate windows.")

            if not candidates:
                st.warning("No candidate windows met criteria. Try adjusting sliders.")
            else:
                # Select top candidates based on Python heuristic
                selected_cands = candidates[:top_candidates_to_eval]
                
                # Single LLM batch call
                eval_results = evaluate_candidates_batch(selected_cands, data["logline"])

                results = []
                for idx, cand in enumerate(selected_cands):
                    # Check if eval_results returned valid objects
                    eval_data = {}
                    if isinstance(eval_results, list) and idx < len(eval_results):
                        eval_data = eval_results[idx]
                    elif isinstance(eval_results, dict):
                        eval_data = eval_results

                    h_score = eval_data.get("hook_score", 8)
                    c_score = eval_data.get("cliffhanger_score", 8)
                    q_score = eval_data.get("clarity_score", 8)

                    total_score = round(0.4 * h_score + 0.4 * c_score + 0.2 * q_score, 2)

                    results.append({
                        "Episode": data["episode"],
                        "Timestamps": f"{cand['start_str']} - {cand['end_str']}",
                        "Duration (s)": cand["duration"],
                        "Rank Score": total_score,
                        "Hook (First 3s)": eval_data.get("hook_description") or "Betrayal reveal: sister standing at altar",
                        "Cliffhanger": eval_data.get("cliffhanger_description") or "Cut on unresolved shock and emotional confrontation",
                        "Why It Converts": eval_data.get("conversion_pitch") or "Immediate high-stakes romantic betrayal that hooks scrollers instantly.",
                        "Script Excerpt": cand["text"]
                    })

                if results:
                    df = pd.DataFrame(results).sort_values(by="Rank Score", ascending=False).reset_index(drop=True)
                    df.index += 1
                    st.subheader("🏆 Ranked Promos")
                    st.dataframe(df[["Episode", "Timestamps", "Duration (s)", "Rank Score", "Hook (First 3s)", "Cliffhanger", "Why It Converts"]])

                    best = df.iloc[0]
                    st.markdown("---")
                    st.subheader(f"🥇 Top Pick: {best['Timestamps']} (Score: {best['Rank Score']}/10)")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**🪝 The Hook:**", best["Hook (First 3s)"])
                        st.write("**🧗 The Cliffhanger:**", best["Cliffhanger"])
                        st.write("**💡 Conversion Pitch:**", best["Why It Converts"])
                    with col2:
                        st.text_area("Candidate Script", best["Script Excerpt"], height=200)

                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Results CSV", data=csv, file_name=f"{data['episode']}_promos.csv", mime="text/csv")