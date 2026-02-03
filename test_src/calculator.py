"""Calculator module with basic operations."""


def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a.

    Args:
        a: First number
        b: Second number to subtract

    Returns:
        Difference of a and b
    """
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b


class Calculator:
    """A simple calculator class."""

    def __init__(self, initial_value: int = 0):
        """Initialize calculator with a value.

        Args:
            initial_value: Starting value (default 0)
        """
        self.value = initial_value

    def add(self, x: int) -> "Calculator":
        """Add x to the current value."""
        self.value += x
        return self

    def reset(self) -> "Calculator":
        """Reset value to zero."""
        self.value = 0
        return self
