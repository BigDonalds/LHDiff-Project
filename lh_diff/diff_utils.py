import difflib
from typing import List, Set, Tuple


def get_unchanged_lines_count(old_lines: List[str], new_lines: List[str]) -> int:
    """
    uses difflib.SequenceMatcher to detect unchanged (exactly matching) lines\n
    returns a set of (old_index, new_index) pairs for unchanged lines
    """

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    unchanged_pairs = 0

    # creates list of unchanged lines
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            unchanged_pairs += 1

    return unchanged_pairs


def print_diff_summary(old_lines: List[str], new_lines: List[str]):
    """
    prints summary of changes to file between old and new versions
    """

    unchanged_count = get_unchanged_lines_count(old_lines, new_lines)
    total_old = len(old_lines)
    total_new = len(new_lines)

    print("----- Diff Summary -----")
    print(f"Old file lines: {total_old}")
    print(f"New file lines: {total_new}")
    print(f"Unchanged lines: {unchanged_count}")
    print(f"Changed/Added/Deleted: {total_old - unchanged_count}")  #
    print("------------------------")
