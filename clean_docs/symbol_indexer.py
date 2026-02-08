"""Symbol indexer using tree-sitter to extract symbols from source code.

This module is optional. If tree-sitter is not installed,
snippet validation features will be disabled gracefully.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional dependencies - gracefully handle if not installed
try:
    import tree_sitter_language_pack as ts_langs
    from tree_sitter import Language, Parser, Node

    SNIPPETS_AVAILABLE = True
except ImportError:
    SNIPPETS_AVAILABLE = False
    ts_langs = None
    Language = None
    Parser = None
    Node = None


@dataclass
class Symbol:
    """Represents a symbol extracted from source code."""

    name: str
    type: str  # "function", "class", "method", "interface", etc.
    file_path: Path
    start_line: int
    end_line: int
    signature: str  # Full signature text
    code: str  # Full code block


# Language configurations for symbol extraction
LANGUAGE_CONFIG: Dict[str, Dict] = {
    "java": {
        "extension": ".java",
        "queries": {
            "class": "(class_declaration name: (identifier) @name) @class",
            "interface": "(interface_declaration name: (identifier) @name) @interface",
            "method": "(method_declaration name: (identifier) @name) @method",
            "constructor": "(constructor_declaration name: (identifier) @name) @constructor",
        },
    },
    "python": {
        "extension": ".py",
        "queries": {
            "class": "(class_definition name: (identifier) @name) @class",
            "function": "(function_definition name: (identifier) @name) @function",
        },
    },
    "scala": {
        "extension": ".scala",
        "queries": {
            "class": "(class_definition name: (identifier) @name) @class",
            "object": "(object_definition name: (identifier) @name) @object",
            "trait": "(trait_definition name: (identifier) @name) @trait",
            "function": "(function_definition name: (identifier) @name) @function",
        },
    },
    "typescript": {
        "extension": ".ts",
        "queries": {
            "class": "(class_declaration name: (type_identifier) @name) @class",
            "interface": "(interface_declaration name: (type_identifier) @name) @interface",
            "function": "(function_declaration name: (identifier) @name) @function",
            "method": "(method_definition name: (property_identifier) @name) @method",
        },
    },
    "javascript": {
        "extension": ".js",
        "queries": {
            "class": "(class_declaration name: (identifier) @name) @class",
            "function": "(function_declaration name: (identifier) @name) @function",
            "method": "(method_definition name: (property_identifier) @name) @method",
        },
    },
    "go": {
        "extension": ".go",
        "queries": {
            "function": "(function_declaration name: (identifier) @name) @function",
            "method": "(method_declaration name: (field_identifier) @name) @method",
            "type": "(type_declaration (type_spec name: (type_identifier) @name)) @type",
        },
    },
    "rust": {
        "extension": ".rs",
        "queries": {
            "function": "(function_item name: (identifier) @name) @function",
            "struct": "(struct_item name: (type_identifier) @name) @struct",
            "enum": "(enum_item name: (type_identifier) @name) @enum",
            "trait": "(trait_item name: (type_identifier) @name) @trait",
            "impl": "(impl_item type: (type_identifier) @name) @impl",
        },
    },
    "starlark": {
        "extension": ".bzl",
        "queries": {
            "function": "(function_definition name: (identifier) @name) @function",
        },
    },
}

# Map file extensions to languages
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ".java": "java",
    ".py": "python",
    ".scala": "scala",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".bzl": "starlark",
    ".bazel": "starlark",
}


class SymbolIndexer:
    """Index symbols from source code using tree-sitter."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if not SNIPPETS_AVAILABLE:
            raise ImportError(
                "Snippet validation requires tree-sitter. "
                "Install with: pip install clean-docs[snippets]"
            )

        self.cache_dir = cache_dir
        self._parsers: Dict[str, Parser] = {}
        self._symbols: Dict[str, List[Symbol]] = {}  # file_path -> symbols
        self._file_hashes: Dict[str, str] = {}  # file_path -> content_hash

    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get or create a parser for the given language."""
        if language not in self._parsers:
            try:
                lang = ts_langs.get_language(language)
                parser = Parser(lang)
                self._parsers[language] = parser
            except Exception:
                return None

        return self._parsers.get(language)

    def _compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_language_for_file(self, file_path: Path) -> Optional[str]:
        """Get the language name for a file based on extension."""
        ext = file_path.suffix.lower()
        return EXTENSION_TO_LANGUAGE.get(ext)

    def index_file(self, file_path: Path) -> List[Symbol]:
        """Extract all symbols from a source file."""
        if not file_path.exists():
            return []

        language = self._get_language_for_file(file_path)
        if not language:
            return []

        content = file_path.read_text(encoding="utf-8")
        content_hash = self._compute_hash(content)

        # Check if already indexed
        str_path = str(file_path)
        if str_path in self._symbols and self._file_hashes.get(str_path) == content_hash:
            return self._symbols[str_path]

        parser = self._get_parser(language)
        if not parser:
            return []

        try:
            tree = parser.parse(content.encode())
            symbols = self._extract_symbols_from_tree(tree.root_node, file_path, content, language)

            self._symbols[str_path] = symbols
            self._file_hashes[str_path] = content_hash

            return symbols
        except Exception:
            return []

    def _extract_symbols_from_tree(
        self, root: Node, file_path: Path, content: str, language: str
    ) -> List[Symbol]:
        """Extract symbols from a parsed tree using tree-sitter queries."""
        symbols = []
        lines = content.split("\n")

        # Use pattern matching on node types
        LANGUAGE_CONFIG.get(language, {})

        def visit_node(node: Node) -> None:
            symbol = self._try_extract_symbol(node, file_path, lines, language)
            if symbol:
                symbols.append(symbol)

            for child in node.children:
                visit_node(child)

        visit_node(root)
        return symbols

    def _try_extract_symbol(
        self, node: Node, file_path: Path, lines: List[str], language: str
    ) -> Optional[Symbol]:
        """Try to extract a symbol from a node based on language-specific patterns."""
        node_type = node.type

        # Java symbols
        if language == "java":
            if node_type == "class_declaration":
                return self._extract_java_class(node, file_path, lines)
            elif node_type == "interface_declaration":
                return self._extract_java_class(node, file_path, lines, "interface")
            elif node_type == "method_declaration":
                return self._extract_java_method(node, file_path, lines)
            elif node_type == "constructor_declaration":
                return self._extract_java_method(node, file_path, lines, "constructor")

        # Python symbols
        elif language == "python":
            if node_type == "class_definition":
                return self._extract_python_class(node, file_path, lines)
            elif node_type == "function_definition":
                return self._extract_python_function(node, file_path, lines)

        # Scala symbols
        elif language == "scala":
            if node_type in ("class_definition", "trait_definition", "object_definition"):
                return self._extract_scala_class(
                    node, file_path, lines, node_type.replace("_definition", "")
                )
            elif node_type == "function_definition":
                return self._extract_scala_function(node, file_path, lines)

        # TypeScript/JavaScript symbols
        elif language in ("typescript", "javascript"):
            if node_type == "class_declaration":
                return self._extract_js_class(node, file_path, lines)
            elif node_type == "function_declaration":
                return self._extract_js_function(node, file_path, lines)
            elif node_type == "interface_declaration":
                return self._extract_js_class(node, file_path, lines, "interface")

        # Go symbols
        elif language == "go":
            if node_type == "function_declaration":
                return self._extract_go_function(node, file_path, lines)
            elif node_type == "method_declaration":
                return self._extract_go_function(node, file_path, lines, "method")
            elif node_type == "type_declaration":
                return self._extract_go_type(node, file_path, lines)

        # Rust symbols
        elif language == "rust":
            if node_type == "function_item":
                return self._extract_rust_function(node, file_path, lines)
            elif node_type in ("struct_item", "enum_item", "trait_item"):
                return self._extract_rust_type(
                    node, file_path, lines, node_type.replace("_item", "")
                )

        # Starlark/Bazel symbols
        elif language == "starlark":
            if node_type == "function_definition":
                return self._extract_starlark_function(node, file_path, lines)

        return None

    def _get_name_node(self, node: Node, name_types: List[str]) -> Optional[Node]:
        """Find a child node that represents the name."""
        for child in node.children:
            if child.type in name_types:
                return child
            # Sometimes name is nested in a field
            if hasattr(child, "children"):
                for grandchild in child.children:
                    if grandchild.type in name_types:
                        return grandchild
        return None

    def _get_code_range(self, node: Node, lines: List[str]) -> Tuple[int, int, str]:
        """Get start line, end line, and code for a node."""
        start_line = node.start_point[0] + 1  # 1-indexed
        end_line = node.end_point[0] + 1
        code = "\n".join(lines[node.start_point[0] : node.end_point[0] + 1])
        return start_line, end_line, code

    def _extract_java_class(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str = "class"
    ) -> Optional[Symbol]:
        """Extract a Java class or interface."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)

        # Get signature (first line usually)
        signature_end = code.find("{")
        signature = code[:signature_end].strip() if signature_end > 0 else code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_java_method(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str = "method"
    ) -> Optional[Symbol]:
        """Extract a Java method or constructor."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)

        # Get signature
        signature_end = code.find("{")
        signature = code[:signature_end].strip() if signature_end > 0 else code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_python_class(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a Python class."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type="class",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_python_function(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a Python function."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        # Determine if method or function based on parent
        symbol_type = "function"
        if node.parent and node.parent.type == "block":
            if node.parent.parent and node.parent.parent.type == "class_definition":
                symbol_type = "method"

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_scala_class(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str
    ) -> Optional[Symbol]:
        """Extract a Scala class/trait/object."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_scala_function(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a Scala function."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type="function",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_js_class(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str = "class"
    ) -> Optional[Symbol]:
        """Extract a JavaScript/TypeScript class or interface."""
        name_node = self._get_name_node(node, ["identifier", "type_identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_js_function(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a JavaScript/TypeScript function."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type="function",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_go_function(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str = "function"
    ) -> Optional[Symbol]:
        """Extract a Go function or method."""
        name_node = self._get_name_node(node, ["identifier", "field_identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_go_type(self, node: Node, file_path: Path, lines: List[str]) -> Optional[Symbol]:
        """Extract a Go type declaration."""
        # Type declarations contain type_spec children
        for child in node.children:
            if child.type == "type_spec":
                name_node = self._get_name_node(child, ["type_identifier"])
                if name_node:
                    name = name_node.text.decode() if name_node.text else ""
                    start_line, end_line, code = self._get_code_range(node, lines)
                    signature = code.split("\n")[0]

                    return Symbol(
                        name=name,
                        type="type",
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        signature=signature,
                        code=code,
                    )
        return None

    def _extract_rust_function(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a Rust function."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type="function",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_rust_type(
        self, node: Node, file_path: Path, lines: List[str], symbol_type: str
    ) -> Optional[Symbol]:
        """Extract a Rust struct/enum/trait."""
        name_node = self._get_name_node(node, ["type_identifier", "identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def _extract_starlark_function(
        self, node: Node, file_path: Path, lines: List[str]
    ) -> Optional[Symbol]:
        """Extract a Starlark/Bazel function."""
        name_node = self._get_name_node(node, ["identifier"])
        if not name_node:
            return None

        name = name_node.text.decode() if name_node.text else ""
        start_line, end_line, code = self._get_code_range(node, lines)
        signature = code.split("\n")[0]

        return Symbol(
            name=name,
            type="function",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            code=code,
        )

    def index_directory(self, directory: Path, extensions: Optional[List[str]] = None) -> int:
        """Index all source files in a directory.

        Args:
            directory: Root directory to scan
            extensions: List of file extensions to include (e.g., [".java", ".py"])
                       If None, includes all supported extensions.

        Returns:
            Number of files indexed
        """
        if extensions is None:
            extensions = list(EXTENSION_TO_LANGUAGE.keys())

        # Directories to skip
        skip_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            ".tox",
            ".pytest_cache",
            "dist",
            "build",
            ".eggs",
            "site-packages",
            ".mypy_cache",
            ".ruff_cache",
            "target",
            "bazel-bin",
            "bazel-out",
            "bazel-testlogs",
            ".idea",
            ".vscode",
        }

        count = 0
        for ext in extensions:
            for file_path in directory.rglob(f"*{ext}"):
                # Skip if any part of path is in skip_dirs
                if any(part in skip_dirs for part in file_path.parts):
                    continue

                symbols = self.index_file(file_path)
                if symbols:
                    count += 1

        return count

    def find_symbol(self, name: str, symbol_type: Optional[str] = None) -> List[Symbol]:
        """Find symbol by name across indexed files.

        Args:
            name: Symbol name to search for
            symbol_type: Optional type filter ("function", "class", "method", etc.)

        Returns:
            List of matching symbols
        """
        results = []
        for symbols in self._symbols.values():
            for symbol in symbols:
                if symbol.name == name:
                    if symbol_type is None or symbol.type == symbol_type:
                        results.append(symbol)
        return results

    def find_symbols_by_prefix(
        self, prefix: str, symbol_type: Optional[str] = None
    ) -> List[Symbol]:
        """Find symbols by name prefix."""
        results = []
        for symbols in self._symbols.values():
            for symbol in symbols:
                if symbol.name.startswith(prefix):
                    if symbol_type is None or symbol.type == symbol_type:
                        results.append(symbol)
        return results

    def get_symbol_code(self, symbol: Symbol) -> str:
        """Get the full code for a symbol."""
        return symbol.code

    def get_all_symbols(self) -> List[Symbol]:
        """Get all indexed symbols."""
        all_symbols = []
        for symbols in self._symbols.values():
            all_symbols.extend(symbols)
        return all_symbols

    def get_symbols_for_file(self, file_path: Path) -> List[Symbol]:
        """Get all symbols for a specific file."""
        return self._symbols.get(str(file_path), [])

    def clear(self) -> None:
        """Clear the index."""
        self._symbols.clear()
        self._file_hashes.clear()
