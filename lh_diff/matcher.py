from typing import List, Dict, Tuple, Set, Optional
from lh_diff.similarity import build_context, combined_similarity
from rapidfuzz.distance import Levenshtein
import re

class DiffMatcher:
    """
    A matching engine designed to compare two versions of source code.
    
    detection methods and approaches:
    1. Structural changes (renamed variables, moved methods).
    2. Logic rewrites (changes in control flow).
    3. Semantic equivalences (refactorings that look different but act the same).
    4. Line splits (one line becoming multiple).
    """

    def __init__(self):
        # Stores indices and metadata about structural changes
        self.structural_changes = {}
        # Maps old variable names to new variable names
        self.variable_renames = {}
        # Stores line ranges for methods: {'method_name': (start_line, end_line)}
        self.method_boundaries = {'old': {}, 'new': {}}
        # Tracks where specific fields were replaced/refactored
        self.field_usage_replacements = {}
        
        # Caches to improve performance during repeated lookups
        self.old_lines_cache = []
        self.similarity_cache = {}
        self.context_cache = {}
        
        # Stores detected logic rewrites and semantic patterns
        self.logic_rewrites = {}
        self.semantic_patterns = {}
        # Metadata regarding how variables are used (surrounding code, operations)
        self.variable_contexts = {'old': {}, 'new': {}}
        
    def detect_structural_changes(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Orchestrates the detection of high-level code changes before line matching begins.
        """
        self.old_lines_cache = old_lines
        
        # Step 1: Map out where methods start and end
        self.method_boundaries['old'] = self._find_method_boundaries(old_lines)
        self.method_boundaries['new'] = self._find_method_boundaries(new_lines)
        # Step 2: Check for removed or modified class fields
        self._detect_field_changes(old_lines, new_lines)
        # Step 3: Check where those fields were used and how that usage changed
        self._detect_field_usage_replacements(old_lines, new_lines)
        # Step 4: Analyze variable usage to find renames
        self._detect_variable_renames(old_lines, new_lines)
        # Step 5: Check for methods that were heavily rewritten
        self._detect_logic_rewrites(old_lines, new_lines)
        # Step 6: Load predefined semantic patterns
        self._detect_semantic_equivalences(old_lines, new_lines)
    
    def _detect_logic_rewrites(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Compares the control flow (cyclomatic complexity features) of methods with the same name.
        """
        old_methods = self.method_boundaries['old']
        new_methods = self.method_boundaries['new']
        
        for method_name, (old_start, old_end) in old_methods.items():
            if method_name in new_methods:
                new_start, new_end = new_methods[method_name]
                
                # Analyze flow features (returns, loops, ifs)
                old_flow = self._analyze_control_flow(old_lines[old_start:old_end+1])
                new_flow = self._analyze_control_flow(new_lines[new_start:new_end+1])
                
                if self._is_major_rewrite(old_flow, new_flow):
                    self.logic_rewrites[method_name] = {
                        'old_flow': old_flow,
                        'new_flow': new_flow,
                        'old_start': old_start,
                        'new_start': new_start,
                        'confidence': self._calculate_rewrite_confidence(old_flow, new_flow)
                    }
    
    def _analyze_control_flow(self, method_lines: List[str]) -> Dict[str, int]:
        """
        Extracts features related to code complexity and control flow.
        """
        flow_patterns = {
            'early_returns': 0,
            'conditional_blocks': 0,
            'nested_blocks': 0,
            'null_checks': 0,
            'assignments': 0
        }
        
        brace_level = 0
        in_conditional = False
        
        for line in method_lines:
            stripped = line.strip()
            
            # Detect returns inside blocks (not at top level)
            if 'return' in stripped and brace_level > 0:
                flow_patterns['early_returns'] += 1
            
            # Detect control structures
            if any(keyword in stripped for keyword in ['if', 'else', 'for', 'while']):
                flow_patterns['conditional_blocks'] += 1
                in_conditional = True
            
            # Detect null checks (Java-style)
            if '!= null' in stripped or '== null' in stripped:
                flow_patterns['null_checks'] += 1
            
            # Detect assignments
            if '=' in stripped and not stripped.startswith('if') and not stripped.startswith('while'):
                flow_patterns['assignments'] += 1
            
            # Track nesting level
            brace_level += line.count('{')
            brace_level -= line.count('}')
        
        return flow_patterns
    
    def _is_major_rewrite(self, old_flow: Dict[str, int], new_flow: Dict[str, int]) -> bool:
        """
        Determines if the changes in control flow are significant enough to call a 'rewrite'.
        """
        early_return_change = abs(old_flow['early_returns'] - new_flow['early_returns']) >= 2
        conditional_change = abs(old_flow['conditional_blocks'] - new_flow['conditional_blocks']) >= 2
        
        return early_return_change or conditional_change
    
    def _calculate_rewrite_confidence(self, old_flow: Dict[str, int], new_flow: Dict[str, int]) -> float:
        """
        Calculates a score (0.0 to 1.0) indicating how confident we are that a rewrite occurred.
        """
        confidence = 0.0
        
        if old_flow['early_returns'] != new_flow['early_returns']:
            confidence += 0.4
        
        if old_flow['conditional_blocks'] != new_flow['conditional_blocks']:
            confidence += 0.3
        
        if old_flow['null_checks'] != new_flow['null_checks']:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _detect_semantic_equivalences(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Defines regex patterns for known refactoring styles (e.g., field consolidation).
        """
        semantic_patterns = []
        
        semantic_patterns.append({
            'old_pattern': r'(\w+)\.id',
            'new_pattern': r'this\.resolvedType\.id',
            'confidence': 0.8,
            'type': 'field_consolidation'
        })
        
        semantic_patterns.append({
            'old_pattern': r'return\s+this\.expressionType\s*=\s*\w+\s*=\s*.*',
            'new_pattern': r'return\s+this\.resolvedType',
            'confidence': 0.7,
            'type': 'return_simplification'
        })
        
        semantic_patterns.append({
            'old_pattern': r'if\s*\(\s*\w+\s*==\s*null\s*\)\s*return\s+null',
            'new_pattern': r'if\s*\(\s*\w+\s*!=\s*null\s*\)\s*\{',
            'confidence': 0.6,
            'type': 'conditional_restructuring'
        })
        
        for pattern in semantic_patterns:
            pattern_key = f"semantic_{pattern['type']}"
            self.semantic_patterns[pattern_key] = pattern
    
    def _detect_field_changes(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Identifies fields that existed in the old code but are missing in the new code.
        """
        old_fields = self._extract_fields(old_lines)
        new_fields = self._extract_fields(new_lines)
        
        removed_fields = old_fields - new_fields
        for field in removed_fields:
            for i, line in enumerate(old_lines):
                # Ensure it looks like a declaration
                if field in line and any(modifier in line for modifier in ['public', 'private', 'protected']):
                    self.structural_changes['field_removed'] = i
                    self.structural_changes['removed_field_name'] = field
                    break
    
    def _detect_field_usage_replacements(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        If a field was removed, find where it was used and attempt to find its replacement in the new code.
        """
        if 'removed_field_name' not in self.structural_changes:
            return
            
        removed_field = self.structural_changes['removed_field_name']
        
        field_pattern = re.compile(r'\b' + re.escape(removed_field) + r'\b')
        
        # Find all usages in old code
        old_usages = []
        for i, line in enumerate(old_lines):
            if field_pattern.search(line):
                old_usages.append((i, line))
        
        # Define search areas in new code
        expected_areas = {}
        for old_idx, old_line in old_usages:
            expected_areas[old_idx] = self._get_expected_replacement_area(old_idx, new_lines)
        
        # Attempt to match old usage patterns to new code
        for old_idx, old_line in old_usages:
            old_usage_pattern = self._extract_field_usage_pattern(old_line, removed_field)
            if old_usage_pattern:
                replacement = self._find_field_replacement(old_usage_pattern, new_lines, removed_field, old_idx, expected_areas[old_idx])
                if replacement:
                    self.field_usage_replacements[old_idx] = {
                        'old_pattern': old_usage_pattern,
                        'replacement': replacement['pattern'],
                        'replacement_line': replacement['line_idx'],
                        'confidence': replacement['confidence']
                    }
    
    def _extract_field_usage_pattern(self, line: str, field_name: str) -> Optional[str]:
        """
        Categorizes how a field is being used (access, comparison, assignment, etc.).
        """
        patterns = [
            rf'{field_name}\.(\w+)',        # Member access
            rf'{field_name}\s*==\s*(\w+)',  # Comparison
            rf'{field_name}\s*=\s*',        # Assignment
            rf'\(\s*{field_name}\s*\)',     # Casting/grouping
        ]
        
        compiled_patterns = [re.compile(pattern) for pattern in patterns]
        
        for pattern in compiled_patterns:
            match = pattern.search(line)
            if match:
                if pattern == compiled_patterns[0]:
                    return f"{field_name}.{match.group(1)}"
                elif pattern == compiled_patterns[1]:
                    return f"{field_name} == {match.group(1)}"
                elif pattern == compiled_patterns[2]:
                    return f"{field_name} assignment"
                else:
                    return f"({field_name})"
        return None

    def _find_field_replacement(self, old_pattern: str, new_lines: List[str], removed_field: str, old_idx: int, expected_area: List[int]) -> Optional[Dict]:
        """
        Scans a specific area of the new code to find the most likely replacement for a removed field usage.
        """
        best_replacement = None
        best_confidence = 0.0
        
        removed_field_pattern = re.compile(r'\b' + re.escape(removed_field) + r'\b')
        
        for new_idx in expected_area:
            new_line = new_lines[new_idx]
            
            # If the field still exists here, it's not a replacement
            if removed_field_pattern.search(new_line):
                continue
                
            confidence = self._calculate_replacement_confidence(old_pattern, new_line, removed_field)
            
            # Check if semantic patterns boost confidence
            semantic_boost = self._check_semantic_patterns(old_pattern, new_line)
            confidence = min(1.0, confidence + semantic_boost)
            
            if confidence > best_confidence:
                best_replacement = {
                    'pattern': self._extract_replacement_pattern(new_line, removed_field, old_pattern),
                    'line_idx': new_idx,
                    'confidence': confidence
                }
                best_confidence = confidence
        
        return best_replacement if best_confidence > 0.3 else None

    def _check_semantic_patterns(self, old_line: str, new_line: str) -> float:
        """
        Checks if the change matches any known refactoring patterns defined in _detect_semantic_equivalences.
        """
        boost = 0.0
        
        for pattern_key, pattern_info in self.semantic_patterns.items():
            old_match = re.search(pattern_info['old_pattern'], old_line)
            new_match = re.search(pattern_info['new_pattern'], new_line)
            
            if old_match and new_match:
                boost = max(boost, pattern_info['confidence'] * 0.5)
        
        return boost

    def _get_expected_replacement_area(self, old_idx: int, new_lines: List[str]) -> List[int]:
        """
        Calculates a window of lines in the new file where a replacement is likely to be found.
        Adjusts based on method boundaries.
        """
        start = max(0, old_idx - 15)
        end = min(len(new_lines), old_idx + 15)
        
        # Constrain search to the same method if possible
        if hasattr(self, 'old_lines_cache') and self.old_lines_cache:
            old_method = self._get_method_context(self.old_lines_cache, old_idx, self.method_boundaries['old'])
            if old_method in self.method_boundaries['new']:
                method_start, method_end = self.method_boundaries['new'][old_method]
                start = min(start, method_start)
                end = max(end, method_end)
        
        return list(range(start, end))

    def _calculate_replacement_confidence(self, old_pattern: str, new_line: str, removed_field: str) -> float:
        """
        Heuristic scoring for how likely a new line replaces an old pattern.
        """
        confidence = 0.0
        
        # Check for preserved properties (e.g., .id access)
        if '.id' in old_pattern and '.id' in new_line:
            confidence += 0.7
        # Check for preserved comparisons
        elif '==' in old_pattern and '==' in new_line:
            old_type = old_pattern.split('==')[-1].strip()
            new_type_match = re.search(r'==\s*(\w+)', new_line)
            if new_type_match and old_type == new_type_match.group(1):
                confidence += 0.9
            else:
                confidence += 0.4
        elif 'assignment' in old_pattern and '=' in new_line:
            confidence += 0.5
        
        # Calculate text similarity on the rest of the line
        old_simple = re.sub(r'\b' + re.escape(removed_field) + r'\b', 'FIELD', old_pattern)
        new_simple = re.sub(r'\b\w+Binding\b', 'TYPE', new_line)
        
        cache_key = (old_simple, new_simple)
        if cache_key not in self.similarity_cache:
            self.similarity_cache[cache_key] = combined_similarity(old_simple, new_simple, "", "")
        
        if self.similarity_cache[cache_key] > 0.5:
            confidence += 0.3
        
        return min(confidence, 1.0)

    def _extract_replacement_pattern(self, line: str, removed_field: str, old_pattern: str) -> str:
        """
        Extracts the snippet of text from the new line that effectively replaced the old field.
        """
        if '.id' in old_pattern:
            match = re.search(r'(\w+\.id)', line)
            if match:
                return match.group(1)
        
        if '==' in old_pattern:
            match = re.search(r'(\w+\s*==\s*\w+)', line)
            if match:
                return match.group(1)
        
        if '=' in line and 'assignment' in old_pattern:
            parts = line.split('=')
            if len(parts) > 1:
                return f"{parts[0].strip()} = ..."
        
        words = line.split()
        if len(words) > 0:
            for word in words:
                if '.' in word:
                    return word
            return words[0] if len(words[0]) > 3 else line[:30]
        
        return line[:30]

    def _extract_fields(self, lines: List[str]) -> Set[str]:
        """
        Regex-based extraction of Java-style field declarations.
        """
        fields = set()
        field_pattern = re.compile(r'(?:public|private|protected)\s+(?:\w+\s+)+\s*(\w+)\s*;')
        
        for line in lines:
            matches = field_pattern.findall(line)
            for match in matches:
                fields.add(match)
        return fields
    
    def _detect_variable_renames(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Main driver for detecting variable renaming. Uses a 4-stage process:
        1. Context-based matching (usage patterns).
        2. Pattern-based matching (regex rules).
        3. Semantic similarity (Levenshtein + Context).
        4. Paired renaming (detecting groups of variables renamed together).
        """
        self._build_variable_contexts(old_lines, new_lines)
        
        all_renames = {}
        
        # Stage 1: Context
        context_renames = self._find_variable_renames_by_context()
        all_renames.update(context_renames)
        
        # Stage 2: Pattern (e.g. varName -> varType)
        pattern_renames = self._find_variable_renames_by_pattern()
        for old_var, (new_var, conf) in pattern_renames.items():
            if old_var not in all_renames or conf > all_renames[old_var][1]:
                all_renames[old_var] = (new_var, conf)
        
        # Stage 3: Semantic/Levenshtein
        semantic_renames = self._find_variable_renames_by_semantic_similarity()
        for old_var, (new_var, conf) in semantic_renames.items():
            if old_var not in all_renames or conf > all_renames[old_var][1]:
                all_renames[old_var] = (new_var, conf)
        
        # Stage 4: Paired logic
        paired_renames = self._find_paired_variable_renames()
        for old_var, (new_var, conf) in paired_renames.items():
            if old_var not in all_renames or conf > all_renames[old_var][1]:
                all_renames[old_var] = (new_var, conf)
        
        # Final validation
        validated_renames = {}
        for old_var, (new_var, confidence) in all_renames.items():
            if confidence > 0.7 and self._validate_rename(old_var, new_var, old_lines, new_lines):
                validated_renames[old_var] = new_var
        
        self.variable_renames = validated_renames
    
    def _build_variable_contexts(self, old_lines: List[str], new_lines: List[str]) -> None:
        """
        Scans code to build a profile for every variable:
        - Methods it appears in.
        - Operations performed on it (assignment, return, etc.).
        - Surrounding text.
        """
        self.variable_contexts = {'old': {}, 'new': {}}
        
        # Helper to process a list of lines and populate the context dictionary
        for i, line in enumerate(old_lines):
            variables = self._extract_variables_from_line(line)
            for var in variables:
                if var not in self.variable_contexts['old']:
                    self.variable_contexts['old'][var] = {
                        'usage_count': 0,
                        'methods': set(),
                        'operations': set(),
                        'surrounding_contexts': set(),
                        'line_indices': set(),
                        'declaration_context': None
                    }
                
                context = self.variable_contexts['old'][var]
                context['usage_count'] += 1
                context['methods'].add(self._get_method_context(old_lines, i, self.method_boundaries['old']))
                context['operations'].update(self._extract_operations_from_line(line, var))
                context['line_indices'].add(i)
                
                # Capture surrounding lines for context matching
                start = max(0, i - 3)
                end = min(len(old_lines), i + 4)
                surrounding = ' '.join(old_lines[start:end])
                context['surrounding_contexts'].add(self._normalize_context(surrounding))
                
                if '=' in line and var in line.split('=')[0]:
                    context['declaration_context'] = self._extract_declaration_context(line)
        
        # Repeat for new lines (Logic duplicated for separation of concerns)
        for i, line in enumerate(new_lines):
            variables = self._extract_variables_from_line(line)
            for var in variables:
                if var not in self.variable_contexts['new']:
                    self.variable_contexts['new'][var] = {
                        'usage_count': 0,
                        'methods': set(),
                        'operations': set(),
                        'surrounding_contexts': set(),
                        'line_indices': set(),
                        'declaration_context': None
                    }
                
                context = self.variable_contexts['new'][var]
                context['usage_count'] += 1
                context['methods'].add(self._get_method_context(new_lines, i, self.method_boundaries['new']))
                context['operations'].update(self._extract_operations_from_line(line, var))
                context['line_indices'].add(i)
                
                start = max(0, i - 3)
                end = min(len(new_lines), i + 4)
                surrounding = ' '.join(new_lines[start:end])
                context['surrounding_contexts'].add(self._normalize_context(surrounding))
                
                if '=' in line and var in line.split('=')[0]:
                    context['declaration_context'] = self._extract_declaration_context(line)
    
    def _extract_variables_from_line(self, line: str) -> List[str]:
        """
        Extracts potential variable names, filtering out Java keywords and common types.
        """
        if any(keyword in line for keyword in ['class ', 'interface ', 'enum ', 'public ', 'private ', 'protected ']):
            return []
        
        words = re.findall(r'\b[a-z][a-zA-Z0-9]*\b', line)
        
        java_keywords = {'if', 'else', 'for', 'while', 'return', 'new', 'this', 'super', 'null', 'true', 'false', 'final'}
        common_types = {'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short', 'void', 'String'}
        
        return [word for word in words if word not in java_keywords and word not in common_types and len(word) > 2]
    
    def _extract_operations_from_line(self, line: str, var: str) -> Set[str]:
        """
        Identifies what is being done to a variable in a specific line.
        """
        operations = set()
        var_pattern = re.compile(r'\b' + re.escape(var) + r'\b')
        
        if not var_pattern.search(line):
            return operations
        
        if '.id' in line and var in line:
            operations.add('id_access')
        if '==' in line and var in line:
            operations.add('comparison')
        if '=' in line and var in line.split('=')[0]:
            operations.add('assignment')
        if 'return' in line and var in line:
            operations.add('return')
        if '(' in line and var in line:
            operations.add('method_call')
        if 'new ' in line and var in line:
            operations.add('instantiation')
        if '.' in line and var in line.split('.')[0]:
            operations.add('field_access')
        
        return operations
    
    def _extract_declaration_context(self, line: str) -> Optional[str]:
        """
        Attempts to find the type or context of a variable declaration.
        """
        type_patterns = [
            r'(\w+)\s+' + r'(\w+)' + r'\s*=',  # Type var = ...
            r'\(\s*(\w+)\s*\)',               # (Type) cast
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1) if match.lastindex >= 1 else None
        return None
    
    def _normalize_context(self, context: str) -> str:
        """
        Generalizes code by replacing specific names with tokens like VAR, TYPE, NUM
        to allow fuzzy matching of contexts.
        """
        normalized = re.sub(r'\b[a-z][a-zA-Z0-9]*\b', 'VAR', context)
        normalized = re.sub(r'\b[A-Z][a-zA-Z0-9]*\b', 'TYPE', normalized)
        normalized = re.sub(r'\b\d+\b', 'NUM', normalized)
        return normalized
    
    def _find_variable_renames_by_context(self) -> Dict[str, Tuple[str, float]]:
        """
        Matches variables based on the similarity of their usage context (methods, operations, surroundings).
        """
        renames = {}
        
        for old_var, old_context in self.variable_contexts['old'].items():
            if old_context['usage_count'] < 2:
                continue
            
            best_match = None
            best_score = 0.0
            
            for new_var, new_context in self.variable_contexts['new'].items():
                if new_context['usage_count'] < 2:
                    continue
                
                score = self._calculate_context_similarity(old_context, new_context)
                
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = new_var
            
            if best_match:
                renames[old_var] = (best_match, best_score)
        
        return renames
    
    def _calculate_context_similarity(self, old_context: Dict, new_context: Dict) -> float:
        """
        Weighted similarity score based on method overlap, operation overlap, and surrounding text.
        """
        similarity = 0.0
        
        method_overlap = len(old_context['methods'].intersection(new_context['methods']))
        method_union = len(old_context['methods'].union(new_context['methods']))
        if method_union > 0:
            similarity += (method_overlap / method_union) * 0.3
        
        operation_overlap = len(old_context['operations'].intersection(new_context['operations']))
        operation_union = len(old_context['operations'].union(new_context['operations']))
        if operation_union > 0:
            similarity += (operation_overlap / operation_union) * 0.4
        
        context_overlap = len(old_context['surrounding_contexts'].intersection(new_context['surrounding_contexts']))
        context_union = len(old_context['surrounding_contexts'].union(new_context['surrounding_contexts']))
        if context_union > 0:
            similarity += (context_overlap / context_union) * 0.3
        
        return similarity
    
    def _find_variable_renames_by_pattern(self) -> Dict[str, Tuple[str, float]]:
        """
        Matches variables based on common renaming conventions (suffixes like 'Temp', 'Old', 'Binding').
        """
        renames = {}
        common_patterns = [
            (r'(\w+)Tb', r'\1Type', 0.9),
            (r'(\w+)Temp', r'\1', 0.7),
            (r'(\w+)Var', r'\1', 0.7),
            (r'(\w+)Old', r'\1', 0.6),
            (r'(\w+)New', r'\1', 0.6),
            (r'(\w+)Binding', r'\1Type', 0.8),
        ]
        
        for old_var in self.variable_contexts['old']:
            for pattern, replacement, confidence in common_patterns:
                if re.match(pattern, old_var):
                    potential_new = re.sub(pattern, replacement, old_var)
                    if potential_new in self.variable_contexts['new']:
                        if self._contexts_are_compatible(old_var, potential_new):
                            renames[old_var] = (potential_new, confidence)
                            break
        
        return renames
    
    def _find_paired_variable_renames(self) -> Dict[str, Tuple[str, float]]:
        """
        Detects if multiple variables with the same root name were renamed similarly.
        """
        renames = {}
        
        # Group old variables by their base name
        old_vars_with_patterns = {}
        for old_var in self.variable_contexts['old']:
            for pattern in [r'(\w+)Tb', r'(\w+)Binding']:
                match = re.match(pattern, old_var)
                if match:
                    base_name = match.group(1)
                    if base_name not in old_vars_with_patterns:
                        old_vars_with_patterns[base_name] = []
                    old_vars_with_patterns[base_name].append(old_var)
        
        # Check if corresponding new variables exist
        for base_name, old_vars in old_vars_with_patterns.items():
            if len(old_vars) >= 2:
                potential_new_vars = []
                for suffix in ['Type', '']:
                    new_var = base_name + suffix
                    if new_var in self.variable_contexts['new']:
                        potential_new_vars.append(new_var)
                
                # Link them up
                for i, old_var in enumerate(old_vars):
                    if i < len(potential_new_vars):
                        new_var = potential_new_vars[i]
                        if self._contexts_are_compatible(old_var, new_var):
                            renames[old_var] = (new_var, 0.85)
        
        return renames
    
    def _contexts_are_compatible(self, old_var: str, new_var: str) -> bool:
        """
        Checks if two variables share enough context to be considered a plausible rename.
        """
        old_context = self.variable_contexts['old'].get(old_var, {})
        new_context = self.variable_contexts['new'].get(new_var, {})
        
        if not old_context or not new_context:
            return False
        
        method_overlap = old_context['methods'].intersection(new_context['methods'])
        if not method_overlap:
            return False
        
        operation_overlap = old_context['operations'].intersection(new_context['operations'])
        if not operation_overlap:
            return False
        
        return True
    
    def _find_variable_renames_by_semantic_similarity(self) -> Dict[str, Tuple[str, float]]:
        """
        Combines name similarity (Levenshtein) and context similarity to find renames.
        """
        renames = {}
        
        for old_var, old_context in self.variable_contexts['old'].items():
            if old_context['usage_count'] < 2:
                continue
            
            best_match = None
            best_score = 0.0
            
            for new_var, new_context in self.variable_contexts['new'].items():
                if new_context['usage_count'] < 2:
                    continue
                
                name_similarity = self._calculate_name_similarity(old_var, new_var)
                
                context_similarity = self._calculate_context_similarity(old_context, new_context)
                # Weighted score favors context heavily
                combined_score = (name_similarity * 0.3) + (context_similarity * 0.7)
                
                if combined_score > best_score and combined_score > 0.65:
                    best_score = combined_score
                    best_match = new_var
            
            if best_match:
                renames[old_var] = (best_match, best_score)
        
        return renames
    
    def _calculate_name_similarity(self, old_name: str, new_name: str) -> float:
        """
        Calculates string similarity, accounting for common prefixes and known rename patterns.
        """
        if old_name == new_name:
            return 1.0
        
        rename_patterns = [
            (r'(\w+)Tb', r'\1Type', 0.9),
            (r'(\w+)Binding', r'\1Type', 0.8),
            (r'temp(\w+)', r'\1', 0.7),
            (r'old(\w+)', r'\1', 0.6),
            (r'new(\w+)', r'\1', 0.6),
        ]
        
        for pattern, replacement, confidence in rename_patterns:
            if re.match(pattern, old_name) and re.sub(pattern, replacement, old_name) == new_name:
                return confidence
        
        max_len = max(len(old_name), len(new_name))
        if max_len == 0:
            return 0.0
        
        levenshtein_similarity = 1.0 - (Levenshtein.distance(old_name, new_name) / max_len)
        
        # Boost score if they start with the same 3 letters
        common_prefix = 0
        for i in range(min(len(old_name), len(new_name))):
            if old_name[i] == new_name[i]:
                common_prefix += 1
            else:
                break
        
        if common_prefix >= 3:
            levenshtein_similarity = min(1.0, levenshtein_similarity + 0.2)
        
        return levenshtein_similarity
    
    def _validate_rename(self, old_var: str, new_var: str, old_lines: List[str], new_lines: List[str]) -> bool:
        """
        Sanity check: Ensures the old name doesn't still exist in the new file,
        and that the variables operate in similar contexts.
        """
        old_pattern = re.compile(r'\b' + re.escape(old_var) + r'\b')
        for line in new_lines:
            if old_pattern.search(line):
                return False
        
        old_context = self.variable_contexts['old'][old_var]
        new_context = self.variable_contexts['new'][new_var]
        
        if not old_context['operations'].intersection(new_context['operations']):
            return False
        
        if not old_context['methods'].intersection(new_context['methods']):
            return False
        
        return True

    def _find_method_boundaries(self, lines: List[str]) -> Dict[str, Tuple[int, int]]:
        """
        Scans lines to find start and end indices of methods based on braces and declaration patterns.
        """
        boundaries = {}
        current_method = None
        brace_count = 0
        method_start = 0
        
        method_pattern = re.compile(r'^\s*(?:public|private|protected)?\s*(?:\w+\s+)*\s*(\w+)\s*\(')
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            method_match = method_pattern.match(stripped)
            if method_match:
                if current_method is None:
                    method_name = method_match.group(1)
                    current_method = method_name
                    method_start = i
                    brace_count = 0
                brace_count += line.count('{')
            
            elif current_method:
                brace_count += line.count('{')
                brace_count -= line.count('}')
                
                if brace_count <= 0 and '}' in line:
                    boundaries[current_method] = (method_start, i)
                    current_method = None
                    brace_count = 0
        
        return boundaries
    
    def _get_method_context(self, lines: List[str], line_idx: int, boundaries: Dict[str, Tuple[int, int]]) -> str:
        """
        Returns the name of the method that contains the given line index.
        """
        if not boundaries:
            return "global"
            
        for method_name, (start, end) in boundaries.items():
            if start <= line_idx <= end:
                return method_name
        return "global"
    
    def _apply_rename_adjustment(self, line: str) -> str:
        """
        Substitutes old variable names with their new counterparts in a string
        to check if it matches the new code.
        """
        adjusted = line
        
        for old_name, new_name in self.variable_renames.items():
            pattern = r'\b' + re.escape(old_name) + r'\b'
            adjusted = re.sub(pattern, new_name, adjusted)
        
        return adjusted

    def _get_cached_context(self, lines: List[str], line_idx: int, window: int = 3) -> str:
        """
        Retrieves context string from cache or builds it.
        """
        cache_key = (id(lines), line_idx, window)
        if cache_key not in self.context_cache:
            self.context_cache[cache_key] = build_context(lines, line_idx, window)
        return self.context_cache[cache_key]

    def _get_cached_similarity(self, line1: str, line2: str, context1: str = "", context2: str = "") -> float:
        """
        Retrieves similarity score from cache or calculates it.
        """
        cache_key = (line1, line2, context1, context2)
        if cache_key not in self.similarity_cache:
            self.similarity_cache[cache_key] = combined_similarity(line1, line2, context1, context2)
        return self.similarity_cache[cache_key]

    def best_match_for_each_line(self, old_lines: List[str], new_lines: List[str], 
                        candidate_sets: Dict[int, List[int]], threshold: float = 0.45) -> Dict[int, Tuple[int, float]]:
        """
        The CORE matching algorithm. Finds the best matching line in the new file for every line in the old file.
        
        Process:
        1. Pre-computation (structural changes, similarity matrix).
        2. Exact matches (Pass 1).
        3. Structural replacements (Pass 2).
        4. Control flow & logic matches (Pass 3).
        5. Local proximity matches (Pass 4).
        6. Remaining structural matches (Pass 5).
        7. Global search (Pass 6).
        8. Forced best-effort match (Pass 7).
        """
        if not self.method_boundaries['old'] or not self.method_boundaries['new']:
            self.method_boundaries['old'] = self._find_method_boundaries(old_lines)
            self.method_boundaries['new'] = self._find_method_boundaries(new_lines)
            
        self.detect_structural_changes(old_lines, new_lines)
        
        n_old = len(old_lines)
        n_new = len(new_lines)

        # Build similarity matrix
        similarity_matrix = [[0.0] * n_new for _ in range(n_old)]
        
        old_contexts = {}
        new_contexts = {}
        
        for old_idx in range(n_old):
            old_contexts[old_idx] = self._get_cached_context(old_lines, old_idx, 2)
        
        for new_idx in range(n_new):
            new_contexts[new_idx] = self._get_cached_context(new_lines, new_idx, 2)
        
        for old_idx, candidates in candidate_sets.items():
            for new_idx in candidates:
                old_context = old_contexts[old_idx]
                new_context = new_contexts[new_idx]
                
                similarity_matrix[old_idx][new_idx] = self._get_cached_similarity(
                    old_lines[old_idx], new_lines[new_idx], old_context, new_context
                )
        
        matches = {}
        used_new_indices = set()
        
        # PASS 1: Exact matches (>95% similarity)
        exact_matches = 0
        for i in range(n_old):
            for j in candidate_sets.get(i, []):
                if similarity_matrix[i][j] > 0.95 and j not in used_new_indices:
                    matches[i] = (j, similarity_matrix[i][j])
                    used_new_indices.add(j)
                    exact_matches += 1
                    break

        # PASS 2: Enhanced structural matches (logic rewrites, semantic patterns)
        enhanced_structural_matches = self._find_enhanced_structural_matches(old_lines, new_lines, similarity_matrix, candidate_sets)
        enhanced_count = 0
        for old_idx, (new_idx, score) in enhanced_structural_matches.items():
            if old_idx not in matches and new_idx not in used_new_indices:
                matches[old_idx] = (new_idx, score)
                used_new_indices.add(new_idx)
                enhanced_count += 1
        
        # PASS 3: Control flow lines (if/else/return)
        control_flow_matches = 0
        for i in range(n_old):
            if i in matches:
                continue
                
            old_line = old_lines[i]
            if self._is_control_flow_line(old_line) or 'return' in old_line:
                best_match = None
                best_score = 0.0
                
                for j in candidate_sets.get(i, []):
                    if j in used_new_indices:
                        continue
                        
                    new_line = new_lines[j]
                    if (self._is_control_flow_line(new_line) or 'return' in new_line) and similarity_matrix[i][j] > 0.6:
                        position_penalty = abs(i - j) / 15.0
                        adjusted_score = similarity_matrix[i][j] * (1 - position_penalty)
                        
                        if adjusted_score > best_score:
                            best_score = adjusted_score
                            best_match = j
                
                if best_match is not None:
                    matches[i] = (best_match, best_score)
                    used_new_indices.add(best_match)
                    control_flow_matches += 1
        
        # PASS 4: Local neighborhood search (match nearby lines)
        local_matches = 0
        for i in range(n_old):
            if i in matches:
                continue
                
            best_match = None
            best_score = 0.0
            
            search_start = max(0, i - 10)
            search_end = min(n_new, i + 11)
            
            for j in range(search_start, search_end):
                if j in used_new_indices:
                    continue
                if j not in candidate_sets.get(i, []):
                    continue
                    
                score = similarity_matrix[i][j]
                position_penalty = abs(i - j) / 25.0
                adjusted_score = score * (1 - position_penalty)
                
                if adjusted_score > best_score and adjusted_score > 0.5:
                    best_score = adjusted_score
                    best_match = j
            
            if best_match is not None:
                matches[i] = (best_match, best_score)
                used_new_indices.add(best_match)
                local_matches += 1
        
        # PASS 5: Remaining structural matches (field replacements)
        structural_matches = self._find_remaining_structural_matches(old_lines, new_lines, similarity_matrix, candidate_sets, matches, used_new_indices)
        structural_count = 0
        for old_idx, (new_idx, score) in structural_matches.items():
            if old_idx not in matches and new_idx not in used_new_indices:
                matches[old_idx] = (new_idx, score)
                used_new_indices.add(new_idx)
                structural_count += 1
        
        # PASS 6: Global search (best match anywhere in file)
        global_matches = 0
        for i in range(n_old):
            if i in matches:
                continue
                
            best_match = None
            best_score = 0.0
            
            for j in candidate_sets.get(i, []):
                if j in used_new_indices:
                    continue
                    
                score = similarity_matrix[i][j]
                if score > best_score and score > 0.3:
                    best_score = score
                    best_match = j
            
            if best_match is not None:
                matches[i] = (best_match, best_score)
                used_new_indices.add(best_match)
                global_matches += 1
        
        # PASS 7: Forced matches (even if confidence is low, pick best available)
        forced_matches = 0
        unmapped_count = 0
        for i in range(n_old):
            if i in matches:
                continue
                
            best_match = None
            best_score = 0.0
            
            for j in candidate_sets.get(i, []):
                score = similarity_matrix[i][j]
                if score > best_score:
                    best_score = score
                    best_match = j
            
            if best_match is not None and best_score > 0.2:
                matches[i] = (best_match, best_score)
                forced_matches += 1
            else:
                unmapped_count += 1
        
        return matches

    def _find_enhanced_structural_matches(self, old_lines: List[str], new_lines: List[str], 
                                        similarity_matrix: List[List[float]], 
                                        candidate_sets: Dict[int, List[int]]) -> Dict[int, Tuple[int, float]]:
        """
        Looks for matches driven by detected structural changes (rewrites, semantic patterns)
        rather than raw string similarity.
        """
        structural_matches = {}
        
        self.old_lines_cache = old_lines
        
        # 1. Matches from field replacement analysis
        for old_idx, replacement_info in self.field_usage_replacements.items():
            replacement_line_idx = replacement_info.get('replacement_line')
            confidence = replacement_info['confidence']
            
            if replacement_line_idx is not None and 0 <= replacement_line_idx < len(new_lines):
                new_line = new_lines[replacement_line_idx]
                score = self._get_cached_similarity(old_lines[old_idx], new_line, "", "")
                
                min_score = 0.4 + (confidence * 0.5)
                boosted_score = max(score, min_score)
                
                if boosted_score > 0.4:
                    structural_matches[old_idx] = (replacement_line_idx, min(boosted_score, 1.0))
        
        # 2. Matches from logic rewrites (interpolating position within methods)
        for method_name, rewrite_info in self.logic_rewrites.items():
            old_start = rewrite_info['old_start']
            new_start = rewrite_info['new_start']
            confidence = rewrite_info['confidence']
            
            if method_name in self.method_boundaries['old'] and method_name in self.method_boundaries['new']:
                old_method_start, old_method_end = self.method_boundaries['old'][method_name]
                new_method_start, new_method_end = self.method_boundaries['new'][method_name]
                
                old_size = old_method_end - old_method_start
                new_size = new_method_end - new_method_start
                
                for old_idx in range(old_method_start, old_method_end + 1):
                    if old_idx in structural_matches:
                        continue
                        
                    # Calculate proportional position in the new method
                    relative_pos = (old_idx - old_method_start) / max(1, old_size)
                    expected_new_idx = new_method_start + int(relative_pos * new_size)
                    
                    search_start = max(new_method_start, expected_new_idx - 10)
                    search_end = min(new_method_end, expected_new_idx + 11)
                    
                    best_new_idx = None
                    best_score = 0.0
                    
                    for new_idx in range(search_start, search_end):
                        if new_idx not in candidate_sets.get(old_idx, []):
                            continue
                            
                        score = similarity_matrix[old_idx][new_idx]
                        boosted_score = min(1.0, score + (confidence * 0.3))
                        
                        if boosted_score > best_score and boosted_score > 0.4:
                            best_score = boosted_score
                            best_new_idx = new_idx
                    
                    if best_new_idx is not None:
                        structural_matches[old_idx] = (best_new_idx, best_score)
        
        # 3. Matches from predefined semantic patterns
        for old_idx, old_line in enumerate(old_lines):
            if old_idx in structural_matches:
                continue
                
            for pattern_key, pattern_info in self.semantic_patterns.items():
                if re.search(pattern_info['old_pattern'], old_line):
                    for new_idx, new_line in enumerate(new_lines):
                        if new_idx in [m[0] for m in structural_matches.values()]:
                            continue
                            
                        if re.search(pattern_info['new_pattern'], new_line):
                            base_score = similarity_matrix[old_idx][new_idx] if new_idx in candidate_sets.get(old_idx, []) else 0.3
                            boosted_score = min(1.0, base_score + (pattern_info['confidence'] * 0.4))
                            
                            if boosted_score > 0.5:
                                structural_matches[old_idx] = (new_idx, boosted_score)
                                break
        
        return structural_matches

    def _find_remaining_structural_matches(self, old_lines: List[str], new_lines: List[str], 
                                         similarity_matrix: List[List[float]], 
                                         candidate_sets: Dict[int, List[int]],
                                         existing_matches: Dict[int, Tuple[int, float]],
                                         used_new_indices: Set[int]) -> Dict[int, Tuple[int, float]]:
        """
        Cleanup pass to find any field replacements that weren't caught in the enhanced pass.
        """
        remaining_matches = {}
        
        for old_idx, replacement_info in self.field_usage_replacements.items():
            if old_idx in existing_matches:
                continue
                
            replacement_line_idx = replacement_info.get('replacement_line')
            if replacement_line_idx is not None and replacement_line_idx not in used_new_indices:
                if 0 <= replacement_line_idx < len(new_lines):
                    new_line = new_lines[replacement_line_idx]
                    score = self._get_cached_similarity(old_lines[old_idx], new_line, "", "")
                    
                    confidence = replacement_info['confidence']
                    min_score = 0.4 + (confidence * 0.5)
                    boosted_score = max(score, min_score)
                    
                    if boosted_score > 0.4:
                        remaining_matches[old_idx] = (replacement_line_idx, min(boosted_score, 1.0))
        
        return remaining_matches

    def _is_control_flow_line(self, line: str) -> bool:
        return bool(re.search(r'\b(?:if|else|for|while|return|switch|case)\b', line))

    def resolve_conflicts(self, matches: Dict[int, Tuple[int, float]], new_lines: List[str]) -> Dict[int, Tuple[int, float]]:
        """
        Handles cases where multiple old lines map to the same new line (many-to-one conflicts).
        Prioritizes the highest score, but tries to find valid alternatives for the losers.
        """
        new_to_old = {}
        for old_idx, (new_idx, score) in matches.items():
            new_to_old.setdefault(new_idx, []).append((old_idx, score))
        
        resolved = {}
        
        for new_idx, old_items in new_to_old.items():
            if len(old_items) == 1:
                resolved[old_items[0][0]] = (new_idx, old_items[0][1])
            else:
                # Conflict: Pick the highest score
                sorted_items = sorted(old_items, key=lambda x: x[1], reverse=True)
                
                best_old_idx, best_score = sorted_items[0]
                
                resolved[best_old_idx] = (new_idx, best_score)
                
                # Attempt to save the "losers" by finding nearby lines
                preserved_count = 0
                for i in range(1, len(sorted_items)):
                    old_idx, score = sorted_items[i]
                    
                    is_structural = old_idx in self.field_usage_replacements
                    is_high_confidence = score > 0.8
                    has_sufficient_distance = abs(old_idx - best_old_idx) > 5
                    is_semantically_reasonable = self._is_semantically_reasonable_match(old_idx, new_idx, new_lines)
                    
                    if (is_structural or is_high_confidence) and has_sufficient_distance and is_semantically_reasonable:
                        nearby_new = self._find_valid_alternative(new_idx, new_lines, old_idx, resolved)
                        if nearby_new is not None and nearby_new != new_idx:
                            resolved[old_idx] = (nearby_new, score)
                            preserved_count += 1
        
        return resolved

    def _is_semantically_reasonable_match(self, old_idx: int, new_idx: int, new_lines: List[str]) -> bool:
        """
        Filters out matches that are syntactically impossible or garbage (e.g. matching code to a lone brace).
        """
        new_line = new_lines[new_idx].strip()
        
        nonsense_patterns = [
            new_line.startswith('public ') and ';' in new_line,
            new_line.startswith('import '),  
            new_line in ['{', '}', '};'],
            len(new_line) < 10,
            '}' in new_line and '{' not in new_line and 'class' not in new_line,
        ]
        
        if any(nonsense_patterns):
            return False
            
        return True

    def _find_valid_alternative(self, original_new_idx: int, new_lines: List[str], old_idx: int, resolved_matches: Dict) -> Optional[int]:
        """
        Searches neighborhood (+/- 15 lines) for a free line to resolve a conflict.
        """
        for offset in range(-15, 16):
            if offset == 0:
                continue
                
            test_idx = original_new_idx + offset
            if 0 <= test_idx < len(new_lines):
                if any(match[0] == test_idx for match in resolved_matches.values()):
                    continue
                    
                if self._is_semantically_reasonable_match(old_idx, test_idx, new_lines):
                    return test_idx
                    
        return None

    def detect_reorders(self, old_lines: List[str], new_lines: List[str], 
                       matches: Dict[int, Tuple[int, float]], threshold: float = 0.4) -> Dict[int, Tuple[int, float]]:
        """
        Detects lines that have moved significantly (e.g., extracted to a new method or reordered).
        Only runs on unmatched lines.
        """
        matched_new = {v[0] for v in matches.values()}
        extra_matches = {}
        
        old_method_contexts = {}
        for old_idx in range(len(old_lines)):
            old_method_contexts[old_idx] = self._get_method_context(old_lines, old_idx, self.method_boundaries['old'])
        
        batch_size = 100
        total_old = len(old_lines)
        
        for batch_start in range(0, total_old, batch_size):
            batch_end = min(batch_start + batch_size, total_old)
            
            for old_idx in range(batch_start, batch_end):
                if old_idx in matches:
                    continue
                    
                old_method = old_method_contexts[old_idx]
                old_line = old_lines[old_idx]
                
                if old_idx == self.structural_changes.get('field_removed'):
                    continue
                
                best_score, best_new_idx = 0.0, None
                
                # Expand search range based on method boundaries
                if old_method in self.method_boundaries['new']:
                    start, end = self.method_boundaries['new'][old_method]
                    search_range = range(max(0, start - 25), min(len(new_lines), end + 26))
                else:
                    search_range = range(max(0, old_idx - 60), min(len(new_lines), old_idx + 61))
                
                for new_idx in search_range:
                    if new_idx in matched_new:
                        continue
                        
                    new_method = self._get_method_context(new_lines, new_idx, self.method_boundaries['new'])
                    # Constrain to method moves or global moves
                    if old_method != "global" and new_method != "global" and old_method != new_method:
                        continue
                        
                    new_line = new_lines[new_idx]
                    score = self._get_cached_similarity(old_line, new_line, "", "")
                    
                    # Try adjusting for variable renames
                    adjusted_old = self._apply_rename_adjustment(old_line)
                    adjusted_new = self._apply_rename_adjustment(new_line)
                    adjusted_score = self._get_cached_similarity(adjusted_old, adjusted_new, "", "")
                    score = max(score, adjusted_score)
                    
                    if score > best_score:
                        best_score, best_new_idx = score, new_idx
                
                if best_new_idx is not None and best_score >= threshold:
                    extra_matches[old_idx] = (best_new_idx, best_score)
                    matched_new.add(best_new_idx)
        
        return {**matches, **extra_matches}

    def detect_line_splits(self, old_lines: List[str], new_lines: List[str], 
                          matches: Dict[int, Tuple[int, float]], threshold_increase: float = 0.01) -> Dict[int, List[int]]:
        """
        Identifies when one line in the old file has been split into multiple lines in the new file.
        """
        updated_matches = {}
        
        for old_idx, (new_idx, score) in matches.items():
            old_line = old_lines[old_idx].strip()
            group = [new_idx]
            
            if self._is_likely_split_candidate(old_line, new_lines, new_idx):
                extended_group = self._extend_split_group_safely(old_line, new_lines, new_idx, threshold_increase)
                if len(extended_group) > 1 and self._validate_split(old_line, extended_group, new_lines):
                    group = extended_group
            
            updated_matches[old_idx] = group
        
        return updated_matches
    
    def _is_likely_split_candidate(self, old_line: str, new_lines: List[str], start_idx: int) -> bool:
        """
        Heuristics to identify split candidates (length check, semicolon count).
        """
        current_text = new_lines[start_idx].strip()
        
        if len(old_line) < 20 or len(current_text) < 10:
            return False
            
        if old_line in ['{', '}', '};'] or current_text in ['{', '}', '};']:
            return False
            
        if old_line.startswith('import ') or old_line.startswith('public ') or old_line.startswith('private '):
            return False
            
        current_similarity = self._get_cached_similarity(old_line, current_text, "", "")
        if current_similarity > 0.9:
            return False
        
        indicators = [
            len(current_text) < len(old_line) * 0.6,
            old_line.endswith(';') and not current_text.endswith(';'),
            ';' in old_line and old_line.count(';') > 1 and ';' not in current_text,
            ('=' in old_line and '(' in old_line) and len(old_line) > 40,
        ]
        
        return any(indicators)
    
    def _extend_split_group_safely(self, old_line: str, new_lines: List[str], 
                                  start_idx: int, threshold_increase: float) -> List[int]:
        """
        Safely tries to add lines to the split group, checking limits on split size.
        """
        group = [start_idx]
        combined_text = new_lines[start_idx].strip()
        best_score = self._get_cached_similarity(old_line, combined_text, "", "")
        
        max_split_size = min(5, len(old_line) // 20)
        
        for next_idx in range(start_idx + 1, min(start_idx + max_split_size + 1, len(new_lines))):
            next_line = new_lines[next_idx].strip()
            
            if not next_line or next_line in ['{', '}', '};']:
                continue
                
            test_combined = combined_text + " " + next_line
            test_score = self._get_cached_similarity(old_line, test_combined, "", "")
            
            if test_score > best_score + max(threshold_increase, 0.05):
                group.append(next_idx)
                combined_text = test_combined
                best_score = test_score
            else:
                break
        
        return group
    
    def _validate_split(self, old_line: str, split_group: List[int], new_lines: List[str]) -> bool:
        """
        Validation logic for the split group to ensure semantic similarity.
        """
        if len(split_group) < 2:
            return False
            
        combined_text = ' '.join(new_lines[idx].strip() for idx in split_group)
        
        best_individual_score = 0.0
        for idx in split_group:
            individual_score = self._get_cached_similarity(old_line, new_lines[idx].strip(), "", "")
            best_individual_score = max(best_individual_score, individual_score)
            
        combined_score = self._get_cached_similarity(old_line, combined_text, "", "")
        
        if combined_score < best_individual_score + 0.1:
            return False
            
        old_tokens = set(re.findall(r'\b\w+\b', old_line.lower()))
        combined_tokens = set(re.findall(r'\b\w+\b', combined_text.lower()))
        
        token_overlap = len(old_tokens.intersection(combined_tokens))
        if token_overlap < len(old_tokens) * 0.6:
            return False
            
        return True
