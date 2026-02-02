# Contributing to Clean Docs

Thank you for your interest in contributing to Clean Docs! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- pip or conda for package management
- Git

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/clean-docs.git
cd clean-docs

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev,semantic]"

# Run tests to verify setup
pytest
```

## 📝 Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write clear, concise code
- Follow existing code style (enforced by Black and Ruff)
- Add tests for new features
- Update documentation as needed

### 3. Run Tests and Linting

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=clean_docs

# Format code
black clean_docs/ tests/

# Lint code
ruff clean_docs/ tests/

# Type checking
mypy clean_docs/
```

### 4. Test Your Changes

```bash
# Test CLI locally
clean-docs doctor
clean-docs scan ./test_docs

# Test fix mode
clean-docs scan ./test_docs --fix --dry-run
```

## 🧪 Testing Guidelines

### Test Structure

```python
# tests/test_new_feature.py
import pytest
from clean_docs.module import NewFeature

class TestNewFeature:
    """Tests for NewFeature."""
    
    def test_basic_functionality(self):
        """Test basic feature operation."""
        feature = NewFeature()
        result = feature.do_something()
        assert result == expected
    
    def test_edge_cases(self):
        """Test edge cases and error handling."""
        pass
```

### Running Specific Tests

```bash
# Run specific test file
pytest tests/test_link_checker.py

# Run specific test
pytest tests/test_link_checker.py::TestLinkChecker::test_check_internal_link

# Run with verbose output
pytest -v

# Run with debugging
pytest --pdb
```

## 📋 Code Style

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **MyPy** for type checking

### Pre-commit Hooks (Recommended)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## 🎯 Areas for Contribution

### High Priority

- [ ] Better anchor suggestion algorithm
- [ ] More link types support (e.g., Sphinx references)
- [ ] Enhanced semantic analysis features
- [ ] Performance optimizations

### Documentation

- [ ] More usage examples
- [ ] Video tutorials
- [ ] Blog posts about use cases
- [ ] Translation to other languages

### Features

- [ ] Plugin system for custom checkers
- [ ] Web dashboard for results visualization
- [ ] Integration with more CI/CD platforms
- [ ] Pre-commit hook integration

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **Clear description** of what went wrong
2. **Steps to reproduce** the issue
3. **Expected vs actual behavior**
4. **Environment info**:
   - Python version: `python --version`
   - Clean Docs version: `clean-docs --version`
   - OS and version
5. **Sample files** or minimal reproduction case

Example:

```markdown
**Bug:** Anchor suggestions not working for headers with special characters

**Steps:**
1. Create file with heading: `## API v2.0 (Beta)`
2. Link to it: `[API](#api-v20-beta)`
3. Run: `clean-docs scan .`

**Expected:** Link should be valid
**Actual:** Reports as broken with no suggestion

**Environment:**
- Python 3.12
- Clean Docs 0.1.0
- macOS 14.2
```

## 💡 Suggesting Features

Feature suggestions are welcome! Please:

1. Check if the feature already exists or is planned
2. Describe the use case clearly
3. Explain why it would benefit users
4. Consider implementation complexity

## 📚 Documentation

When updating documentation:

- Keep README.md concise and focused on usage
- Add detailed docs to docs/ folder if needed
- Update CHANGELOG.md with your changes
- Include code examples where helpful

## 🔍 Review Process

Pull requests will be reviewed for:

1. **Code quality** (style, tests, type hints)
2. **Functionality** (does it work as intended)
3. **Documentation** (updated and clear)
4. **Tests** (adequate coverage)
5. **Breaking changes** (avoid or clearly document)

## 🙏 Thank You!

Your contributions make Clean Docs better for everyone. We appreciate your time and effort!

## 📞 Questions?

- Open an issue for bugs or features
- Start a discussion for questions
- Check existing issues before creating new ones

---

**Happy documenting! 📝**