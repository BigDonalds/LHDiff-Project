import re
from typing import List


def read_file(filepath: str) -> List[str]:
    """
    returns a list of raw lines (without \\n characters).
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f]
    return lines


def normalize_line(
    line: str, remove_comments: bool = True, lowercase: bool = False
) -> str:
    """
    remove whitespace and replace multiple spaces with one
    """
    line = line.strip()
    line = re.sub(r"\s+", " ", line)

    # block comments are handled in more detail in normalize_block_comments, here a simple check is completed.
    if remove_comments:
        line = re.sub(r"//.*", "", line)  # C/Java style
        line = re.sub(r"#.*", "", line)  # Python/Unix style
        line = re.sub(
            r"\'\'\'.*?\'\'\'", "", line
        )  # python block comments (though not integrated into the language natively, this is the standard form of block comments in python)
        line = re.sub(r"/\*.*?\*/", "", line)  # Block comments

    # remove punctuation and braces
    # line = re.sub(r'[;,\(\)\{\}\[\]]', '', line)

    if lowercase:
        line = line.lower()

    return line.strip()

def normalize_block_comments(norm_lines:list[str]) -> list[str]:
    # not using for loop as norm_lines will be altered and the length will change
    currentLineIndex = 0
    maxLineIndex = len(norm_lines)
    while currentLineIndex < maxLineIndex:
        if re.search(r"(\'\'\'|\"\"\"|/\*)", norm_lines[currentLineIndex]): # opening
            norm_lines[currentLineIndex] = re.sub(r"(\'\'\'|\"\"\"|/\*).*$", "", norm_lines[currentLineIndex])
            currentLineIndex+=1
            while not re.search(r"(\'\'\'|\"\"\"|\*/)", norm_lines[currentLineIndex]):
                norm_lines[currentLineIndex] = ""
                currentLineIndex+=1
            norm_lines[currentLineIndex] = re.sub(r".*?(\'\'\'|\"\"\"|\*/)", "", norm_lines[currentLineIndex])
        currentLineIndex+=1
        maxLineIndex = len(norm_lines)
    return norm_lines

def build_normalized_lines(
    filepath: str, remove_comments: bool = True, lowercase: bool = False
) -> List[str]:
    """
    reads and normalizes all lines from a file\n
    returns list of normalized strings (empty lines kept as '')
    """
    raw_lines = read_file(filepath)
    # each line is normalized and contained in a list
    norm_lines = [
        normalize_line(line, remove_comments, lowercase) for line in raw_lines
    ]

    norm_lines = normalize_block_comments(norm_lines)

    return norm_lines
