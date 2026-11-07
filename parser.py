import os
import re

def parse_time(time_str):
    """Converts (MM:SS.ss) or MM:SS.ss string to float seconds."""
    clean = time_str.strip("() \t\r\n")
    parts = clean.split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        return 0.0
    return 0.0

def format_time(seconds):
    """Converts float seconds back to MM:SS string."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def parse_screenplay(file_path):
    """Parses a microdrama screenplay file into ordered blocks."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Normalize line endings to avoid Windows \r\n regex matching issues
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Extract Episode info
    ep_num_match = re.search(r"EPISODE NUMBER:\s*(Episode\s*\d+)", text, re.IGNORECASE)
    ep_name = ep_num_match.group(1).strip() if ep_num_match else os.path.basename(file_path)

    logline_match = re.search(r"EPISODE LOGLINE:\s*(.*?)(?=\n[A-Z\s]+:|\n---|\Z)", text, re.DOTALL)
    logline = logline_match.group(1).strip() if logline_match else ""

    # Flexible regex to match any **HEADER:** block followed by Start/End timestamps
    block_pattern = re.compile(
        r"\*\*([^\*\n]+?)\:\*\*\s*\n\s*Start:\s*(\([0-9\:\.]+\))\s*\|\s*End:\s*(\([0-9\:\.]+\))\s*\n([\s\S]*?)(?=(?:\*\*[^\*\n]+?\:\*\*)|(?:--- SCRIPT END ---)|\Z)",
        re.MULTILINE
    )

    blocks = []
    for match in block_pattern.finditer(text):
        speaker_or_type = match.group(1).strip()
        start_sec = parse_time(match.group(2))
        end_sec = parse_time(match.group(3))
        content = match.group(4).strip()

        # Classify block type
        upper_name = speaker_or_type.upper()
        if "CAMERA" in upper_name:
            b_type = "CAMERA"
        elif "ACTION" in upper_name:
            b_type = "ACTION"
        elif "SOUND" in upper_name:
            b_type = "SOUND"
        else:
            b_type = "DIALOGUE"

        blocks.append({
            "speaker": speaker_or_type,
            "type": b_type,
            "start": start_sec,
            "end": end_sec,
            "content": content
        })

    return {
        "episode": ep_name,
        "logline": logline,
        "blocks": blocks
    }

def score_candidate_heuristic(text):
    """Fast rule-based tension heuristic to rank candidates before LLM evaluation."""
    score = 0
    keywords = [
        "slap", "crying", "tear", "betray", "marry", "wedding", "husband", 
        "wife", "disown", "enough", "mistake", "furious", "shock", "gasp", 
        "cruel", "shame", "embarrass", "love", "cheating", "paternity"
    ]
    lower_text = text.lower()
    for kw in keywords:
        if kw in lower_text:
            score += 2
    # Exclamation and question marks reflect emotional confrontation
    score += text.count("!") * 1.5
    score += text.count("?") * 1.0
    return score

def generate_candidate_windows(blocks, min_len=20, max_len=60, step=10):
    if not blocks:
        return []

    total_duration = max(b["end"] for b in blocks)
    candidates = []

    t = 0.0
    while t + min_len <= total_duration:
        for target_duration in [30, 45, 55]:
            if target_duration < min_len or target_duration > max_len:
                continue

            t_end = min(t + target_duration, total_duration)
            window_blocks = [b for b in blocks if b["end"] > t and b["start"] < t_end]

            if not window_blocks:
                continue

            actual_start = min(b["start"] for b in window_blocks)
            actual_end = max(b["end"] for b in window_blocks)
            duration = actual_end - actual_start

            if 20.0 <= duration <= 60.0:
                lines = []
                dialogue_count = 0
                for b in window_blocks:
                    if b["type"] == "DIALOGUE":
                        lines.append(f"{b['speaker']}: {b['content']}")
                        dialogue_count += 1
                    elif b["type"] == "ACTION":
                        lines.append(f"[ACTION] {b['content']}")

                if len(lines) >= 3 and dialogue_count >= 1:
                    text_str = "\n".join(lines)
                    h_score = score_candidate_heuristic(text_str)
                    candidates.append({
                        "start_sec": actual_start,
                        "end_sec": actual_end,
                        "start_str": format_time(actual_start),
                        "end_str": format_time(actual_end),
                        "duration": round(duration, 1),
                        "text": text_str,
                        "heuristic_score": h_score
                    })

        t += step

    # Deduplicate overlapping candidates
    unique_candidates = []
    seen = set()
    # Sort by heuristic score descending first
    candidates.sort(key=lambda x: x["heuristic_score"], reverse=True)
    
    for c in candidates:
        key = (round(c["start_sec"] / 4) * 4, round(c["end_sec"] / 4) * 4)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    return unique_candidates