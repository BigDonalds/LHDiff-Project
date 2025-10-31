import os
from lh_diff.io import build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.matcher import best_match_for_each_line, resolve_conflicts, detect_line_splits, detect_reorders
from lh_diff.evaluator import evaluate_mapping, print_evaluation, save_results_csv, average_results
from lh_diff.diff_utils import print_diff_summary

# infer matching old/new file pairs in a folder
def infer_file_pairs(data_folder="data"):
    files = os.listdir(data_folder)
    old_files = [f for f in files if "_old.txt" in f]
    pairs = []

    for old_file in old_files:
        base_name = old_file.replace("_old.txt", "")
        new_file = f"{base_name}_new.txt"
        old_path = os.path.join(data_folder, old_file)
        new_path = os.path.join(data_folder, new_file)

        if new_file in files:
            pairs.append((base_name, old_path, new_path))

    return sorted(pairs)


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

    # heuristic: one old line, two new lines — check if new lines reconstruct old
    if len(new_lines) == 1 and ";" in new_lines[0] and len(old_lines) > 1:
        ground_truth = {old_idx: [0] for old_idx in range(len(old_lines))}

    elif len(old_lines) == 1 and len(new_lines) == 2:
        old_clean = old_lines[0].replace(" ", "")
        new0_clean = new_lines[0].replace(" ", "")
        new1_clean = new_lines[1].replace(" ", "")

        # normalize additive assignments for comparison (a+b+c vs a+b; +=c)
        old_norm = old_clean.replace("+=", "+")
        new0_norm = new0_clean.replace("+=", "+")
        new1_norm = new1_clean.replace("+=", "+")

        import re
        extract_tokens = lambda s: set(re.findall(r"[A-Za-z_]\w*", s))
        old_tokens = extract_tokens(old_norm)
        new_tokens = extract_tokens(new0_norm) | extract_tokens(new1_norm)

        # detect split if all old tokens exist across combined new lines
        if old_tokens.issubset(new_tokens) or old_norm.startswith(new0_norm) or old_norm.endswith(new1_norm):
            ground_truth = {0: [0, 1]}
        else:
            j = 0
            for i in range(len(old_lines)):
                while j < len(new_lines) and new_lines[j] != old_lines[i]:
                    j += 1
                if j < len(new_lines):
                    ground_truth[i] = [j]

    # 1-to-1 mapping
    elif len(old_lines) == len(new_lines):
        ground_truth = {i: [i] for i in range(len(old_lines))}

    # forgiving fallback for mismatched lengths
    else:
        j = 0
        for i in range(len(old_lines)):
            while j < len(new_lines) and new_lines[j] != old_lines[i]:
                j += 1
            if j < len(new_lines):
                ground_truth[i] = [j]

    precision, recall, f1 = evaluate_mapping(split_map, ground_truth)
    print_evaluation(name, precision, recall, f1)

    return (name, precision, recall, f1)


# run all cases in folder and save results
def main():
    data_folder = "data"
    pairs = infer_file_pairs(data_folder)

    if not pairs:
        print("No file pairs found in 'data/'")
        return

    results = []
    for name, old_path, new_path in pairs:
        try:
            results.append(run_case(name, old_path, new_path))
        except Exception as e:
            print(f"Error processing {name}: {e}")

    if results:
        save_results_csv(results, os.path.join(data_folder, "evaluation_results.csv"))
        average_results(results)
    else:
        print("No successful test cases were evaluated.")


if __name__ == "__main__":
    main()
