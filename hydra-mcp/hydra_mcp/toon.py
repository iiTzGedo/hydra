"""TOON formatter wrapper for Hydra MCP responses.

Uses the official toon-format library to encode API responses in TOON
(Text-Oriented Object Notation) format, providing 30-60% token reduction
compared to JSON while maintaining readability for LLMs.

See: https://github.com/toon-format/toon-python
"""

from typing import Any

from toon_format import encode


class TOONFormatter:
    """Wrapper for TOON encoding with Hydra-specific defaults.

    TOON (Text-Oriented Object Notation) provides a more compact and
    LLM-friendly format compared to JSON, reducing token usage by 30-60%.

    Example:
        Basic usage::

            formatter = TOONFormatter()
            output = formatter.format({"name": "node-01", "status": "active"})
    """

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
        result: str = encode(data, self.options)  # type: ignore[arg-type]
        return result

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
        encoded: str = encode(data, self.options)  # type: ignore[arg-type]
        output += encoded
        return output

    def format_error(self, code: str, message: str, details: dict[str, Any] | None = None) -> str:
        """Format an error response.

        Args:
            code: Error code
            message: Error message
            details: Optional error details

        Returns:
            TOON-formatted error
        """
        error_obj: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if details:
            error_obj["details"] = details
        error_data: dict[str, Any] = {"error": error_obj}
        result: str = encode(error_data, self.options)  # type: ignore[arg-type]
        return result
