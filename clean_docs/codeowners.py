"""CODEOWNERS file parser and path matching."""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CodeOwnerRule:
    """A single rule from CODEOWNERS file."""
    pattern: str
    owners: List[str]
    line_number: int
    is_negation: bool = False
    
    def matches(self, path: str) -> bool:
        """Check if this rule matches a given path.
        
        CODEOWNERS uses gitignore-style patterns:
        - Patterns starting with / are relative to root
        - Patterns without / match anywhere (like **/pattern)
        - Patterns ending with / match directories
        - * matches anything except /
        - ** matches anything including /
        """
        pattern = self.pattern
        
        # Handle negation patterns (rare but supported)
        if pattern.startswith('!'):
            pattern = pattern[1:]
        
        # Normalize path (remove leading ./ or /)
        path = path.lstrip('./')
        
        # Handle root-relative patterns
        if pattern.startswith('/'):
            pattern = pattern[1:]
            # Must match from root
            return self._match_pattern(pattern, path)
        else:
            # Can match anywhere in path - try matching from each directory level
            # But typically CODEOWNERS patterns without / are still root-relative
            # when they contain a directory separator
            if '/' in pattern:
                return self._match_pattern(pattern, path)
            else:
                # Simple filename pattern - match anywhere
                return self._match_pattern('**/' + pattern, path)
    
    def _match_pattern(self, pattern: str, path: str) -> bool:
        """Match a pattern against a path using gitignore-style rules."""
        # Remove trailing slash from pattern (matches directory or file)
        pattern = pattern.rstrip('/')
        
        # Convert gitignore pattern to regex
        regex = self._pattern_to_regex(pattern)
        
        # Try to match the full path or any parent directory
        if re.match(regex, path):
            return True
        
        # For directory patterns, check if path is under that directory
        if not pattern.endswith('*'):
            dir_regex = self._pattern_to_regex(pattern + '/**')
            if re.match(dir_regex, path):
                return True
        
        return False
    
    def _pattern_to_regex(self, pattern: str) -> str:
        """Convert a gitignore-style pattern to a regex."""
        # Escape regex special chars except * and ?
        regex = ''
        i = 0
        while i < len(pattern):
            c = pattern[i]
            if c == '*':
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
                    # ** matches anything including /
                    if i + 2 < len(pattern) and pattern[i + 2] == '/':
                        regex += '(?:.*/)?'
                        i += 3
                        continue
                    else:
                        regex += '.*'
                        i += 2
                        continue
                else:
                    # * matches anything except /
                    regex += '[^/]*'
            elif c == '?':
                regex += '[^/]'
            elif c in '.^$+{}[]|()\\':
                regex += '\\' + c
            else:
                regex += c
            i += 1
        
        return '^' + regex + '$'


@dataclass
class CodeOwners:
    """Parsed CODEOWNERS file with path matching."""
    rules: List[CodeOwnerRule] = field(default_factory=list)
    default_owners: List[str] = field(default_factory=list)
    
    @classmethod
    def parse_file(cls, codeowners_path: Path) -> "CodeOwners":
        """Parse a CODEOWNERS file."""
        if not codeowners_path.exists():
            return cls()
        
        content = codeowners_path.read_text(encoding="utf-8")
        return cls.parse_content(content)
    
    @classmethod
    def parse_content(cls, content: str) -> "CodeOwners":
        """Parse CODEOWNERS content."""
        rules = []
        default_owners = []
        
        for line_num, line in enumerate(content.split('\n'), 1):
            # Remove comments
            line = line.split('#')[0].strip()
            
            if not line:
                continue
            
            # Parse the line: pattern followed by owners
            parts = line.split()
            if len(parts) < 2:
                continue
            
            pattern = parts[0]
            owners = parts[1:]
            
            # Filter valid owners (start with @ or are email addresses)
            owners = [o for o in owners if o.startswith('@') or '@' in o]
            
            if not owners:
                continue
            
            # Check for default rule (*)
            if pattern == '*':
                default_owners = owners
                continue
            
            is_negation = pattern.startswith('!')
            
            rules.append(CodeOwnerRule(
                pattern=pattern,
                owners=owners,
                line_number=line_num,
                is_negation=is_negation,
            ))
        
        return cls(rules=rules, default_owners=default_owners)
    
    @classmethod
    def find_and_parse(cls, repo_root: Path) -> Optional["CodeOwners"]:
        """Find and parse CODEOWNERS from standard locations."""
        # Standard CODEOWNERS locations
        locations = [
            repo_root / "CODEOWNERS",
            repo_root / ".github" / "CODEOWNERS",
            repo_root / "docs" / "CODEOWNERS",
        ]
        
        for path in locations:
            if path.exists():
                return cls.parse_file(path)
        
        return None
    
    def get_owners(self, file_path: str) -> List[str]:
        """Get the owners for a given file path.
        
        Returns the owners from the last matching rule (CODEOWNERS uses
        last-match-wins semantics, like .gitignore).
        """
        # Normalize path
        file_path = str(file_path).lstrip('./')
        
        matching_owners = self.default_owners.copy()
        
        # Find all matching rules (last one wins)
        for rule in self.rules:
            if rule.matches(file_path):
                if rule.is_negation:
                    # Negation clears previous owners
                    matching_owners = []
                else:
                    matching_owners = rule.owners.copy()
        
        return matching_owners
    
    def get_owner_key(self, file_path: str) -> str:
        """Get a stable key representing the owners for grouping.
        
        Returns a sorted, comma-separated string of owners.
        """
        owners = self.get_owners(file_path)
        if not owners:
            return "_no_owner_"
        return ",".join(sorted(owners))
    
    def group_files_by_owner(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group a list of files by their owners.
        
        Returns a dict mapping owner_key -> list of file paths.
        """
        groups: Dict[str, List[str]] = {}
        
        for path in file_paths:
            owner_key = self.get_owner_key(path)
            if owner_key not in groups:
                groups[owner_key] = []
            groups[owner_key].append(path)
        
        return groups
    
    def get_all_owners(self) -> Set[str]:
        """Get all unique owners defined in the file."""
        owners = set(self.default_owners)
        for rule in self.rules:
            owners.update(rule.owners)
        return owners
