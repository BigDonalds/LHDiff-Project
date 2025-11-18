import os, re
from lh_diff.io import build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.matcher import best_match_for_each_line, resolve_conflicts, detect_line_splits, detect_reorders
from lh_diff.evaluator import evaluate_mapping, print_evaluation, save_results_csv, average_results
from lh_diff.diff_utils import print_diff_summary
from lh_diff.ground_truth import build_ground_truth

def infer_file_pairs(data_folder="data"):
    files = os.listdir(data_folder)
    old_files = [f for f in files if re.search(r"_1\.[A-Za-z0-9]+$", f)]
    pairs = []
    for old_file in old_files:
        base_name, ext = os.path.splitext(old_file)
        if base_name.endswith("_1"):
            prefix = base_name[:-2]
            new_file = f"{prefix}_2{ext}"
            old_path = os.path.join(data_folder, old_file)
            new_path = os.path.join(data_folder, new_file)
            if new_file in files:
                pairs.append((prefix, old_path, new_path))
    return sorted(pairs)

def run_case(name, old_file, new_file):
    
    old_lines = build_normalized_lines(old_file)
    new_lines = build_normalized_lines(new_file)
    print_diff_summary(old_lines, new_lines)
    candidates = generate_candidate_sets(old_lines, new_lines, k=20)
    matches = best_match_for_each_line(old_lines, new_lines, candidates, threshold=0.45)
    resolved = resolve_conflicts(matches, new_lines)
    resolved = detect_reorders(old_lines, new_lines, resolved)
    split_map = detect_line_splits(old_lines, new_lines, resolved)
    ground_truth = build_ground_truth(old_lines, new_lines)
    precision, recall, f1 = evaluate_mapping(split_map, ground_truth)
    print_evaluation(name, precision, recall, f1)
    
    return (name, precision, recall, f1)

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
