import re
from rapidfuzz.distance import Levenshtein

def tokenize(line: str):
    tokens = set(re.findall(r"[A-Za-z_]\w*|\d+|[{}();,=+\-*/<>!]+", line))
    common_tokens = {'{', '}', '(', ')', ';', ',', '='}
    return tokens - common_tokens

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0

def structural_fingerprint(line: str) -> int:
    cleaned = re.sub(r'//.*|".*?"|\'.*?\'', '', line)
    structural_tokens = re.findall(r'[A-Za-z_]\w*(?=\s*\()|\b(?:if|else|for|while|return|new)\b|[{}();]', cleaned)
    return hash(tuple(sorted(set(structural_tokens))))

def normalized_levenshtein(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    dist = Levenshtein.distance(a, b)
    max_len = max(len(a), len(b))
    return 1 - (dist / max_len) if max_len > 0 else 0

def is_control_flow_line(line: str) -> bool:
    return bool(re.search(r'\b(?:if|else|for|while|return|switch|case)\b', line))

def is_structural_line(line: str) -> bool:
    line = line.strip()
    if len(line) <= 2:
        return True
    if line in ['{', '}', '};', '();']:
        return True
    if re.match(r'^\s*[{}();]\s*$', line):
        return True
    return False

def calculate_semantic_similarity(old_line: str, new_line: str) -> float:
    old_tokens = tokenize(old_line)
    new_tokens = tokenize(new_line)
    
    token_sim = jaccard(old_tokens, new_tokens)
    string_sim = normalized_levenshtein(old_line, new_line)
    
    old_structural = set(re.findall(r'[A-Za-z_]\w*(?=\s*\()|\b(?:if|else|for|while|return|new)\b', old_line))
    new_structural = set(re.findall(r'[A-Za-z_]\w*(?=\s*\()|\b(?:if|else|for|while|return|new)\b', new_line))
    structural_sim = jaccard(old_structural, new_structural)
    
    if is_control_flow_line(old_line) and is_control_flow_line(new_line):
        weights = [0.3, 0.3, 0.4]
    elif is_structural_line(old_line) and is_structural_line(new_line):
        weights = [0.2, 0.3, 0.5]
    else:
        weights = [0.5, 0.3, 0.2]
    
    return (weights[0] * token_sim + 
            weights[1] * string_sim + 
            weights[2] * structural_sim)

def build_ground_truth(old_lines, new_lines):
    n_old = len(old_lines)
    n_new = len(new_lines)

    similarity_matrix = [[0.0] * n_new for _ in range(n_old)]
    for i in range(n_old):
        for j in range(n_new):
            similarity_matrix[i][j] = calculate_semantic_similarity(old_lines[i], new_lines[j])

    gt = {}
    used_new_indices = set()
    
    for i in range(n_old):
        for j in range(n_new):
            if similarity_matrix[i][j] > 0.95 and j not in used_new_indices:
                gt[i] = [j]
                used_new_indices.add(j)
                break

    for i in range(n_old):
        if i in gt:
            continue
            
        old_line = old_lines[i]
        if is_control_flow_line(old_line) or 'return' in old_line:
            best_match = None
            best_score = 0.0
            
            for j in range(n_new):
                if j in used_new_indices:
                    continue
                    
                new_line = new_lines[j]
                if (is_control_flow_line(new_line) or 'return' in new_line) and similarity_matrix[i][j] > 0.7:
                    position_penalty = abs(i - j) / 10.0
                    adjusted_score = similarity_matrix[i][j] * (1 - position_penalty)
                    
                    if adjusted_score > best_score:
                        best_score = adjusted_score
                        best_match = j
            
            if best_match is not None:
                gt[i] = [best_match]
                used_new_indices.add(best_match)

    for i in range(n_old):
        if i in gt:
            continue
            
        best_match = None
        best_score = 0.0
        
        search_start = max(0, i - 8)
        search_end = min(n_new, i + 9)
        
        for j in range(search_start, search_end):
            if j in used_new_indices:
                continue
                
            score = similarity_matrix[i][j]
            position_penalty = abs(i - j) / 20.0
            adjusted_score = score * (1 - position_penalty)
            
            if adjusted_score > best_score and adjusted_score > 0.6:
                best_score = adjusted_score
                best_match = j
        
        if best_match is not None:
            gt[i] = [best_match]
            used_new_indices.add(best_match)

    for i in range(n_old):
        if i in gt:
            continue
            
        best_match = None
        best_score = 0.0
        
        for j in range(n_new):
            if j in used_new_indices:
                continue
                
            score = similarity_matrix[i][j]
            if score > best_score and score > 0.4:
                best_score = score
                best_match = j
        
        if best_match is not None:
            gt[i] = [best_match]
            used_new_indices.add(best_match)

    unmapped_count = 0
    for i in range(n_old):
        if i not in gt:
            best_match = None
            best_score = 0.0
            
            for j in range(n_new):
                score = similarity_matrix[i][j]
                if score > best_score:
                    best_score = score
                    best_match = j
            
            if best_match is not None and best_score > 0.3:
                gt[i] = [best_match]
            else:
                unmapped_count += 1

    return gt