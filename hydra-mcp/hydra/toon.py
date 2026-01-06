"""TOON formatter wrapper for Hydra MCP responses.

Uses the official toon-format library to encode API responses in TOON
(Text-Oriented Object Notation) format, providing 30-60% token reduction
compared to JSON while maintaining readability for LLMs.

See: https://github.com/toon-format/toon-python
"""

from typing import Any

from toon_format import encode


class TOONFormatter:
    """Wrapper for TOON encoding with Hydra-specific defaults."""

    def __init__(self, delimiter: str = ",", indent: int = 2, length_marker: str = ""):
        """Initialize the formatter.

        Args:
            delimiter: Field delimiter ("," | "\t" | "|")
            indent: Spaces per indentation level
            length_marker: Prefix for array lengths ("" or "#")
        """
        self.options = {
            "delimiter": delimiter,
            "indent": indent,
            "lengthMarker": length_marker,
        }

    def format(self, data: Any) -> str:
        """Encode any data structure to TOON format.

        Args:
            data: Any JSON-serializable Python object

        Returns:
            TOON-formatted string
        """
        return encode(data, self.options)

    def format_response(self, data: Any, title: str | None = None) -> str:
        """Format an API response with optional title header.

        Args:
            data: Response data to format
            title: Optional title to prepend

        Returns:
            TOON-formatted string with optional header
        """
        output = ""
        if title:
            output = f"# {title}\n\n"
        output += encode(data, self.options)
        return output

    def format_error(self, code: str, message: str, details: dict | None = None) -> str:
        """Format an error response.

        Args:
            code: Error code
            message: Error message
            details: Optional error details

        Returns:
            TOON-formatted error
        """
        error_data = {
            "error": {
                "code": code,
                "message": message,
            }
        }
        if details:
            error_data["error"]["details"] = details
        return encode(error_data, self.options)
