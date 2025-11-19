import os, re
from lh_diff.io import build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.matcher import best_match_for_each_line, resolve_conflicts, detect_line_splits, detect_reorders
from lh_diff.evaluator import evaluate_mapping, print_evaluation, save_results_csv, average_results
from lh_diff.diff_utils import print_diff_summary
from lh_diff.ground_truth import build_ground_truth
from typing import List

def infer_file_pairs(data_folder="data") -> dict:
    filesDictionary: dict[str, List[str]] = dict()
    files = os.listdir(data_folder)
    for file in files:
        path = os.path.join(data_folder, file)
        if os.path.isfile(path):
            base_name, ext = os.path.splitext(file)
            base_name = base_name[:-2]
            if filesDictionary.get(base_name):
                filesDictionary.get(base_name).append(path)
            else:
                filesDictionary[base_name] = List()
                filesDictionary[base_name].append(path)
    pop_list = List()
    for fileGroup in filesDictionary:
        if len(filesDictionary[fileGroup]) < 2:
            pop_list.append(fileGroup)
    for pop_item in pop_list:
        filesDictionary.pop(pop_item)
    return filesDictionary

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
    filesDictionary = infer_file_pairs(data_folder)
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
