"""
GroundTruth – Loader for manually annotated semantic diff data.

This module reads a single JSON file (`data/ground_truth.json`) that contains
human-verified line mappings and bug-identifier results for a set of test cases.

The ground truth is used to:
- Evaluate the accuracy of automated diff matchers (DiffMatcher)
- Measure precision/recall of line-level mappings
- Validate bug detection logic across refactoring versions
"""

import os
import json
from typing import Dict, List, Any, Tuple


class GroundTruth:
    """
    Static utility class.
    Loads the ground-truth JSON once at import time.
    """

    # Path to the single source of truth (human-annotated data)
    _json_file_path = os.path.join("data", "ground_truth.json")

    # Load the JSON at import time – if file is missing or malformed, fall back to empty dict
    try:
        with open(_json_file_path, "r", encoding="utf-8") as f:
            GROUND_TRUTH = json.load(f)
    except Exception as e:
        print(f"[GroundTruth] Warning: Could not load ground truth from {_json_file_path}: {e}")
        GROUND_TRUTH = {}


    @staticmethod
    def load_ground_truth(old_file: str, new_file: str) -> Dict[int, List[int]]:
        """
        Load the line-level mapping for the given file pair.

        Returns:
            Mapping from old version line numbers (0-based) -> list of new version line numbers.
            Format expected by the evaluator: { old_index: [new_index, ...] }

        Example:
            { 5: [7], 6: [8, 9] }  → line 6 in old file was split into lines 8 and 9 in new file
        """
        test_id, old_ver = GroundTruth._extract_version_info(old_file)
        _, new_ver = GroundTruth._extract_version_info(new_file)

        version_key = f"v{old_ver}-v{new_ver}"

        try:
            # Expected structure: GROUND_TRUTH[test_id]["lhdiff"][version_key] = [[old, new], ...]
            mapping_list = GroundTruth.GROUND_TRUTH[test_id]["lhdiff"][version_key]
        except KeyError:
            return {}

        # Convert from 1-based (as stored in JSON) -> 0-based (as used internally)
        return {old - 1: [new - 1] for old, new in mapping_list}


    @staticmethod
    def load_bug_truth(old_file: str, new_file: str) -> Dict[str, Any]:
        """
        Load bug-identifier ground truth for this version transition.
        Returns whatever metadata was stored under "bug_identifier" for this pair
        
        Note: This function is a place holder since the assignmnet didnt specify a specific
        evaluation for bug identifying process. The program still gives detailed report in
        a text file located in result folder.
        """
        test_id, old_ver = GroundTruth._extract_version_info(old_file)
        _, new_ver = GroundTruth._extract_version_info(new_file)

        version_key = f"v{old_ver}-v{new_ver}"

        # traverse nested dicts – return empty dict if anything is missing
        return (
            GroundTruth.GROUND_TRUTH.get(test_id, {})
            .get("bug_identifier", {})
            .get(version_key, {})
        )

    @staticmethod
    def _extract_version_info(filename: str) -> Tuple[str, str]:
        """
        Parse test case ID and version number from filenames like:
            - mytest_v1.java  → ("mytest", "1")
            - mytest_v2.java  → ("mytest", "2")
            - mytest.java     → ("mytest", "1")  (fallback)
        """
        base = os.path.basename(filename).split(".")[0]

        if "_v" in base:
            parts = base.split("_v")
            test_id = parts[0]
            version = parts[1]
            return test_id, version

        return base, "1"
