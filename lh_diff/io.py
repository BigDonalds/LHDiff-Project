import re
from typing import List


# returns a list of raw lines (without \n characters).
def read_file(filepath: str) -> List[str]:

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.rstrip('\n') for line in f]
    return lines


def normalize_line(line: str, remove_comments: bool = True, lowercase: bool = False) -> str:
    # remove whitespace and replace multiple spaces with one
    line = line.strip()
    line = re.sub(r'\s+', ' ', line)

    if remove_comments:
        line = re.sub(r'//.*', '', line)        # C/Java style
        line = re.sub(r'#.*', '', line)         # Python/Unix style
        line = re.sub(r'/\*.*?\*/', '', line)   # Block comments

    # remove punctuation and braces
    line = re.sub(r'[;,\(\)\{\}\[\]]', '', line)

    if lowercase:
        line = line.lower()

    return line.strip()


# reads and normalizes all lines from a file
# returns list of normalized strings (empty lines kept as '')
def build_normalized_lines(filepath: str, remove_comments: bool = True, lowercase: bool = False) -> List[str]:

    raw_lines = read_file(filepath)
    norm_lines = [normalize_line(line, remove_comments, lowercase) for line in raw_lines]
    return norm_lines
