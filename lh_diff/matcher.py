from typing import List, Dict, Tuple
from lh_diff.similarity import build_context, combined_similarity
import math

# handles insertions, reorderings, and context drift
def best_match_for_each_line(
    old_lines: List[str],
    new_lines: List[str],
    candidate_sets: Dict[int, List[int]],
    threshold: float = 0.5
) -> Dict[int, Tuple[int, float]]:
    
    matches = {}
    last_match_old = -1
    last_match_new = -1

    for old_idx, candidates in candidate_sets.items():
        old_line = old_lines[old_idx]
        old_context = build_context(old_lines, old_idx)

        best_score = 0.0
        best_new_idx = None

        # normal candidate matching
        for new_idx in candidates:
            new_line = new_lines[new_idx]
            new_context = build_context(new_lines, new_idx)
            score = combined_similarity(old_line, new_line, old_context, new_context)

            # favor nearby alignment but not too strongly
            distance_penalty = 1 / (1 + abs(old_idx - new_idx))
            adjusted_score = score * (0.95 + 0.05 * distance_penalty)

            if adjusted_score > best_score:
                best_score = adjusted_score
                best_new_idx = new_idx

        # tolerate small insertions between good matches
        if best_score < threshold and last_match_old != -1 and last_match_new != -1:
            # try predicting that a few new lines were inserted between matches
            max_lookahead = 3
            for offset in range(1, max_lookahead + 1):
                predicted_new = last_match_new + offset
                if predicted_new >= len(new_lines):
                    break
                pred_score = combined_similarity(
                    old_lines[old_idx], new_lines[predicted_new], "", ""
                )
                # allow looser threshold for insertion recovery
                if pred_score > best_score and pred_score >= threshold * 0.75:
                    best_new_idx = predicted_new
                    best_score = pred_score
                    break

        # safeguard: skip if similarity is meaningless
        if best_new_idx is not None and best_score >= threshold * 0.9:
            matches[old_idx] = (best_new_idx, best_score)
            last_match_old = old_idx
            last_match_new = best_new_idx

    return matches

# resolve multiple old lines mapping to same new line
def resolve_conflicts(matches: Dict[int, Tuple[int, float]]) -> Dict[int, Tuple[int, float]]:
    new_to_old = {}
    for old_idx, (new_idx, score) in matches.items():
        if new_idx not in new_to_old or score > new_to_old[new_idx][1]:
            new_to_old[new_idx] = (old_idx, score)
    resolved = {old_idx: (new_idx, score) for new_idx, (old_idx, score) in new_to_old.items()}
    return resolved

# detect lines that have moved slightly (local reordering).
def detect_reorders(
    old_lines: List[str],
    new_lines: List[str],
    matches: Dict[int, Tuple[int, float]],
    threshold: float = 0.35
) -> Dict[int, Tuple[int, float]]:

    unmatched_old = [i for i in range(len(old_lines)) if i not in matches]
    matched_new = {v[0] for v in matches.values()}
    extra_matches = {}

    for old_idx in unmatched_old:
        old_line = old_lines[old_idx]
        old_ctx = build_context(old_lines, old_idx, window=6)
        best_score, best_new_idx = 0.0, None

        for new_idx in range(max(0, old_idx - 5), min(len(new_lines), old_idx + 6)):
            if new_idx in matched_new:
                continue
            new_line = new_lines[new_idx]
            new_ctx = build_context(new_lines, new_idx, window=6)
            score = combined_similarity(old_line, new_line, old_ctx, new_ctx, weight_content=0.7, weight_context=0.3)
            if score > best_score:
                best_score, best_new_idx = score, new_idx

        if best_new_idx is not None and best_score >= threshold:
            extra_matches[old_idx] = (best_new_idx, best_score)

    final_matches = {**matches, **extra_matches}
    return final_matches

# detects when an old line corresponds to multiple new lines or vice versa,
# but applies this logic selectively to avoid hurting precision in normal cases.
def detect_line_splits(
    old_lines: List[str],
    new_lines: List[str],
    matches: Dict[int, Tuple[int, float]],
    threshold_increase: float = 0.03
) -> Dict[int, List[int]]:

    updated_matches = {}

    for old_idx, (new_idx, _) in matches.items():
        old_line = old_lines[old_idx].strip()
        group = [new_idx]
        combined_text = new_lines[new_idx].strip()
        best_score = combined_similarity(old_line, combined_text, "", "")

        # Case 1: possible line split
        # only attempt this if the new line is shorter (possible partial)
        if len(combined_text) < len(old_line) and ";" not in old_line:
            for nxt in range(new_idx + 1, min(new_idx + 3, len(new_lines))):
                test_text = combined_text + " " + new_lines[nxt].strip()
                new_score = combined_similarity(old_line, test_text, "", "")
                if new_score > best_score + threshold_increase:
                    group.append(nxt)
                    combined_text = test_text
                    best_score = new_score
                else:
                    break

        # Case 2: possible line merge (semicolon joins two statements)
        elif ";" in new_lines[new_idx]:
            split_parts = [p.strip() for p in new_lines[new_idx].split(";") if p.strip()]
            if len(split_parts) > 1:
                merged_score = 0.0
                for part in split_parts:
                    s = combined_similarity(old_line, part, "", "")
                    if s > merged_score:
                        merged_score = s
                if merged_score > best_score + threshold_increase:
                    best_score = merged_score

        updated_matches[old_idx] = group

    return updated_matches

