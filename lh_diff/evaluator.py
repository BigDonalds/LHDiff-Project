from typing import Dict, List, Tuple
import pandas as pd


def expand_pairs(mapping: Dict[int, List[int]]) -> set:
    """
    converts dicts of old-new mappings into flat (old,new) pairs
    """
    pairs = set()
    for old_idx, mapped in mapping.items():

        # multi-line splits or merges produce a list of new indices
        if isinstance(mapped, list):
            for n in mapped:
                pairs.add((old_idx, n))

        # tuple format; only take the first index
        elif isinstance(mapped, tuple):
            pairs.add((old_idx, mapped[0]))

        # single int mapping, not wrapped in list or tuple
        elif isinstance(mapped, int):
            pairs.add((old_idx, mapped))

    return pairs


def evaluate_mapping(
    predicted: Dict[int, List[int]],
    ground_truth: Dict[int, List[int]]
) -> Tuple[float, float, float]:
    """
    compute standard Precision / Recall / F1 metrics
    """

    pred_pairs = expand_pairs(predicted)
    true_pairs = expand_pairs(ground_truth)

    # intersection gives the true positives
    true_positive = len(pred_pairs & true_pairs)
    # predicted pairs not in truth false positives
    false_positive = len(pred_pairs - true_pairs)
    # truth pairs not predicted false negatives
    false_negative = len(true_pairs - pred_pairs)

    # avoid division by zero
    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 0
    )
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    return precision, recall, f1


def print_evaluation(name: str, precision: float, recall: float, f1: float):
    """
    prints evaluation for single test case
    """
    print(f"\n===== Evaluation: {name} =====")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1 Score:  {f1:.3f}")
    print("==============================\n")


def save_results_csv(results: List[Tuple[str, float, float, float]], path: str = "evaluation_results.csv"):
    """
    save all results to a CSV file
    """
    df = pd.DataFrame(results, columns=["Dataset", "Precision", "Recall", "F1"])
    df.to_csv(path, index=False)
    print(f"Results saved to {path}")


def average_results(results: List[Tuple[str, float, float, float]]):
    if not results:
        print("No results to average.")
        return

    # careful: list indices correspond to metric positions
    avg_precision = sum(r[1] for r in results) / len(results)
    avg_recall = sum(r[2] for r in results) / len(results)
    avg_f1 = sum(r[3] for r in results) / len(results)

    print("\n==== Overall Averages ====")
    print(f"Precision: {avg_precision:.3f}")
    print(f"Recall:    {avg_recall:.3f}")
    print(f"F1 Score:  {avg_f1:.3f}")
    print("==========================\n")
