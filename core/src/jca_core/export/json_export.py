"""Export the whole analysis as JSON, and read it back."""

from pydantic import ValidationError

from jca_core.schema.records import AnalysisDocument

JSON_INDENT = 2


def analysis_to_json(document: AnalysisDocument) -> str:
    """Return the document as JSON: times, beats, both model outputs and the user edits."""
    return document.model_dump_json(indent=JSON_INDENT)


def analysis_from_json(text: str) -> AnalysisDocument:
    """Parse and validate an exported document. Raises ValueError for bad input."""
    try:
        return AnalysisDocument.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(f"Invalid analysis JSON: {error.error_count()} problem(s)") from error
