# Integrated from robust_organizer.py for enhanced functionality
# At the top of the file, update the imports:
import gc  # For memory management  # noqa: F401
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

# Fix the database import to use relative import
from ..mem_db.db.database import create_connection, extract_entities  # noqa: E402

# Import dependencies with error handling
try:
    import pytesseract  # noqa: E402
    from PIL import Image  # noqa: E402

    pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD", "")
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
try:
    import fitz  # PyMuPDF for PDF handling  # noqa: E402

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
try:
    from bs4 import BeautifulSoup  # For HTML parsing  # noqa: E402

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class OllamaClient:
    def __init__(
        self,
        base_url="http://127.0.0.1:11434",
        generator_model="phi4-mini",
        timeout=240,
    ):
        self.base_url = base_url
        self.generator_model = generator_model
        self.timeout = timeout

    def classify_document(self, text, filename):
        text_sample = text[:2000]  # Limit text to avoid overwhelming the model  # noqa: F841
        prompt = """Analyze the document and classify it into ONE of the following categories: Legal_Motions, Legal_Contracts, Legal_Pleadings, Legal_Correspondence, Case_Law, Meeting_Minutes, Financial_Documents, Other_Documents.

Filename: {filename}
Content: {text_sample}

RESPONSE FORMAT:
Category: [EXACT_CATEGORY_NAME]
Confidence: [1-100]"""
        try:
            # Use subprocess to call Ollama, as it's set up in robust_organizer.py
            payload = {
                "model": self.generator_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            }
            result = subprocess.run(
                ["ollama", "run", self.generator_model, json.dumps(payload)],
                capture_output=True,
                text=True,
                shell=True,
            )
            responsetext = result.stdout.strip()  # noqa: F841
            category_match = re.search(r"Category:\s*(\w+)", response_text)  # noqa: F821
            confidence_match = re.search(r"Confidence:\s*(\d+)", response_text)  # noqa: F821
            category = category_match.group(1) if category_match else None
            confidence = int(confidence_match.group(1)) if confidence_match else 0
            return category, confidence
        except Exception as e:  # noqa: F841
            return None, 0

    def generate_llm_filename(self, text, original_name, category):
        text_sample = text[:2000]  # noqa: F841
        prompt = """Create a descriptive filename for the following document. Use underscores. Do not include the file extension.
Format: Category_Topic_Or_Parties_YYYY-MM-DD

Category: {category}
Original Filename: {original_name}
Content: {text_sample}

SUGGESTED FILENAME:"""
        try:
            payload = {
                "model": self.generator_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            }
            result = subprocess.run(
                ["ollama", "run", self.generator_model, json.dumps(payload)],
                capture_output=True,
                text=True,
                shell=True,
            )
            suggested_name = result.stdout.strip()
            extension = Path(original_name).suffix
            clean_name = re.sub(r"[^\w\-_.]", "_", suggested_name).strip("_")
            final_name = (
                (clean_name[:80] + extension)
                if len(clean_name) <= 80
                else (clean_name[:77] + "..." + extension)
            )
            return final_name
        except Exception as e:  # noqa: F841
            return None


def extract_text(file_path):  # noqa: C901
    extension = Path(file_path).suffix.lower()
    if extension in [".md", ".txt"]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception as e:
            return f"Text extraction failed for TXT file: {str(e)}"
    elif extension == ".pd":
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(file_path)  # type: ignore
                text = ""
                for page in doc:
                    text += page.get_text("text")  # type: ignore  # Corrected to use "text" method
                doc.close()
                return text.strip()
            except Exception as e:
                return f"Text extraction failed for PDF file with PyMuPDF: {str(e)}"
        else:
            return "PyMuPDF not installed. PDF extraction not available."
    elif extension in [".jpg", ".png"]:
        if OCR_AVAILABLE:
            try:
                img = Image.open(file_path)  # type: ignore
                return pytesseract.image_to_string(img).strip()  # type: ignore
            except Exception as e:
                return f"Text extraction failed for image file: {str(e)}"
        else:
            return "OCR not available. Image extraction requires pytesseract and Tesseract OCR."
    elif extension == ".html":
        if BS4_AVAILABLE:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f, "html.parser")  # type: ignore
                    return soup.get_text().strip()
            except Exception as e:
                return f"Text extraction failed for HTML file: {str(e)}"
        else:
            return "BeautifulSoup not installed. HTML extraction not available."
    else:
        return "Unsupported file type"


def classify_document(file_path):
    text_content = extract_text(file_path)
    if (
        "failed" in text_content.lower()
        or "unsupported" in text_content.lower()
        or "not installed" in text_content.lower()
    ):
        return text_content  # Return extraction error if it occurred
    ollama_client = OllamaClient()
    category, confidence = ollama_client.classify_document(text_content, file_path)
    if category:
        filename_suggested = ollama_client.generate_llm_filename(
            text_content, Path(file_path).name, category
        )
        if filename_suggested:
            suggested_filename = filename_suggested
        else:
            suggested_filename = None
        # Update database connection to use the imported function
        conn = (
            create_connection()
        )  # Remove the parameter as it's handled in the function
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO classifications (filename, category, confidence, suggested_filename) VALUES (?, ?, ?, ?)",
                (Path(file_path).name, category, confidence, suggested_filename),
            )
            # Extract and save entities
            entities = extract_entities(text_content)
            for entity_type, entity_values in entities.items():
                for value in entity_values:
                    cursor.execute(
                        "INSERT INTO entities (classification_id, entity_type, entity_value) VALUES ((SELECT last_insert_rowid()), ?, ?)",
                        (entity_type, value),
                    )
            conn.commit()
            conn.close()
            # Return with entities if needed
            return f"Category: {category}, Confidence: {confidence}%, Suggested Filename: {suggested_filename or 'None'}, Entities stored in database"
        else:
            return f"Category: {category}, Confidence: {confidence}%, Suggested Filename: {suggested_filename or 'None'}, Database connection failed"
    else:
        return "Classification failed or no category determined."
