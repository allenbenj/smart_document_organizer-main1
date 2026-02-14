import tempfile
import os
import logging
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile

logger = logging.getLogger(__name__)

class SimpleDocumentProcessor:
    """Simplified document processor for FastAPI backend integration"""

    def __init__(self):
        self.supported_extensions = {
            ".pdf",
            ".docx",
            ".doc",
            ".txt",
            ".html",
            ".htm",
            ".rtf",
            ".md",
            ".xlsx",
            ".xls",
            ".csv",
            ".pptx",
            ".ppt",
            ".png",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
            ".bmp",
        }

    async def process(self, file: UploadFile) -> dict:
        """Process a document file and extract content and metadata."""
        tmp_file_path = None
        try:
            filename = file.filename if file.filename is not None else "tempfile"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(filename).suffix
            ) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
                file_size = len(content)
                file_extension = Path(file.filename or "").suffix.lower()
                if file_extension not in self.supported_extensions:
                    raise Exception(f"Unsupported file type: {file_extension}")
                
                # Reset file cursor for future reads if needed, though here we used content bytes
                await file.seek(0)
                
                extracted_content = await self._extract_content(
                    tmp_file_path, file_extension, content
                )
                category = self._determine_category(file_extension, extracted_content)
                return {
                    "success": True,
                    "filename": file.filename,
                    "file_size": file_size,
                    "file_type": file_extension,
                    "mime_type": file.content_type,
                    "content": extracted_content,
                    "category": category,
                    "processing_method": "simple_extraction",
                    "confidence": 0.8,
                    "processed_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            return {
                "success": False,
                "filename": file.filename,
                "error": str(e),
                "processing_method": "failed",
                "confidence": 0.0,
            }
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    async def _extract_content(
        self, file_path: str, file_extension: str, content_bytes: bytes
    ) -> str:
        """Extract text content from file based on type"""
        try:
            if file_extension in [".txt", ".md", ".html", ".htm"]:
                # Try different encodings for text files
                for encoding in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        return content_bytes.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return content_bytes.decode("utf-8", errors="ignore")

            elif file_extension == ".pdf":
                return await self._extract_pdf_content(file_path)

            elif file_extension in [".docx", ".doc"]:
                return await self._extract_docx_content(file_path)

            elif file_extension in [".xlsx", ".xls", ".csv"]:
                return await self._extract_spreadsheet_content(
                    file_path, file_extension
                )

            else:
                return f"Binary file: {Path(file_path).name} (content extraction not supported)"

        except Exception as e:
            logger.warning(f"Content extraction failed for {file_path}: {e}")
            return f"File: {Path(file_path).name} (content extraction failed)"

    async def _extract_pdf_content(self, file_path: str) -> str:
        """Extract content from PDF file"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            content = []

            for page_num in range(doc.page_count):
                page = doc[page_num]
                # Use get_text() without parameters or with specific format
                content.append(
                    f"\n--- Page {page_num + 1} ---\n{page.get_text('text')}"
                )
            doc.close()
            return "\n".join(content).strip()
        except ImportError:
            return f"PDF file: {Path(file_path).name} (PyMuPDF not available for text extraction)"
        except Exception as e:
            return f"PDF file: {Path(file_path).name} (extraction failed: {e})"

    async def _extract_docx_content(self, file_path: str) -> str:
        """Extract content from DOCX file"""
        try:
            from docx import Document

            doc = Document(file_path)
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
            return content.strip()
        except ImportError:
            return f"DOCX file: {Path(file_path).name} (python-docx not available for text extraction)"
        except Exception as e:
            return f"DOCX file: {Path(file_path).name} (extraction failed: {e})"

    async def _extract_spreadsheet_content(
        self, file_path: str, file_extension: str
    ) -> str:
        """Extract content from spreadsheet files"""
        try:
            import pandas as pd

            if file_extension == ".csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            content = f"Spreadsheet with {len(df)} rows and {len(df.columns)} columns\n"
            content += f"Columns: {', '.join(df.columns)}\n\n"
            content += df.head(10).to_string()  # First 10 rows
            return content
        except ImportError:
            return f"Spreadsheet file: {Path(file_path).name} (pandas not available for data extraction)"
        except Exception as e:
            return f"Spreadsheet file: {Path(file_path).name} (extraction failed: {e})"

    def _determine_category(self, file_extension: str, content: str) -> str:
        """Determine document category based on file type and content"""
        # Basic categorization logic
        if file_extension in [".pdf", ".docx", ".doc", ".txt", ".md"]:
            if any(
                keyword in content.lower()
                for keyword in ["contract", "agreement", "legal", "terms"]
            ):
                return "legal"
            elif any(
                keyword in content.lower()
                for keyword in ["report", "analysis", "summary"]
            ):
                return "report"
            else:
                return "document"
        elif file_extension in [".xlsx", ".xls", ".csv"]:
            return "spreadsheet"
        elif file_extension in [".pptx", ".ppt"]:
            return "presentation"
        elif file_extension in [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"]:
            return "image"
        else:
            return "other"
