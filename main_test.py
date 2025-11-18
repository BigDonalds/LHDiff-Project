import os, re, difflib
from lh_diff.io import build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.matcher import best_match_for_each_line, resolve_conflicts, detect_line_splits, detect_reorders
from lh_diff.evaluator import evaluate_mapping, print_evaluation, save_results_csv, average_results
from lh_diff.diff_utils import print_diff_summary


def infer_file_pairs(data_folder="data") -> dict:
    filesDictionary: dict[str, list[str]] = dict()
    files = os.listdir(data_folder)
    for file in files:
        path = os.path.join(data_folder, file)
        if os.path.isfile(path):
            base_name, ext = os.path.splitext(file)
            base_name = base_name[:-2]
            if filesDictionary.get(base_name):
                filesDictionary.get(base_name).append(path)
            else:
                filesDictionary[base_name] = list()
                filesDictionary[base_name].append(path)
    pop_list = list()
    for fileGroup in filesDictionary:
        if len(filesDictionary[fileGroup]) < 2:
            pop_list.append(fileGroup)
    for pop_item in pop_list:
        filesDictionary.pop(pop_item)
    return filesDictionary


def run_case(name, old_file, new_file):
    old_lines = build_normalized_lines(old_file)
    new_lines = build_normalized_lines(new_file)

    print(f"\n===== Running: {name} =====")
    print_diff_summary(old_lines, new_lines)

    candidates = generate_candidate_sets(old_lines, new_lines, k=20)
    matches = best_match_for_each_line(old_lines, new_lines, candidates, threshold=0.45)
    resolved = resolve_conflicts(matches, new_lines)
    resolved = detect_reorders(old_lines, new_lines, resolved)
    split_map = detect_line_splits(old_lines, new_lines, resolved)

    ground_truth = {}

    # Case 1: simple one-line to two-line split
    if len(old_lines) == 1 and len(new_lines) == 2:
        old_clean = old_lines[0].replace(" ", "")
        new0_clean = new_lines[0].replace(" ", "")
        new1_clean = new_lines[1].replace(" ", "")

        extract_tokens = lambda s: set(re.findall(r"[A-Za-z_]\w*", s))
        old_tokens = extract_tokens(old_clean)
        new_tokens = extract_tokens(new0_clean) | extract_tokens(new1_clean)

        if old_tokens.issubset(new_tokens) or old_clean.startswith(new0_clean) or old_clean.endswith(new1_clean):
            ground_truth = {0: [0, 1]}
        else:
            # fallback token-wise
            ratios = [(j, difflib.SequenceMatcher(None, old_lines[0], new).ratio()) for j, new in enumerate(new_lines)]
            best_j, best_score = max(ratios, key=lambda x: x[1])
            if best_score >= 0.35:
                ground_truth = {0: [best_j]}

    # Case 2: multiple old lines merged into fewer new lines
    elif len(old_lines) > len(new_lines):
        ground_truth = {}

        for j, new_line in enumerate(new_lines):
            best_span = (None, None, 0)
            for start in range(len(old_lines)):
                for end in range(start, len(old_lines)):
                    merged_old = " ".join(old_lines[start:end + 1])
                    ratio = difflib.SequenceMatcher(None, merged_old, new_line).ratio()
                    if ratio > best_span[2]:
                        best_span = (start, end, ratio)
            s, e, score = best_span
            if score >= 0.35:
                for i in range(s, e + 1):
                    ground_truth[i] = [j]

        # special merge pattern: inline literal expansion
        # example: "items=[1,2,3]; for x in items:" -> "for x in [1,2,3]:"
        for j, new_line in enumerate(new_lines):
            if "for" in new_line and "in" in new_line and "[" in new_line and "]" in new_line:
                for i, old_line in enumerate(old_lines):
                    if "for" in old_line or "items" in old_line or "[" in old_line:
                        ground_truth[i] = [j]

    # Case 3: equal number of lines -> 1-to-1 mapping
    elif len(old_lines) == len(new_lines):
        ground_truth = {i: [i] for i in range(len(old_lines))}

    # Case 4: single new line merging multiple old lines with ';'
    elif len(new_lines) == 1 and ";" in new_lines[0]:
        ground_truth = {old_idx: [0] for old_idx in range(len(old_lines))}

    # Case 5: fallback heuristic using token overlap
    else:
        for i, old in enumerate(old_lines):
            ratios = [(j, difflib.SequenceMatcher(None, old, new).ratio()) for j, new in enumerate(new_lines)]
            best_j, best_score = max(ratios, key=lambda x: x[1])
            if best_score >= 0.35:
                ground_truth[i] = [best_j]

    precision, recall, f1 = evaluate_mapping(split_map, ground_truth)
    print_evaluation(name, precision, recall, f1)

    return (name, precision, recall, f1)


# run all cases in folder and save results
def main():
    data_folder = "data"
    filesDictionary = infer_file_pairs(data_folder)

    # error case: no file pairs
    if not filesDictionary:
        print("No file pairs found in 'data/'")
        return

    results = []
    for name in filesDictionary:
        originalFile = filesDictionary[name][0]
        isOriginal = True
        for file in filesDictionary[name]:
            if isOriginal:
                isOriginal = False
                continue
            try:
                results.append(run_case(name, originalFile, file))
            except Exception as e:
                # catch-all error case
                print(f"Error processing {name}: {e}")

    if results:
        save_results_csv(results, os.path.join(data_folder, "evaluation_results.csv"))
        average_results(results)
    else:
        print("No successful test cases were evaluated.")


if __name__ == "__main__":
    main()
