from typing import List
from rapidfuzz.distance import Levenshtein
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import warnings
import re


def normalize_code(line: str) -> str:
    """
    replaces variable names and numbers to make comparisons structural
    """
    line = re.sub(r"\b\d+\b", "NUM", line)
    line = re.sub(r"\b[_a-zA-Z]\w*\b", "VAR", line)
    return line


def content_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    norm_a = normalize_code(a)
    norm_b = normalize_code(b)

    distance = Levenshtein.distance(norm_a, norm_b)
    max_len = max(len(norm_a), len(norm_b))
    return 1 - (distance / max_len)


def build_context(lines: List[str], index: int, window: int = 4) -> str:
    """
    makes a context string around a line using 'window' lines above and below
    """
    start = max(0, index - window)
    end = min(len(lines), index + window + 1)
    context_slice = lines[start:end]
    return " ".join(context_slice)


def context_similarity(a_context: str, b_context: str) -> float:
    """
    calculates cosine similarity between two context strings using TF-IDF
    """
    if not a_context.strip() or not b_context.strip():
        return 0.0

    try:
        vectorizer = TfidfVectorizer().fit([a_context, b_context])
        vectors = vectorizer.transform([a_context, b_context])
        similarity = cosine_similarity(vectors[0], vectors[1])[0][0]
        return float(similarity)

    except ValueError as e:
        if "empty vocabulary" in str(e).lower():
            warnings.warn(
                "Empty vocabulary detected — skipping context similarity for this pair.",
                RuntimeWarning,
            )
            return 0.0
        else:
            raise e


def combined_similarity(
    a: str,
    b: str,
    a_context: str,
    b_context: str,
    weight_content: float = 0.6,
    weight_context: float = 0.4,
) -> float:
    """
    mixes content and context similarity with said weights
    """
    c_sim = content_similarity(a, b)
    x_sim = context_similarity(a_context, b_context)
    return (weight_content * c_sim) + (weight_context * x_sim)
