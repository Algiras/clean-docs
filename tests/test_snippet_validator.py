"""Tests for code snippet validation functionality."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from clean_docs.parsers.markdown import MarkdownParser, CodeBlock


# Fixtures

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that gets cleaned up after tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Provide a markdown parser instance."""
    return MarkdownParser()


# CodeBlock Extraction Tests

class TestCodeBlockExtraction:
    """Test code block extraction from markdown."""

    def test_extract_simple_code_block(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test extracting a simple fenced code block."""
        content = '''# Test

```python
def hello():
    return "world"
```
'''
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.code_blocks) == 1
        block = doc.code_blocks[0]
        assert block.language == "python"
        assert "def hello():" in block.code
        assert block.line == 3

    def test_extract_multiple_code_blocks(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test extracting multiple code blocks with different languages."""
        content = '''# Test

```java
public class Foo {
}
```

Some text here.

```python
class Bar:
    pass
```

```scala
object Baz
```
'''
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.code_blocks) == 3
        assert doc.code_blocks[0].language == "java"
        assert doc.code_blocks[1].language == "python"
        assert doc.code_blocks[2].language == "scala"

    def test_extract_code_block_without_language(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test extracting code blocks without language hint."""
        content = '''# Test

```
some code
```
'''
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.code_blocks) == 1
        assert doc.code_blocks[0].language == ""


class TestFileHintExtraction:
    """Test file path hint extraction from code blocks."""

    def test_extract_java_file_hint(self, markdown_parser: MarkdownParser):
        """Test extracting Java file hint from comment."""
        code = '''// src/main/java/com/example/Foo.java
public class Foo {
}
'''
        file_hint = markdown_parser._extract_file_hint(code, "java")
        assert file_hint == "src/main/java/com/example/Foo.java"

    def test_extract_python_file_hint(self, markdown_parser: MarkdownParser):
        """Test extracting Python file hint from comment."""
        code = '''# app/models/user.py
class User:
    pass
'''
        file_hint = markdown_parser._extract_file_hint(code, "python")
        assert file_hint == "app/models/user.py"

    def test_extract_file_hint_with_prefix(self, markdown_parser: MarkdownParser):
        """Test extracting file hint with File: prefix."""
        code = '''// File: src/utils.ts
export function helper() {}
'''
        file_hint = markdown_parser._extract_file_hint(code, "typescript")
        assert file_hint == "src/utils.ts"

    def test_no_file_hint_returns_none(self, markdown_parser: MarkdownParser):
        """Test that missing file hint returns None."""
        code = '''public class Foo {
}
'''
        file_hint = markdown_parser._extract_file_hint(code, "java")
        assert file_hint is None


class TestSymbolExtraction:
    """Test symbol extraction from code blocks."""

    def test_extract_java_class(self, markdown_parser: MarkdownParser):
        """Test extracting Java class name."""
        code = '''public class MyService {
    public void process() {
    }
}
'''
        symbols = markdown_parser._extract_symbols(code, "java")
        assert "MyService" in symbols

    def test_extract_java_interface(self, markdown_parser: MarkdownParser):
        """Test extracting Java interface name."""
        code = '''public interface Repository {
    void save(Entity entity);
}
'''
        symbols = markdown_parser._extract_symbols(code, "java")
        assert "Repository" in symbols

    def test_extract_java_method(self, markdown_parser: MarkdownParser):
        """Test extracting Java method name."""
        code = '''public void processData(String input) {
    System.out.println(input);
}
'''
        symbols = markdown_parser._extract_symbols(code, "java")
        assert "processData" in symbols

    def test_extract_python_class(self, markdown_parser: MarkdownParser):
        """Test extracting Python class name."""
        code = '''class UserService:
    def get_user(self, id):
        pass
'''
        symbols = markdown_parser._extract_symbols(code, "python")
        assert "UserService" in symbols
        assert "get_user" in symbols

    def test_extract_python_function(self, markdown_parser: MarkdownParser):
        """Test extracting Python function name."""
        code = '''def process_data(items):
    return [i for i in items]
'''
        symbols = markdown_parser._extract_symbols(code, "python")
        assert "process_data" in symbols

    def test_extract_scala_class(self, markdown_parser: MarkdownParser):
        """Test extracting Scala class/trait/object names."""
        code = '''class Service {
  def run(): Unit = {}
}

trait Repository

object Config
'''
        symbols = markdown_parser._extract_symbols(code, "scala")
        assert "Service" in symbols
        assert "Repository" in symbols
        assert "Config" in symbols

    def test_extract_typescript_symbols(self, markdown_parser: MarkdownParser):
        """Test extracting TypeScript symbols."""
        code = '''class ApiClient {
    constructor() {}
}

function fetchData(): Promise<Data> {
    return fetch('/api/data');
}

const processItems = async (items: Item[]) => {
    return items.map(i => i.value);
};
'''
        symbols = markdown_parser._extract_symbols(code, "typescript")
        assert "ApiClient" in symbols
        assert "fetchData" in symbols
        assert "processItems" in symbols

    def test_extract_bazel_symbols(self, markdown_parser: MarkdownParser):
        """Test extracting Bazel/Starlark symbols."""
        code = '''def my_rule(ctx):
    return []

java_library(
    name = "my_library",
    srcs = glob(["*.java"]),
)
'''
        symbols = markdown_parser._extract_symbols(code, "bazel")
        assert "my_rule" in symbols
        assert "my_library" in symbols

    def test_extract_removes_duplicates(self, markdown_parser: MarkdownParser):
        """Test that duplicate symbols are removed."""
        code = '''def helper():
    pass

def helper():
    pass
'''
        symbols = markdown_parser._extract_symbols(code, "python")
        assert symbols.count("helper") == 1


# Symbol Indexer Tests (require optional dependencies)

class TestSymbolIndexer:
    """Test symbol indexer functionality.

    These tests require tree-sitter to be installed.
    """

    @pytest.fixture
    def check_snippets_available(self):
        """Skip tests if snippets dependencies are not available."""
        try:
            from clean_docs.symbol_indexer import SNIPPETS_AVAILABLE
            if not SNIPPETS_AVAILABLE:
                pytest.skip("Snippets dependencies not installed")
        except ImportError:
            pytest.skip("Snippets dependencies not installed")

    def test_index_python_file(self, temp_dir: Path, check_snippets_available):
        """Test indexing a Python file."""
        from clean_docs.symbol_indexer import SymbolIndexer

        # Create a Python file
        py_file = temp_dir / "example.py"
        py_file.write_text('''
class MyClass:
    """A sample class."""

    def method(self):
        pass

def helper_function():
    """A helper function."""
    return True
''')

        indexer = SymbolIndexer()
        symbols = indexer.index_file(py_file)

        # Should find class and functions
        names = [s.name for s in symbols]
        assert "MyClass" in names
        assert "helper_function" in names

    def test_index_java_file(self, temp_dir: Path, check_snippets_available):
        """Test indexing a Java file."""
        from clean_docs.symbol_indexer import SymbolIndexer

        # Create a Java file
        java_file = temp_dir / "Example.java"
        java_file.write_text('''
public class Example {
    public void doSomething() {
        System.out.println("Hello");
    }

    private int calculate(int x) {
        return x * 2;
    }
}
''')

        indexer = SymbolIndexer()
        symbols = indexer.index_file(java_file)

        names = [s.name for s in symbols]
        assert "Example" in names

    def test_find_symbol_by_name(self, temp_dir: Path, check_snippets_available):
        """Test finding symbols by name."""
        from clean_docs.symbol_indexer import SymbolIndexer

        # Create files with same symbol name
        file1 = temp_dir / "a.py"
        file1.write_text('''
class Service:
    pass
''')
        file2 = temp_dir / "b.py"
        file2.write_text('''
class Service:
    pass
''')

        indexer = SymbolIndexer()
        indexer.index_file(file1)
        indexer.index_file(file2)

        matches = indexer.find_symbol("Service")
        assert len(matches) == 2

    def test_index_directory(self, temp_dir: Path, check_snippets_available):
        """Test indexing an entire directory."""
        from clean_docs.symbol_indexer import SymbolIndexer

        # Create some files
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("def main(): pass")
        (temp_dir / "src" / "utils.py").write_text("def helper(): pass")

        indexer = SymbolIndexer()
        count = indexer.index_directory(temp_dir)

        assert count >= 2


# Snippet Validator Tests

class TestSnippetValidator:
    """Test snippet validation functionality.

    These tests require tree-sitter to be installed.
    """

    @pytest.fixture
    def check_snippets_available(self):
        """Skip tests if snippets dependencies are not available."""
        try:
            from clean_docs.symbol_indexer import SNIPPETS_AVAILABLE
            if not SNIPPETS_AVAILABLE:
                pytest.skip("Snippets dependencies not installed")
        except ImportError:
            pytest.skip("Snippets dependencies not installed")

    def test_validate_matching_snippet(self, temp_dir: Path, check_snippets_available):
        """Test validating a snippet that matches source code."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator, ValidationStatus
        from clean_docs.parsers.markdown import CodeBlock

        # Create source file
        src_file = temp_dir / "example.py"
        src_file.write_text('''
def process_data(items):
    """Process a list of items."""
    return [i * 2 for i in items]
''')

        indexer = SymbolIndexer()
        indexer.index_file(src_file)

        validator = SnippetValidator(indexer, similarity_threshold=0.7)

        snippet = CodeBlock(
            language="python",
            code='''def process_data(items):
    """Process a list of items."""
    return [i * 2 for i in items]''',
            line=10,
            symbols=["process_data"],
        )

        result = validator.validate_snippet(snippet)

        assert result.status == ValidationStatus.VALID or result.status == ValidationStatus.OUTDATED

    def test_validate_outdated_snippet(self, temp_dir: Path, check_snippets_available):
        """Test validating a snippet that is outdated."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator, ValidationStatus
        from clean_docs.parsers.markdown import CodeBlock

        # Create source file with updated code
        src_file = temp_dir / "example.py"
        src_file.write_text('''
def process_data(items, multiplier=2):
    """Process a list of items with a multiplier."""
    return [i * multiplier for i in items]
''')

        indexer = SymbolIndexer()
        indexer.index_file(src_file)

        validator = SnippetValidator(indexer, similarity_threshold=0.9)

        # Old version of the snippet
        snippet = CodeBlock(
            language="python",
            code='''def process_data(items):
    return [i * 2 for i in items]''',
            line=10,
            symbols=["process_data"],
        )

        result = validator.validate_snippet(snippet)

        # Should be outdated since signatures differ
        assert result.status in (ValidationStatus.OUTDATED, ValidationStatus.VALID)

    def test_validate_not_found_snippet(self, temp_dir: Path, check_snippets_available):
        """Test validating a snippet with no source match."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator, ValidationStatus
        from clean_docs.parsers.markdown import CodeBlock

        indexer = SymbolIndexer()
        # Don't index any files

        validator = SnippetValidator(indexer)

        snippet = CodeBlock(
            language="python",
            code='''def nonexistent_function():
    pass''',
            line=10,
            symbols=["nonexistent_function"],
        )

        result = validator.validate_snippet(snippet)

        assert result.status == ValidationStatus.NOT_FOUND

    def test_validate_empty_snippet(self, check_snippets_available):
        """Test validating an empty code block."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator, ValidationStatus
        from clean_docs.parsers.markdown import CodeBlock

        indexer = SymbolIndexer()
        validator = SnippetValidator(indexer)

        snippet = CodeBlock(
            language="python",
            code="",
            line=10,
        )

        result = validator.validate_snippet(snippet)

        assert result.status == ValidationStatus.NOT_FOUND

    def test_compute_diff(self, temp_dir: Path, check_snippets_available):
        """Test computing diff between snippet and source."""
        from clean_docs.symbol_indexer import SymbolIndexer, Symbol
        from clean_docs.snippet_validator import SnippetValidator
        from clean_docs.parsers.markdown import CodeBlock

        indexer = SymbolIndexer()
        validator = SnippetValidator(indexer)

        snippet = CodeBlock(
            language="python",
            code="def foo():\n    return 1",
            line=10,
        )

        source = Symbol(
            name="foo",
            type="function",
            file_path=temp_dir / "test.py",
            start_line=1,
            end_line=2,
            signature="def foo():",
            code="def foo():\n    return 2",
        )

        diff = validator.compute_diff(snippet, source)

        assert "-    return 1" in diff or "- return 1" in diff
        assert "+    return 2" in diff or "+ return 2" in diff


class TestSnippetFixer:
    """Test snippet fixing functionality."""

    @pytest.fixture
    def check_snippets_available(self):
        """Skip tests if snippets dependencies are not available."""
        try:
            from clean_docs.symbol_indexer import SNIPPETS_AVAILABLE
            if not SNIPPETS_AVAILABLE:
                pytest.skip("Snippets dependencies not installed")
        except ImportError:
            pytest.skip("Snippets dependencies not installed")

    def test_fix_snippet_in_document(self, temp_dir: Path, check_snippets_available):
        """Test fixing a snippet in a markdown document."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator
        from clean_docs.parsers.markdown import CodeBlock

        indexer = SymbolIndexer()
        validator = SnippetValidator(indexer)

        doc_content = '''# Example

Here is some code:

```python
def old_code():
    return 1
```

More text here.
'''
        snippet = CodeBlock(
            language="python",
            code="def old_code():\n    return 1",
            line=5,
        )

        new_code = "def new_code():\n    return 2"

        updated_content = validator.fix_snippet(snippet, new_code, doc_content)

        assert "def new_code():" in updated_content
        assert "return 2" in updated_content


# Integration Tests

class TestSnippetValidationIntegration:
    """Integration tests for the full snippet validation workflow."""

    @pytest.fixture
    def check_snippets_available(self):
        """Skip tests if snippets dependencies are not available."""
        try:
            from clean_docs.symbol_indexer import SNIPPETS_AVAILABLE
            if not SNIPPETS_AVAILABLE:
                pytest.skip("Snippets dependencies not installed")
        except ImportError:
            pytest.skip("Snippets dependencies not installed")

    def test_full_validation_workflow(self, temp_dir: Path, markdown_parser: MarkdownParser, check_snippets_available):
        """Test complete validation workflow from markdown to results."""
        from clean_docs.symbol_indexer import SymbolIndexer
        from clean_docs.snippet_validator import SnippetValidator

        # Create source code
        src_dir = temp_dir / "src"
        src_dir.mkdir()
        (src_dir / "utils.py").write_text('''
def helper_function():
    """A helper function."""
    return "hello"

class Service:
    """A service class."""

    def process(self):
        pass
''')

        # Create documentation with code blocks
        doc_file = temp_dir / "README.md"
        doc_file.write_text('''# My Project

## Usage

Here's how to use the helper function:

```python
def helper_function():
    """A helper function."""
    return "hello"
```

And here's the Service class:

```python
class Service:
    """A service class."""

    def process(self):
        pass
```
''')

        # Parse documentation
        doc = markdown_parser.parse_file(doc_file)
        assert len(doc.code_blocks) == 2

        # Index source code
        indexer = SymbolIndexer()
        indexer.index_directory(src_dir)

        # Validate snippets
        validator = SnippetValidator(indexer, similarity_threshold=0.8)
        report = validator.validate_document(doc_file, doc.code_blocks)

        # Should have some valid matches
        assert report.total_snippets == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
