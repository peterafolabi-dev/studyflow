import os
import re
from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFExtractionError(Exception):
    """Custom exception raised during PDF text extraction issues."""
    pass


class ScannedOrEmptyPDFError(PDFExtractionError):
    """Raised when the PDF has no readable digital text (scanned or empty)."""
    pass


def extract_and_chunk_pdf(file_path_or_file, max_chars=12000):
    """
    Extracts selectable text from a PDF file using pypdf.
    
    Handles:
    - Empty or scanned PDFs (raises ScannedOrEmptyPDFError)
    - File errors / encryption / corruption (raises PDFExtractionError)
    - Long documents (chunks text up to max_chars while preserving coherent structure)
    """
    try:
        reader = PdfReader(file_path_or_file)
    except PdfReadError as e:
        raise PDFExtractionError(f"Unable to read PDF file: {str(e)}")
    except Exception as e:
        raise PDFExtractionError(f"Could not open file: {str(e)}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise PDFExtractionError("This PDF is password-protected and cannot be read.")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ScannedOrEmptyPDFError("The uploaded PDF has no pages.")

    extracted_pages = []
    total_length = 0

    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        
        # Clean extra whitespace
        cleaned = re.sub(r'[ \t]+', ' ', page_text).strip()
        if cleaned:
            extracted_pages.append((i + 1, cleaned))
            total_length += len(cleaned)

    # Check if virtually no text was extracted (scanned or blank PDF)
    raw_combined = " ".join(text for _, text in extracted_pages)
    # Check alphanumeric characters count
    alnum_count = len(re.findall(r'[a-zA-Z0-9]', raw_combined))
    if alnum_count < 40:
        raise ScannedOrEmptyPDFError(
            "This PDF appears to be scanned or contains no extractable text. "
            "Please upload a document with selectable text or OCR."
        )

    # If document is within limit, return combined text with page hints
    if total_length <= max_chars:
        return "\n\n".join(f"[Page {pnum}]\n{text}" for pnum, text in extracted_pages)

    # If document is longer than max_chars, chunk intelligently:
    # Prioritize earlier pages and representative key sections
    budget_per_page = max(300, max_chars // min(total_pages, 10))
    selected_chunks = []
    accumulated = 0

    for pnum, text in extracted_pages:
        if accumulated >= max_chars:
            break
        # Take up to budget_per_page from this page
        remaining_budget = max_chars - accumulated
        slice_len = min(len(text), budget_per_page, remaining_budget)
        chunk = text[:slice_len].rsplit(' ', 1)[0] if slice_len < len(text) else text
        selected_chunks.append(f"[Page {pnum}]\n{chunk}")
        accumulated += len(chunk)

    combined = "\n\n".join(selected_chunks)
    if accumulated < total_length:
        combined += f"\n\n[... Note: Document has {total_pages} pages; first key sections analyzed ...]"
    return combined
