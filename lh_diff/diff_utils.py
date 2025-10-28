import difflib
from typing import List, Set, Tuple


# uses difflib.SequenceMatcher to detect unchanged (exactly matching) lines
# returns a set of (old_index, new_index) pairs for unchanged lines
def get_unchanged_lines(old_lines: List[str], new_lines: List[str]) -> Set[Tuple[int, int]]:

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    unchanged_pairs = set()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                unchanged_pairs.add((i, j))

    return unchanged_pairs


def print_diff_summary(old_lines: List[str], new_lines: List[str]) -> None:

    unchanged = get_unchanged_lines(old_lines, new_lines)
    total_old = len(old_lines)
    total_new = len(new_lines)
    unchanged_count = len(unchanged)

    print("----- Diff Summary -----")
    print(f"Old file lines: {total_old}")
    print(f"New file lines: {total_new}")
    print(f"Unchanged lines: {unchanged_count}")
    print(f"Changed/Added/Deleted: {total_old - unchanged_count}")
    print("------------------------")
