import os
import re
from typing import List, Dict, Tuple, Optional
from lh_diff.io import read_file, build_normalized_lines
from lh_diff.simhash_index import generate_candidate_sets
from lh_diff.matcher import DiffMatcher

# Extract numeric version from filename using common patterns
def extract_version_number(filename: str) -> Optional[int]:
    patterns = [
        r'_(\d+)\.txt$',
        r'v(\d+)',
        r'_v(\d+)',
        r'(\d+)_old',
        r'(\d+)_new',
        r'old_(\d+)',
        r'new_(\d+)',
        r'version(\d+)',
        r'ver(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

# Sort list for files that shares a base name
def build_version_timeline(data_folder: str, base_name: str) -> List[Tuple[str, int]]:
    files = os.listdir(data_folder)
    versions = []
    
    for file in files:
        filepath = os.path.join(data_folder, file)
        if not os.path.isfile(filepath):
            continue
        
        file_base_name, ext = os.path.splitext(file)
        
        if len(file_base_name) < 2:
            continue
    
        # Consider files that start with this 'base_name'
        if file_base_name.startswith(base_name):
            version_num = extract_version_number(file)
            if version_num is None:
                if '_v' in file_base_name:
                    parts = file_base_name.split('_v')
                    if len(parts) == 2 and parts[1].isdigit():
                        version_num = int(parts[1])
                    elif '_old' in file or 'old_' in file:
                        version_num = 1
                    elif '_new' in file or 'new_' in file:
                        version_num = 2
                    else:
                        continue
                else:
                    continue
            
            versions.append((filepath, version_num))
    # Sort by version number
    versions.sort(key=lambda x: x[1])
    return versions

# compute line-level changes between two versions and annotate each change
def get_changed_lines(old_file: str, new_file: str, 
                     existing_mappings: Optional[Dict[int, List[int]]] = None,
                     existing_removed: Optional[List[int]] = None,
                     existing_inserted: Optional[List[int]] = None) -> List[Dict]:
    old_lines = build_normalized_lines(old_file)
    new_lines = build_normalized_lines(new_file)
    old_raw = read_file(old_file)
    new_raw = read_file(new_file)
    
    # Use existing mappings if provided to avoid re-running LHDiff
    if existing_mappings is not None:
        # Convert the mapping format to match what the matcher produces
        split_map = {}
        for old_idx, new_indices in existing_mappings.items():
            if isinstance(new_indices, list):
                split_map[old_idx] = new_indices
            else:
                split_map[old_idx] = [new_indices]
        
        # Build mapped_new_indices from existing mappings
        mapped_new_indices = set()
        for new_indices in split_map.values():
            if isinstance(new_indices, list):
                for idx in new_indices:
                    if idx != -1:  # -1 might indicate no mapping
                        mapped_new_indices.add(idx)
            elif new_indices != -1:
                mapped_new_indices.add(new_indices)
    else:
        # Or compute mappings from scratch
        matcher = DiffMatcher()
        candidates = generate_candidate_sets(old_lines, new_lines, k=25)
        matches = matcher.best_match_for_each_line(old_lines, new_lines, candidates, threshold=0.38)
        matches = matcher.resolve_conflicts(matches, new_lines)
        matches = matcher.detect_reorders(old_lines, new_lines, matches)
        split_map = matcher.detect_line_splits(old_lines, new_lines, matches)
        
        # Build mapped_new_indices
        mapped_new_indices = set()
        for old_idx, new_idxs in split_map.items():
            if not isinstance(new_idxs, list):
                new_idxs = [new_idxs]
            for new_idx in new_idxs:
                if new_idx != -1:
                    mapped_new_indices.add(new_idx)
    
    changed = []
    
    # Handle edits using split_map (whether from existing_mappings or computed)
    for old_idx, new_idxs in split_map.items():
        if not isinstance(new_idxs, list):
            new_idxs = [new_idxs]
        
        for new_idx in new_idxs:
            if new_idx == -1:  # No mapping
                continue
                
            # Ensure indices are within bounds
            old_text = old_raw[old_idx] if old_idx < len(old_raw) else ""
            new_text = new_raw[new_idx] if new_idx < len(new_raw) else ""

            # Only consider it a change if actual text differs 
            if old_text.strip() != new_text.strip():
                semantics = analyze_change_semantics(old_text, new_text)
                changed.append({
                    'old_line_num': old_idx + 1,
                    'old_text': old_text,
                    'new_line_num': new_idx + 1,
                    'new_text': new_text,
                    'semantics': semantics,
                    'bug_fix_score': semantics['bug_fix_score']
                })
    
    # Handle inserted lines
    # If we have existing_inserted list, use it directly
    if existing_inserted is not None:
        for idx in existing_inserted:
            if idx < len(new_raw) and new_raw[idx].strip():
                semantics = analyze_change_semantics("", new_raw[idx])
                changed.append({
                    'old_line_num': None,
                    'old_text': None,
                    'new_line_num': idx + 1,
                    'new_text': new_raw[idx],
                    'semantics': semantics,
                    'bug_fix_score': semantics['bug_fix_score']
                })
    else:
        # Or find inserted lines by checking mapped indices
        for idx, line in enumerate(new_raw):
            if idx not in mapped_new_indices and line.strip():
                semantics = analyze_change_semantics("", line)
                changed.append({
                    'old_line_num': None,
                    'old_text': None,
                    'new_line_num': idx + 1,
                    'new_text': line,
                    'semantics': semantics,
                    'bug_fix_score': semantics['bug_fix_score']
                })
    
    # Rank changes based on how the bug could be fixed
    changed.sort(key=lambda x: x['bug_fix_score'], reverse=True)
    return changed

def analyze_change_semantics(old_line: str, new_line: str) -> Dict[str, float]:
    analysis = {
        'is_defensive': 0.0,
        'is_validation': 0.0,
        'is_error_handling': 0.0,
        'is_null_check': 0.0,
        'is_bounds_check': 0.0,
        'is_type_fix': 0.0,
        'is_encoding_fix': 0.0,
        'is_logic_fix': 0.0,
        'bug_fix_score': 0.0
    }
    
    if not old_line and not new_line:
        return analysis
    
    old_lower = old_line.lower() if old_line else ""
    new_lower = new_line.lower() if new_line else ""
    
    # Comments describing the bug/fix
    is_bug_comment = any(word in old_lower for word in ['bug:', 'bugfix:', 'fix:', 'error:', 'issue:', 'problem:', 'vulnerability:', 'security:'])
    is_fix_comment = any(word in new_lower for word in ['fix:', 'fixed:', 'resolve:', 'patch:', 'correct:', 'solution:', 'guard:', 'validation:'])
    
    if is_bug_comment and is_fix_comment:
        analysis['bug_fix_score'] = 0.15
    
    # Pattern sets
    defensive_patterns = [
        (r'if\s+(!|not\s+)\w+', 0.45),
        (r'if\s+\w+\s+(is\s+)?(==\s+)?null', 0.45),
        (r'if\s+\w+\s+(is\s+)?(==\s+)?none', 0.45),
        (r'if\s+\w+\s+is\s+not\s+(null|none)', 0.35),
        (r'assert\s+', 0.35),
        (r'raise\s+', 0.4),
        (r'throw\s+', 0.4),
        (r'catch\s*\(', 0.45),
        (r'finally\s*{', 0.3),
        (r'throws\s+', 0.35),
    ]
    
    validation_patterns = [
        (r'validate\w*', 0.45),
        (r'check\w*', 0.35),
        (r'verify\w*', 0.4),
        (r'isvalid\w*', 0.45),
        (r'is_valid\w*', 0.45),
        (r'len\([^)]+\)\s*[<>=!]=?', 0.4),
        (r'\.length\s*[<>=!]=?', 0.4),
        (r'\.size\s*\(\)\s*[<>=!]=?', 0.4),
        (r'\.isEmpty\s*\(\)', 0.35),
        (r'\.isBlank\s*\(\)', 0.35),
        (r'==\s*0', 0.3),
        (r'!=\s*0', 0.3),
        (r'<\s*0', 0.3),
        (r'>\s*0', 0.3),
    ]
    
    error_handling_patterns = [
        (r'try\s*{', 0.55),
        (r'try:', 0.55),
        (r'except\s', 0.55),
        (r'catch\s', 0.55),
        (r'error', 0.35),
        (r'exception', 0.4),
        (r'throw\s+new\s+', 0.5),
        (r'IllegalArgumentException', 0.45),
        (r'RuntimeException', 0.45),
        (r'ArithmeticException', 0.5),
        (r'DivideByZeroException', 0.55),
        (r'NullPointerException', 0.5),
        (r'ArrayIndexOutOfBoundsException', 0.5),
    ]
    
    null_check_patterns = [
        (r'if\s+(!|not\s+)\w+', 0.55),
        (r'if\s+\w+\s+(is\s+)?(==\s+)?null', 0.55),
        (r'if\s+\w+\s+(is\s+)?(==\s+)?none', 0.55),
        (r'if\s+\w+\s+!=?\s+(null|none)', 0.45),
        (r'Objects\.requireNonNull', 0.5),
        (r'\.orElse', 0.4),
        (r'\.getOrElse', 0.4),
        (r'Optional\.', 0.4),
    ]
    
    bounds_patterns = [
        (r'\.length\s*[<>]', 0.5),
        (r'\.size\s*\(\)\s*[<>]', 0.5),
        (r'len\([^)]+\)\s*[<>]', 0.5),
        (r'index\s*[<>]', 0.5),
        (r'out\s+of\s+bounds', 0.6),
        (r'array\s+index', 0.55),
        (r'string\s+index', 0.55),
        (r'\.substring\s*\(', 0.4),
        (r'\.charAt\s*\(', 0.4),
        (r'\[.*\]', 0.35),
    ]
    
    logic_fix_patterns = [
        (r'return\s+(0|false|null|none)', 0.4),
        (r'return\s+true', 0.4),
        (r'break', 0.3),
        (r'continue', 0.3),
        (r'else\s+return', 0.35),
        (r'default:', 0.3),
        (r'switch', 0.3),
    ]
    
    # Group patterns
    pattern_categories = [
        (defensive_patterns, 'is_defensive'),
        (validation_patterns, 'is_validation'),
        (error_handling_patterns, 'is_error_handling'),
        (null_check_patterns, 'is_null_check'),
        (bounds_patterns, 'is_bounds_check'),
        (logic_fix_patterns, 'is_logic_fix'),
    ]
    
    # Score patterns that appear in the new line but not in the old line
    for patterns, key in pattern_categories:
        for pattern, score in patterns:
            if re.search(pattern, new_lower, re.IGNORECASE) and not re.search(pattern, old_lower, re.IGNORECASE):
                analysis[key] = max(analysis[key], score)
    
    # Keyword tweaks on top of patterns
    error_keywords = ['try', 'catch', 'except', 'finally', 'throw', 'throws', 'raise']
    old_words = set(old_lower.split())
    new_words = set(new_lower.split())
    
    for keyword in error_keywords:
        if keyword in new_words and keyword not in old_words:
            analysis['is_error_handling'] = max(analysis['is_error_handling'], 0.45)
    
    null_keywords = ['null', 'none', 'nil', 'optional', 'nullable']
    for keyword in null_keywords:
        if keyword in new_words and keyword not in old_words:
            analysis['is_null_check'] = max(analysis['is_null_check'], 0.4)
    
    validation_keywords = ['validate', 'check', 'verify', 'assert', 'guard', 'ensure', 'protect']
    for keyword in validation_keywords:
        if keyword in new_words and keyword not in old_words:
            analysis['is_validation'] = max(analysis['is_validation'], 0.4)
    
    if any(op in new_lower for op in ['/', '%', 'divide', 'mod']) and not any(op in old_lower for op in ['/', '%', 'divide', 'mod']):
        if any(check in new_lower for check in ['if', 'check', 'verify', '!= 0', '> 0', '== 0']):
            analysis['is_validation'] = max(analysis['is_validation'], 0.45)
    
    if 'null' in old_lower and 'null' not in new_lower and '=' in new_lower:
        analysis['is_null_check'] = max(analysis['is_null_check'], 0.35)
    
    # Combine semantic flags 
    analysis['bug_fix_score'] = (
        analysis['is_defensive'] * 0.15 +
        analysis['is_validation'] * 0.20 +
        analysis['is_error_handling'] * 0.30 +
        analysis['is_null_check'] * 0.25 +
        analysis['is_bounds_check'] * 0.15 +
        analysis['is_type_fix'] * 0.05 +
        analysis['is_encoding_fix'] * 0.05 +
        analysis['is_logic_fix'] * 0.05
    )
    
    if is_bug_comment or is_fix_comment:
        analysis['bug_fix_score'] = min(1.0, analysis['bug_fix_score'] + 0.1)
    
    if old_line and new_line and not old_lower.startswith('//') and not old_lower.startswith('*'):
        if analysis['bug_fix_score'] > 0:
            analysis['bug_fix_score'] = min(1.0, analysis['bug_fix_score'] * 1.2)
    
    return analysis

# Find the most likely originating line in previous_file for a given line in current_file.
def blame(line_text: str, line_num: int, current_file: str, previous_file: str) -> Tuple[Optional[int], float]:
    if not line_text or not line_text.strip():
        return (None, 0.0)
    
    if not os.path.exists(previous_file):
        return (None, 0.0)
    
    old_lines = build_normalized_lines(previous_file)
    new_lines = build_normalized_lines(current_file)
    old_raw = read_file(previous_file)
    new_raw = read_file(current_file)
    
    if line_num > len(new_raw):
        return (None, 0.0)
    
    target_line = new_raw[line_num - 1] if line_num <= len(new_raw) else ""
    target_normalized = build_normalized_lines(current_file)[line_num - 1] if line_num <= len(new_lines) else ""
    
    # To limit comparisons
    candidates = generate_candidate_sets([target_normalized], old_lines, k=15)
    
    if 0 not in candidates or not candidates[0]:
        return (None, 0.0)
    
    matcher = DiffMatcher()
    matches = matcher.best_match_for_each_line([target_normalized], old_lines, {0: candidates[0]}, threshold=0.35)
    
    # If matcher finds direct match, use it
    if 0 in matches:
        matched_idx, confidence = matches[0]
        return (matched_idx + 1, confidence)
    
    best_match_idx = None
    best_confidence = 0.0
    
    for old_idx in candidates[0][:10]:
        old_normalized = old_lines[old_idx]
        old_actual = old_raw[old_idx] if old_idx < len(old_raw) else ""
        
        if target_normalized == old_normalized:
            return (old_idx + 1, 1.0)
        
        if target_line and old_actual:
            target_words = set(target_line.lower().split())
            old_words = set(old_actual.lower().split())
            if target_words and old_words:
                overlap = len(target_words & old_words) / max(len(target_words), len(old_words))
                if overlap > 0.7 and overlap > best_confidence:
                    best_confidence = overlap
                    best_match_idx = old_idx
    
    if best_match_idx is not None and best_confidence > 0.5:
        return (best_match_idx + 1, best_confidence)
    
    return (None, 0.0)

# Filter changed lines that are likely to be bug fixes
def detect_potential_bug_fixes(changed_lines: List[Dict]) -> List[Dict]:
    potential_fixes = []
    
    for change in changed_lines:
        score = change['bug_fix_score']
        semantics = change['semantics']
        
        if score < 0.15:
            continue

        is_potential_fix = (
            semantics['is_error_handling'] > 0.25 or
            semantics['is_null_check'] > 0.25 or
            semantics['is_bounds_check'] > 0.25 or
            semantics['is_validation'] > 0.25 or
            semantics['is_defensive'] > 0.25 or
            score > 0.20
        )
        
        if is_potential_fix:
            fix_info = change.copy()
            fix_info['is_potential_fix_reason'] = []
            if semantics['is_error_handling'] > 0.25:
                fix_info['is_potential_fix_reason'].append(f"error_handling:{semantics['is_error_handling']:.2f}")
            if semantics['is_null_check'] > 0.25:
                fix_info['is_potential_fix_reason'].append(f"null_check:{semantics['is_null_check']:.2f}")
            if semantics['is_bounds_check'] > 0.25:
                fix_info['is_potential_fix_reason'].append(f"bounds_check:{semantics['is_bounds_check']:.2f}")
            if semantics['is_validation'] > 0.25:
                fix_info['is_potential_fix_reason'].append(f"validation:{semantics['is_validation']:.2f}")
            if semantics['is_defensive'] > 0.25:
                fix_info['is_potential_fix_reason'].append(f"defensive:{semantics['is_defensive']:.2f}")
            if score > 0.20:
                fix_info['is_potential_fix_reason'].append(f"high_score:{score:.2f}")
            
            potential_fixes.append(fix_info)
    
    return potential_fixes

# Reverse through the timeline to find where the buggy line likely first appeared
def trace_bug_introduction(buggy_line: str, buggy_line_num: int, current_file: str, timeline: List[Tuple[str, int]]) -> Tuple[str, int, float]:
    current_idx = next((i for i, (f, v) in enumerate(timeline) if f == current_file), -1)
    
    # If file can not be found, assume it's here
    if current_idx <= 0:
        return (current_file, timeline[current_idx][1] if current_idx >= 0 else -1, 1.0)
    
    if not buggy_line or not buggy_line.strip():
        return (current_file, timeline[current_idx][1], 0.5)
    
    # Reverse through previous version and use blame on the line
    for i in range(current_idx - 1, -1, -1):
        prev_file, prev_version = timeline[i]
        
        blamed_line_num, confidence = blame(buggy_line, buggy_line_num, current_file, prev_file)
        
        if blamed_line_num and confidence > 0.6:
            if i > 0:
                result = trace_bug_introduction(buggy_line, blamed_line_num, prev_file, timeline)
                if result[2] > confidence:
                    return result
            return (prev_file, prev_version, confidence)
    
    return (current_file, timeline[current_idx][1], 0.3)

# Analyze all versions of files to detect bug fixes
def analyze_version_evolution(file_pairs: Dict[str, List[str]], data_folder: str) -> Dict[str, any]:
    results = {}
    
    for base_name, file_list in file_pairs.items():
        if len(file_list) < 2:
            continue
        
        file_list_with_versions = []
        for file_path in file_list:
            file_base_name, ext = os.path.splitext(os.path.basename(file_path))
            if len(file_base_name) >= 2:
                version_suffix = file_base_name[-2:]
                if version_suffix.isdigit():
                    file_list_with_versions.append((file_path, int(version_suffix)))
                else:
                    version_num = extract_version_number(file_base_name)
                    if version_num is not None:
                        file_list_with_versions.append((file_path, version_num))
                    else:
                        file_list_with_versions.append((file_path, len(file_list_with_versions) + 1))
            else:
                file_list_with_versions.append((file_path, len(file_list_with_versions) + 1))
        
        file_list_with_versions.sort(key=lambda x: x[1])
        timeline = file_list_with_versions
        
        if len(timeline) < 2:
            continue
        
        all_bug_fixes = []
        all_bug_introductions = []
        
        # Compare each version with the next in the timeline
        for i in range(len(timeline) - 1):
            old_file = timeline[i][0]
            new_file = timeline[i + 1][0]
            
            if not os.path.exists(old_file) or not os.path.exists(new_file):
                continue
            
            changed_lines = get_changed_lines(old_file, new_file)
            potential_fixes = detect_potential_bug_fixes(changed_lines)
            
            for fix in potential_fixes:
                buggy_line = fix['old_text'] if fix['old_text'] else fix['new_text']
                buggy_line_num = fix['old_line_num'] if fix['old_line_num'] else fix['new_line_num']
                
                if not buggy_line or not buggy_line_num:
                    continue
                
                intro_file, intro_version, intro_confidence = trace_bug_introduction(
                    buggy_line,
                    buggy_line_num,
                    old_file,
                    timeline
                )
                
                all_bug_fixes.append({
                    'version_pair': (old_file, new_file),
                    'old_line': fix['old_line_num'],
                    'new_line': fix['new_line_num'],
                    'old_text': fix['old_text'],
                    'new_text': fix['new_text'],
                    'bug_fix_score': fix['bug_fix_score'],
                    'semantics': fix['semantics']
                })
                
                all_bug_introductions.append({
                    'buggy_line': buggy_line,
                    'buggy_line_num': buggy_line_num,
                    'introduced_in': intro_file,
                    'introduced_version': intro_version,
                    'confidence': intro_confidence
                })
        
        if all_bug_fixes:
            results[base_name] = {
                'timeline': timeline,
                'bug_fixes': all_bug_fixes,
                'bug_introductions': all_bug_introductions
            }
        else:
            results[base_name] = {
                'timeline': timeline,
                'bug_fixes': [],
                'bug_introductions': []
            }
    
    return results

# Group files in folder by base name and run version analysis with at least 2 versions. 
def find_bug_introductions(data_folder: str = "data") -> Dict[str, any]:
    files = os.listdir(data_folder)
    file_pairs = {}
    
    for file in files:
        path = os.path.join(data_folder, file)
        if not os.path.isfile(path):
            continue
        
        base_name, ext = os.path.splitext(file)
        
        if len(base_name) < 2:
            continue
        
        if '_v' in base_name:
            base_name = base_name.split('_v')[0]
        elif base_name[-2:].isdigit():
            base_name = base_name[:-2]
        
        if base_name not in file_pairs:
            file_pairs[base_name] = []
        
        file_pairs[base_name].append(path)
    
    # Only keep groups that have atleast 2 versions
    for base_name in list(file_pairs.keys()):
        if len(file_pairs[base_name]) < 2:
            del file_pairs[base_name]
    
    results = analyze_version_evolution(file_pairs, data_folder)
    
    return results

# Create a high-level summary of bug fixes and introductions over all cases.
def generate_report(results: Dict[str, any]) -> Dict[str, any]:
    report = {
        'total_cases': len(results),
        'total_bug_fixes': 0,
        'total_introductions': 0,
        'cases': []
    }
    
    for case_name, case_data in results.items():
        num_fixes = len(case_data['bug_fixes'])
        num_intros = len(case_data['bug_introductions'])
        
        report['total_bug_fixes'] += num_fixes
        report['total_introductions'] += num_intros
        
        case_report = {
            'case_name': case_name,
            'num_bug_fixes': num_fixes,
            'num_introductions': num_intros,
            'bug_fixes': case_data['bug_fixes'],
            'introductions': case_data['bug_introductions']
        }
        
        report['cases'].append(case_report)
    
    return report

# Check timelines and flag low-confidence introduction
def validate_results(results: Dict[str, any]) -> Dict[str, any]:
    validation = {
        'valid_cases': 0,
        'invalid_cases': 0,
        'warnings': []
    }
    
    for case_name, case_data in results.items():
        is_valid = True
        warnings = []
        
        if len(case_data['timeline']) < 2:
            warnings.append("Insufficient version history")
            is_valid = False
        
        for intro in case_data['bug_introductions']:
            if intro['confidence'] < 0.4:
                warnings.append(f"Low confidence for bug introduction: {intro['confidence']:.2f}")
        
        if is_valid:
            validation['valid_cases'] += 1
        else:
            validation['invalid_cases'] += 1
        
        if warnings:
            validation['warnings'].append({
                'case': case_name,
                'warnings': warnings
            })
    
    return validation

# Run bug introduction analysis on folder and return results, report and valadation
def run_bug_classifier(data_folder: str = "data") -> Dict[str, any]:
    results = find_bug_introductions(data_folder)
    
    if not results:
        return {
            'results': {},
            'report': {'total_cases': 0},
            'validation': {'valid_cases': 0, 'invalid_cases': 0}
        }
    
    report = generate_report(results)
    validation = validate_results(results)
    
    return {
        'results': results,
        'report': report,
        'validation': validation
    }

# Forward to detect_potential_bug_fixes_for_pair
def detect_potential_bug_fixes_for_pair(old_file: str, new_file: str, changed_lines: List[Dict]) -> List[Dict]:
    return detect_potential_bug_fixes(changed_lines)

# Find bug introduction for old and new file pair using its history in the same folder
def find_bug_introductions_for_pair(old_file: str, new_file: str, changed_lines: List[Dict]) -> List[Dict]:
    old_filename = os.path.basename(old_file)
    new_filename = os.path.basename(new_file)
    
    old_base = old_filename.split('_v')[0] if '_v' in old_filename else old_filename.split('.')[0]
    new_base = new_filename.split('_v')[0] if '_v' in new_filename else new_filename.split('.')[0]
    
    if old_base != new_base:
        return []
    
    data_folder = os.path.dirname(old_file)
    timeline = build_version_timeline(data_folder, old_base)
    
    if len(timeline) < 2:
        return []
    
    # Locate the current version of the timeline
    current_idx = -1
    for i, (f, v) in enumerate(timeline):
        if os.path.basename(f) == old_filename:
            current_idx = i
            break
    
    if current_idx < 0:
        return []
    
    bug_introductions = []
    potential_fixes = detect_potential_bug_fixes(changed_lines)
    
    for fix in potential_fixes:
        buggy_line = fix['old_text'] if fix['old_text'] else fix['new_text']
        buggy_line_num = fix['old_line_num'] if fix['old_line_num'] else fix['new_line_num']
        
        if not buggy_line or not buggy_line_num:
            continue
        
        intro_file, intro_version, intro_confidence = trace_bug_introduction(
            buggy_line,
            buggy_line_num,
            old_file,
            timeline
        )
        
        bug_introductions.append({
            'buggy_line': buggy_line,
            'buggy_line_num': buggy_line_num,
            'introduced_in': intro_file,
            'introduced_version': intro_version,
            'confidence': intro_confidence,
            'fix_details': {
                'old_line': fix['old_line_num'],
                'new_line': fix['new_line_num'],
                'bug_fix_score': fix['bug_fix_score']
            }
        })
    
    return bug_introductions

# Return all changed lines, potential bug fixes, and where those bugs were introduced.
def run_bug_identifier_for_pair(old_file: str, new_file: str,
                               existing_mappings: Optional[Dict[int, List[int]]] = None,
                               existing_removed: Optional[List[int]] = None,
                               existing_inserted: Optional[List[int]] = None) -> Dict[str, any]:
    changed_lines = get_changed_lines(
        old_file, 
        new_file,
        existing_mappings=existing_mappings,
        existing_removed=existing_removed,
        existing_inserted=existing_inserted
    )
    bug_fixes = detect_potential_bug_fixes_for_pair(old_file, new_file, changed_lines)
    bug_introductions = find_bug_introductions_for_pair(old_file, new_file, changed_lines)
    
    results = {
        'old_file': old_file,
        'new_file': new_file,
        'changed_lines': changed_lines,
        'bug_fixes': bug_fixes,
        'bug_introductions': bug_introductions,
        'num_bug_fixes': len(bug_fixes),
        'num_introductions': len(bug_introductions)
    }
    
    return results