from typing import Dict, List, Tuple
import pandas as pd


# calculates Precision, Recall, and F1 between predicted and ground truth mappings.
def evaluate_mapping(
    predicted: Dict[int, List[int]],
    ground_truth: Dict[int, List[int]]
) -> Tuple[float, float, float]:

    pred_pairs = {(o, n) for o, ns in predicted.items() for n in ns}
    true_pairs = {(o, n) for o, ns in ground_truth.items() for n in ns}

    true_positive = len(pred_pairs & true_pairs)
    false_positive = len(pred_pairs - true_pairs)
    false_negative = len(true_pairs - pred_pairs)

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    return precision, recall, f1

# each case report
def print_evaluation(name: str, precision: float, recall: float, f1: float):

    print(f"\n===== Evaluation: {name} =====")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1 Score:  {f1:.3f}")
    print("==============================\n")

# save report in csv file (path: ~/LHDiff/data/)
def save_results_csv(results: List[Tuple[str, float, float, float]], path: str = "evaluation_results.csv"):

    df = pd.DataFrame(results, columns=["Dataset", "Precision", "Recall", "F1"])
    df.to_csv(path, index=False)
    print(f"Results saved to {path}")

# overall report
def average_results(results: List[Tuple[str, float, float, float]]):

    if not results:
        print("No results to average.")
        return

    avg_precision = sum(r[1] for r in results) / len(results)
    avg_recall = sum(r[2] for r in results) / len(results)
    avg_f1 = sum(r[3] for r in results) / len(results)

    print("\n==== Overall Averages ====")
    print(f"Precision: {avg_precision:.3f}")
    print(f"Recall:    {avg_recall:.3f}")
    print(f"F1 Score:  {avg_f1:.3f}")
    print("==========================\n")
