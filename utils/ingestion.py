import logging
import os  # noqa: E402
import sys  # noqa: E402
from functools import wraps  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Dict, Optional, Union  # noqa: E402

import docx  # For DOCX text extraction; install via pip if needed  # noqa: E402
import pdfplumber  # Installed via pip for PDF handling  # noqa: E402

from .classification import extract_text  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ingestion.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DocumentIngestionError(Exception):
    """Base class for document ingestion errors"""


class InvalidFilePathError(DocumentIngestionError):
    """Raised when file path is invalid"""


class UnsupportedFileTypeError(DocumentIngestionError):
    """Raised when file type is unsupported"""


class EmptyDocumentError(DocumentIngestionError):
    """Raised when no text content is extracted"""


# class TextProcessingError(DocumentIngestionError):
#     """Raised when text processing fails"""
#     pass


def log_execution_time(func: Callable) -> Callable:
    """Decorator to log execution time of functions"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        import time  # noqa: E402

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug(
            f"Function {func.__name__} executed in {end_time - start_time:.4f} seconds"
        )
        return result

    return wrapper


def validate_file_path(file_path: str) -> str:
    """
    Validate and sanitize file path.

    Args:
        file_path: Path to validate

    Returns:
        Absolute path if valid

    Raises:
        InvalidFilePathError: If path is invalid
    """
    if not file_path:
        raise InvalidFilePathError("File path cannot be empty")

    try:
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(os.path.abspath(os.getcwd())):
            raise InvalidFilePathError(
                "Invalid file path: Attempted directory traversal"
            )

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Document not found at {abs_path}")

        return abs_path
    except Exception as e:
        raise InvalidFilePathError(f"Invalid file path: {str(e)}")


@log_execution_time
def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text content

    Raises:
        DocumentIngestionError: If extraction fails
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            return "".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        logger.error(f"PDF extraction error for {file_path}: {str(e)}")
        raise DocumentIngestionError(f"Failed to extract text from PDF: {str(e)}")


@log_execution_time
def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from DOCX file.

    Args:
        file_path: Path to DOCX file

    Returns:
        Extracted text content

    Raises:
        DocumentIngestionError: If extraction fails
    """
    try:
        doc = docx.Document(file_path)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    except Exception as e:
        logger.error(f"DOCX extraction error for {file_path}: {str(e)}")
        raise DocumentIngestionError(f"Failed to extract text from DOCX: {str(e)}")


@log_execution_time
def ingest_document(file_path):
    """
    Process and ingest a document into the system.

    Args:
        file_path (str): Path to the document to ingest

    Returns:
        str: Status message indicating success or failure
    """
    try:
        # Validate file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Document not found at {file_path}")

        # Extract text content using the existing extract_text function
        text_content = extract_text(file_path)

        if not text_content or not text_content.strip():
            raise EmptyDocumentError("No text extracted from document")

        if "failed" in text_content.lower() or "not available" in text_content.lower():
            raise DocumentIngestionError(text_content)

        # Return the extracted text for further processing
        return text_content

    except Exception as e:
        logger.error(f"Ingestion failed for {file_path}: {str(e)}")
        raise DocumentIngestionError(f"Ingestion failed: {str(e)}")


def create_text_processor(
    lowercase: bool = True,
    remove_special_chars: bool = True,
    custom_filters: Optional[Dict[str, Callable]] = None,
) -> Callable[[str], str]:
    """
    Create a text processor function with specified options.

    Args:
        lowercase: Convert text to lowercase (default: True)
        remove_special_chars: Remove special characters (default: True)
        custom_filters: Dictionary of custom filters to apply

    Returns:
        Text processor function
    """
    if custom_filters is not None and not isinstance(custom_filters, dict):
        raise ValueError("custom_filters must be a dictionary or None")

    def processor(text: str) -> str:
        """
        Process text with configured options.

        Args:
            text: Input text to process

        Returns:
            Processed text
        """
        # Remove extra whitespace
        cleaned_text = " ".join(text.split())

        if remove_special_chars:
            # Keep only alphanumeric characters and whitespace
            cleaned_text = "".join(
                char for char in cleaned_text if char.isalnum() or char.isspace()
            )

        if lowercase:
            cleaned_text = cleaned_text.lower()

        # Apply custom filters if provided
        if custom_filters:
            for filter_name, filter_func in custom_filters.items():
                try:
                    cleaned_text = filter_func(cleaned_text)
                except Exception as e:
                    logger.warning(f"Custom filter '{filter_name}' failed: {str(e)}")
                    continue

        return cleaned_text

    return processor


@log_execution_time
def preprocess_text(
    text: str,
    lowercase: bool = True,
    remove_special_chars: bool = True,
    custom_filters: Optional[Dict[str, Callable]] = None,
) -> str:
    """
    Preprocess text with configurable options.

    Args:
        text: Input text to preprocess
        lowercase: Convert text to lowercase (default: True)
        remove_special_chars: Remove special characters (default: True)
        custom_filters: Dictionary of custom filters to apply

    Returns:
        Preprocessed text

    Raises:
        ValueError: If custom filters are invalid
    """
    processor = create_text_processor(lowercase, remove_special_chars, custom_filters)
    return processor(text)


def process_document(
    file_path: str, preprocessing_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Union[str, int]]:
    """
    Process a document with optional preprocessing.

    Args:
        file_path: Path to the document file
        preprocessing_options: Dictionary of preprocessing options

    Returns:
        Dictionary containing:
        - extracted_text: Extracted text content
        - processed_text: Processed text content
        - original_length: Length of original text
        - processed_length: Length of processed text

    Raises:
        DocumentIngestionError: For any processing errors
    """
    if preprocessing_options is None:
        preprocessing_options = {}

    try:
        extracted_text = ingest_document(file_path)
        processed_text = preprocess_text(extracted_text, **preprocessing_options)

        return {
            "extracted_text": extracted_text,
            "processed_text": processed_text,
            "original_length": len(extracted_text),
            "processed_length": len(processed_text),
        }
    except Exception as e:
        logger.error(f"Document processing failed for {file_path}: {str(e)}")
        raise DocumentIngestionError(f"Failed to process document: {str(e)}")


def main(file_path: Optional[str] = None) -> None:
    """
    Main function for command-line usage.

    Args:
        file_path: Optional path to document file
    """
    if file_path is None:
        if len(sys.argv) != 2:
            print("Usage: python ingestion.py <file_path>")
            sys.exit(1)
        file_path = sys.argv[1]

    try:
        result = process_document(file_path)
        print("Document ingested and preprocessed successfully.")
        print(f"Extracted text length: {result['original_length']} characters")
        print(f"Processed text length: {result['processed_length']} characters")
        print(f"Sample of processed text: {result['processed_text'][:200]}...")
    except Exception as e:
        print(f"Error during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
