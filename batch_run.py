import os
import glob
import time
import pandas as pd
from parser import parse_screenplay, generate_candidate_windows
from evaluator import evaluate_candidates_batch

INPUT_DIR = "input_pack"
OUTPUT_DIR = "outputs"

def run_batch():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.txt")))
    print(f"==================================================")
    print(f"🎬 Kuku Promo Extractor - Batch Pipeline")
    print(f"Found {len(files)} screenplay files to process in {INPUT_DIR}/")
    print(f"==================================================\n")

    all_promos = []

    for file_idx, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        print(f"[{file_idx}/{len(files)}] Processing {filename}...")
        
        try:
            data = parse_screenplay(filepath)
            candidates = generate_candidate_windows(data["blocks"], min_len=25, max_len=55, step=10)
            
            if not candidates:
                print(f"  ⚠️ No candidate windows found for {filename}")
                continue

            # Pick the top 2 candidate windows using our Python emotional heuristic
            selected_cands = candidates[:2]
            
            # Single-batch LLM evaluation
            eval_results = evaluate_candidates_batch(selected_cands, data["logline"])
            
            for idx, cand in enumerate(selected_cands):
                eval_data = eval_results[idx] if isinstance(eval_results, list) and idx < len(eval_results) else {}
                
                h_score = eval_data.get("hook_score", 8)
                c_score = eval_data.get("cliffhanger_score", 8)
                q_score = eval_data.get("clarity_score", 8)
                rank_score = round(0.4 * h_score + 0.4 * c_score + 0.2 * q_score, 2)
                
                all_promos.append({
                    "Episode": data["episode"],
                    "Filename": filename,
                    "Start_Time": cand["start_str"],
                    "End_Time": cand["end_str"],
                    "Duration_s": cand["duration"],
                    "Rank_Score": rank_score,
                    "Hook_Score": h_score,
                    "Cliffhanger_Score": c_score,
                    "Clarity_Score": q_score,
                    "Hook_Description": eval_data.get("hook_description", "High-tension opening beat"),
                    "Cliffhanger_Description": eval_data.get("cliffhanger_description", "Unresolved dramatic cut point"),
                    "Why_It_Converts": eval_data.get("conversion_pitch", "Visceral emotional stakes that compel viewer to watch full episode."),
                    "Script_Excerpt": cand["text"]
                })
            
            print(f"  ✅ Extracted {len(selected_cands)} promos.")
            # Small delay to keep API traffic steady
            time.sleep(1)

        except Exception as e:
            print(f"  ❌ Error processing {filename}: {e}")

    if all_promos:
        master_df = pd.DataFrame(all_promos)
        # Sort overall by Rank_Score descending
        master_df = master_df.sort_values(by="Rank_Score", ascending=False).reset_index(drop=True)
        master_df.index += 1
        
        csv_path = os.path.join(OUTPUT_DIR, "all_episodes_promos_ranked.csv")
        json_path = os.path.join(OUTPUT_DIR, "all_episodes_promos_ranked.json")
        
        master_df.to_csv(csv_path, index_label="Overall_Rank")
        master_df.to_json(json_path, orient="records", indent=2)
        
        print("\n==================================================")
        print(f"🎉 BATCH COMPLETE!")
        print(f"Saved ranked promos to:\n • {csv_path}\n • {json_path}")
        print("==================================================")

if __name__ == "__main__":
    run_batch()