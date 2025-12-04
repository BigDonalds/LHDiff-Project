import os
from typing import List, Dict, Any, Tuple

from lh_diff.io import build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.evaluator import evaluate_mapping, print_evaluation, save_results_csv, average_results
from lh_diff.matcher import DiffMatcher
from lh_diff.ground_truth import GroundTruth
from lh_diff.bug_identifier import run_bug_identifier_for_pair


def format_lhdiff_output(mappings: Dict[int, List[int]]) -> str:
    """Format LHDiff mappings for text output"""
    lines = []
    # Iterate over old line indices in sorted order
    for old_idx in sorted(mappings.keys()):
        new_indices = mappings[old_idx]

        if isinstance(new_indices, list): # Check if the mapping is already a list
            if len(new_indices) == 1: 
                lines.append(f"[{old_idx}] -> [{new_indices[0]}]")
            else:
                lines.append(f"[{old_idx}] -> {new_indices}")
        else:
            lines.append(f"[{old_idx}] -> [{new_indices}]")
    return "\n".join(lines)


def format_bug_identifier_output(bug_results: Dict[str, Any]) -> str:
    """Format Bug Identifier results for text output"""
    lines = []
    
    # Bug fixes section
    lines.append("=== BUG FIXES ===")
    fixes = bug_results.get('bug_fixes', [])
    if fixes:
        for i, fix in enumerate(fixes, 1): # Loop over each fix with a 1-based index
            lines.append(f"FIX #{i}:")
            lines.append(f"  Old Line: {fix.get('old_line_num', 'N/A')}") # Show old line number or 'N/A' 
            lines.append(f"  New Line: {fix.get('new_line_num', 'N/A')}") # Show new line number or 'N/A'
            lines.append(f"  Bug Fix Score: {fix.get('bug_fix_score', 0):.3f}")

          
            # Show semantics
            semantics = fix.get('semantics', {})
            if semantics:
                lines.append(f"  Semantics:")
                for key, value in semantics.items():
            # filter zero and main key if present
                    if value > 0 and key != 'bug_fix_score':
                        lines.append(f"    - {key}: {value:.3f}")
            
            lines.append("") # blank line between fix
    else:
        lines.append("No bug fixes detected")
        lines.append("")
    
    # Bug introductions section
    lines.append("=== BUG INTRODUCTIONS ===")
    introductions = bug_results.get('bug_introductions', [])
    if introductions:
        for i, intro in enumerate(introductions, 1): 
            lines.append(f"INTRODUCTION #{i}:")
            lines.append(f"  Buggy Line: {intro.get('buggy_line_num', 'N/A')}")
            lines.append(f"  Introduced In: {os.path.basename(intro.get('introduced_in', 'Unknown'))}")
            lines.append(f"  Version: {intro.get('introduced_version', 'N/A')}")
            lines.append(f"  Confidence: {intro.get('confidence', 0):.3f}")
            
            # Show fix details if available
            fix_details = intro.get('fix_details', {})
            if fix_details:
                lines.append(f"  Fixed in current version at:")
                lines.append(f"    - Old Line: {fix_details.get('old_line', 'N/A')}")
                lines.append(f"    - New Line: {fix_details.get('new_line', 'N/A')}")
            
            lines.append("") # blank line between the introductions
    else:
        lines.append("No bug introductions detected")
        lines.append("")
    
    # Summary
    lines.append("=== SUMMARY ===")
    summary = bug_results.get('summary', {})
    # Goes back to original length if summary field is missing
    lines.append(f"Total bug fixes: {summary.get('num_bug_fixes', len(fixes))}")
    lines.append(f"Total bug introductions: {summary.get('num_introductions', len(introductions))}")
    
    return "\n".join(lines)


def save_results_to_file(case_name: str, lhdiff_mappings: Dict[int, List[int]], 
                        bug_results: Dict[str, Any], removed_lines: List[int] = None,
                        inserted_lines: List[int] = None, output_dir: str = "results"):
    """Save both LHDiff and Bug Identifier results to a text file"""
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"{case_name}_results.txt"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"RESULTS FOR: {case_name}\n")
        f.write("=" * 50 + "\n\n")
        
        # LHDiff section
        f.write("LHDIFF MAPPINGS:\n")
        f.write("-" * 20 + "\n")
        f.write(format_lhdiff_output(lhdiff_mappings))
        f.write("\n\n")
        
        #Remove lines from list 
        f.write("\nRemoved lines:\n")
        if removed_lines:
            for idx in removed_lines:
                f.write(f"  Old {idx+1}\n")
        else:
            f.write("  None\n")
        
        #Insert line
        f.write("\nInserted lines:\n")
        if inserted_lines:
            for idx in inserted_lines:
                f.write(f"  New {idx+1}\n")
        else:
            f.write("  None\n")
        
        f.write("\n")
        
        # Bug Identifier section  
        f.write("BUG IDENTIFIER RESULTS:\n")
        f.write("-" * 25 + "\n")
        f.write(format_bug_identifier_output(bug_results))
    
    print(f"Results saved to: {filepath}")


def infer_file_pairs(data_folder="data") -> dict:
    """Group files by test case and sort by version"""
    filesDictionary = {}
    files = os.listdir(data_folder) # List all entries in the data folder
    
    for file in files: # Iterate over each entry in the directory
        path = os.path.join(data_folder, file)
        if os.path.isfile(path): # Split filename into base and extension; only regular files
            base_name, ext = os.path.splitext(file)
            
            # Extract test case name and version
            if "_v" in base_name:
                parts = base_name.split("_v")
                if len(parts) == 2:
                    test_case = parts[0] # The part before "_v" is the test case
                    version = parts[1] # The part after "_v" is the version 
            
                    if test_case not in filesDictionary:
                        filesDictionary[test_case] = {}
                    
                    filesDictionary[test_case][version] = path
    
    #Sort the versions and build final mapping test case
    sorted_files = {}
    for test_case, versions in filesDictionary.items(): # Iterate over each test case and its version mapping
    
        sorted_versions = sorted(versions.keys(), key=lambda x: int(x) if x.isdigit() else x)
        sorted_files[test_case] = [versions[v] for v in sorted_versions]
    
    pop_list = [name for name, files in sorted_files.items() if len(files) < 2] # Find test cases with fewer than 2 versions
    for name in pop_list: # For each such test case, remove it the dictionary
        sorted_files.pop(name)

    return sorted_files


def extract_version_info(filepath: str) -> Tuple[str, str]:
    filename = os.path.basename(filepath) # Get just the filename 
    base_name, ext = os.path.splitext(filename) # Split filename into base name and extension
    
    if "_v" in base_name: # Check if filename follows the pattern with "_v"
        parts = base_name.split("_v") #Split
        if len(parts) == 2:
            return parts[0], parts[1]
    return base_name, "unknown"

 

def run_case(old_file: str, new_file: str) -> Tuple[str, float, float, float, Dict[int, List[int]], List[int], List[int]]:
    old_case, old_ver = extract_version_info(old_file) # Extract test case name and version for the old file
    new_case, new_ver = extract_version_info(new_file) # Extract test case name and version for the new file
    
    case_name = f"{old_case}_v{old_ver}_to_v{new_ver}"
    
    print(f"\n---- LH-DIFF RUN: {case_name} ----")
    print(f"From: {os.path.basename(old_file)}")
    print(f"To: {os.path.basename(new_file)}")
    
    old_lines = build_normalized_lines(old_file)
    new_lines = build_normalized_lines(new_file)

    candidates = generate_candidate_sets(old_lines, new_lines, k=20) # Generate candidate sets for matching using SimHash with k=20
    matcher = DiffMatcher()  # Create a DiffMatcher instance 
    matches = matcher.best_match_for_each_line(old_lines, new_lines, candidates, threshold=0.45)  # Get best match for each old line with threshold 0.45
    resolved = matcher.resolve_conflicts(matches, new_lines)  # Resolve conflicts when multiple old lines match the same new line
    resolved = matcher.detect_reorders(old_lines, new_lines, resolved, threshold=0.4)  # Detect and reordered lines with threshold 0.4


    # --- DIFF SUMMARY CALCULATION ---
    mapped_old = set(resolved.keys()) # Set of all old line that are mapped
    mapped_new = set([new for new, _ in resolved.values() if new != -1]) # Set of new line that are mapped

    all_old = set(range(len(old_lines)))
    all_new = set(range(len(new_lines)))

    removed_lines = sorted(all_old - mapped_old)
    inserted_lines = sorted(all_new - mapped_new)
    # -----------------------------------

    # Build mapping for evaluator
    final_mappings = {}
    for old_idx, (new_idx, score) in resolved.items():  # Iterate over resolved mapping results
        final_mappings[old_idx] = [new_idx]  # Store mapping as a single-element list for each old index
    
    ground_truth = GroundTruth.load_ground_truth(old_file, new_file) # Load ground truth mappings for this file pair
    precision, recall, f1 = evaluate_mapping(final_mappings, ground_truth)
    print_evaluation(case_name, precision, recall, f1)
    return (case_name, precision, recall, f1, final_mappings, removed_lines, inserted_lines)


def run_bug_identifier_for_case(old_file: str, new_file: str, 
                               final_mappings: Dict[int, List[int]],
                               removed_lines: List[int],
                               inserted_lines: List[int]) -> Dict[str, Any]:
    old_case, old_ver = extract_version_info(old_file) # Extract test case and version for old file
    new_case, new_ver = extract_version_info(new_file) # Extract test case and version for new file
    case_name = f"{old_case}_v{old_ver}_to_v{new_ver}" # Build a case name for log and output
    
    print(f"\n---- BUG IDENTIFIER RUN: {case_name} ----")
    
    # Pass the pre-computed LHDiff mappings to avoid re-running LHDiff in bug identifier
    bug_results = run_bug_identifier_for_pair(
        old_file, 
        new_file,
        existing_mappings=final_mappings,
        existing_removed=removed_lines,
        existing_inserted=inserted_lines
    )
    
    # Reformat raw bug identifier results 
    formatted_results = {
        'case_name': case_name,
        'bug_fixes': bug_results['bug_fixes'],
        'bug_introductions': bug_results['bug_introductions'],
        'changed_lines': bug_results['changed_lines'],
        'summary': {
            'num_bug_fixes': bug_results['num_bug_fixes'],
            'num_introductions': bug_results['num_introductions']
        }
    }
    
    return formatted_results


def main():
    data_folder = "data" # Folder where versioned test case files are located
    result_folder = "results"
    filesDictionary = infer_file_pairs(data_folder)
    if not filesDictionary: 
        print("No file pairs found in 'data/'")
        return

    results = []

    # Iterate over each test case and its ordered version list
    for test_case, file_list in filesDictionary.items():
        print(f"\n{'='*60}")
        print(f"Processing Test Case: {test_case}")
        print(f"Versions found: {len(file_list)}")
        print(f"{'='*60}")
        
    # Loop over adjacent pairs of versions
        for i in range(len(file_list) - 1):
            old_file = file_list[i] # Old version path
            new_file = file_list[i + 1] # New version path
            
            old_case, old_ver = extract_version_info(old_file) # Extract from old file
            new_case, new_ver = extract_version_info(new_file) # Extract from new file
            case_name = f"{test_case}_v{old_ver}_to_v{new_ver}"  # Build readable case
            
            print(f"\n--- Processing: {os.path.basename(old_file)} -> {os.path.basename(new_file)} ---")
            
            lhdiff_result = run_case(old_file, new_file) # Run LHDiff and evaluation on this pair
            case_name_result, precision, recall, f1, final_mappings, removed_lines, inserted_lines = lhdiff_result
            results.append((case_name_result, precision, recall, f1))
            
            # Pass the already-computed LHDiff mappings to bug identifier
            bug_results = run_bug_identifier_for_case(
                old_file, 
                new_file, 
                final_mappings, 
                removed_lines, 
                inserted_lines
            )
            
            save_results_to_file(case_name, final_mappings, bug_results, removed_lines, inserted_lines)

    if results: # If at least one version pair was successfully processed
        save_results_csv(results, os.path.join(result_folder, "evaluation_results.csv"))
        average_results(results) # Compute and print
        
        print(f"\n{'='*60}")
        print("PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total version pairs processed: {len(results)}")
        print(f"Results saved to 'results/' directory")
    else:
        print("No successful LH-Diff cases.")


if __name__ == "__main__":
    main()
