from typing import List, Tuple, Dict
from simhash import Simhash
import heapq


def compute_simhash(text: str) -> int:
    """
    gets the SimHash value for a given string \n
    SimHash is good for approximate text similarity comparison
    """
    return Simhash(text).value


def hamming_distance(hash1: int, hash2: int) -> int:
    return bin(hash1 ^ hash2).count("1")


class SimhashIndex:
    """
    builds and manages SimHash values for a list of lines and finds top-k most similar lines
    """

    def __init__(self, lines: List[str]):
        self.lines = lines
        self.hashes = [compute_simhash(line) for line in lines]

    def get_top_k_candidates(self, target_line: str, k: int = 15) -> List[Tuple[int, int]]:
        """
        for a target line, returns a list of (index, distance) \n
        for the top-k most similar lines (smallest Hamming distance)
        """
        target_hash = compute_simhash(target_line)
        distances = [(i, hamming_distance(target_hash, h)) for i, h in enumerate(self.hashes)]
        
        return heapq.nsmallest(k, distances, key=lambda x: x[1])


def generate_candidate_sets(old_lines: List[str], new_lines: List[str], k: int = 15) -> Dict[int, List[int]]:
    """
    for each old line, generate a candidate list of top-k new line indices \n
    returns a dict: old_index -> [new_indices]
    """
    new_index = SimhashIndex(new_lines)
    candidate_sets = {}

    for old_idx, old_line in enumerate(old_lines):
        top_k = new_index.get_top_k_candidates(old_line, k)
        candidate_sets[old_idx] = [idx for idx, dist in top_k]

    return candidate_sets
