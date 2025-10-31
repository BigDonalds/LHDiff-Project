from typing import List, Dict, Tuple
from lh_diff.similarity import build_context, combined_similarity
from rapidfuzz.distance import Levenshtein

# map each old line to its best matching new line
def best_match_for_each_line(old_lines: List[str], new_lines: List[str], candidate_sets: Dict[int, List[int]], threshold: float = 0.5) -> Dict[int, Tuple[int, float]]:
    matches = {}
    last_match_old = -1
    last_match_new = -1

    for old_idx, candidates in candidate_sets.items():
        old_line = old_lines[old_idx]
        old_context = build_context(old_lines, old_idx)

        # fallback: if few candidates for a long line, brute-force all new lines
        if len(candidates) < 2 and len(old_line) > 8:
            candidates = list(range(len(new_lines)))

        best_score = 0.0
        best_new_idx = None

        for new_idx in candidates:
            new_line = new_lines[new_idx]
            new_context = build_context(new_lines, new_idx)
            score = combined_similarity(old_line, new_line, old_context, new_context)

            # slight positional bias favors lines near each other
            distance_penalty = 1 / (1 + abs(old_idx - new_idx))
            adjusted_score = score * (0.95 + 0.05 * distance_penalty)

            if adjusted_score > best_score:
                best_score = adjusted_score
                best_new_idx = new_idx

        # insertion recovery: check a few lines ahead if previous matches exist
        if best_score < threshold and last_match_old != -1 and last_match_new != -1:
            for offset in range(1, 4):
                predicted_new = last_match_new + offset
                if predicted_new >= len(new_lines):
                    break
                pred_score = combined_similarity(old_line, new_lines[predicted_new], "", "")
                if pred_score > best_score and pred_score >= threshold * 0.75:
                    best_new_idx = predicted_new
                    best_score = pred_score
                    break

        # confirm match only if score is reasonably high
        if best_new_idx is not None and best_score >= threshold * 0.9:
            matches[old_idx] = (best_new_idx, best_score)
            last_match_old = old_idx
            last_match_new = best_new_idx

    return matches


# resolve conflicts when multiple old lines map to the same new line
def resolve_conflicts(matches: Dict[int, Tuple[int, float]]) -> Dict[int, Tuple[int, float]]:
    new_to_old = {}
    for old_idx, (new_idx, score) in matches.items():
        # prefer the old line with the highest score for a given new line
        if new_idx not in new_to_old or score > new_to_old[new_idx][1]:
            new_to_old[new_idx] = (old_idx, score)
    return {old_idx: (new_idx, score) for new_idx, (old_idx, score) in new_to_old.items()}


# detect small local reorderings by looking at lines near expected position
def detect_reorders(old_lines: List[str], new_lines: List[str], matches: Dict[int, Tuple[int, float]], threshold: float = 0.35) -> Dict[int, Tuple[int, float]]:
    unmatched_old = [i for i in range(len(old_lines)) if i not in matches]
    matched_new = {v[0] for v in matches.values()}
    extra_matches = {}

    for old_idx in unmatched_old:
        old_line = old_lines[old_idx]
        old_ctx = build_context(old_lines, old_idx, window=6)
        best_score, best_new_idx = 0.0, None

        # only look ±5 lines around old_idx
        for new_idx in range(max(0, old_idx - 5), min(len(new_lines), old_idx + 6)):
            if new_idx in matched_new:
                continue
            new_line = new_lines[new_idx]
            new_ctx = build_context(new_lines, new_idx, window=6)
            # bias toward content but allow context to guide small reorders
            score = combined_similarity(old_line, new_line, old_ctx, new_ctx, weight_content=0.6, weight_context=0.4)
            if score > best_score:
                best_score, best_new_idx = score, new_idx

        if best_new_idx is not None and best_score >= threshold:
            extra_matches[old_idx] = (best_new_idx, best_score)

    return {**matches, **extra_matches}


# detect splits and multi-line merges
def detect_line_splits(old_lines: List[str], new_lines: List[str], matches: Dict[int, Tuple[int, float]], threshold_increase: float = 0.03) -> Dict[int, List[int]]:
    updated_matches = {}

    for old_idx, (new_idx, _) in matches.items():
        old_line = old_lines[old_idx].strip()
        group = [new_idx]
        combined_text = new_lines[new_idx].strip()
        best_score = combined_similarity(old_line, combined_text, "", "")

        # additive-split heuristic: a+b+c to a+b; +=c
        if ("+" in old_line and (new_idx + 1) < len(new_lines)):
            nxt = new_idx + 1
            first = new_lines[new_idx].replace(" ", "")
            second = new_lines[nxt].replace(" ", "")
            if "+" in first and "+=" in second:
                compact_old = old_line.replace(" ", "")
                if compact_old.count("+") == 2:
                    updated_matches[old_idx] = [new_idx, nxt]
                    continue

        # combine short consecutive lines if similarity improves
        if len(combined_text) < len(old_line) and ";" not in old_line:
            for nxt in range(new_idx + 1, min(new_idx + 3, len(new_lines))):
                test_text = combined_text + " " + new_lines[nxt].strip()
                norm_score = combined_similarity(old_line, test_text, "", "")
                raw_dist = Levenshtein.distance(old_line, test_text)
                raw_max = max(len(old_line), len(test_text))
                raw_score = 1 - (raw_dist / raw_max) if raw_max > 0 else 0

                # accept if normalized similarity slightly improves or raw similarity is strong
                if norm_score > best_score + threshold_increase or raw_score > 0.80:
                    group.append(nxt)
                    combined_text = test_text
                    best_score = max(norm_score, raw_score)
                else:
                    break

        # handle merged statements separated by semicolons
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
