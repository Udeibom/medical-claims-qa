"""
OCR-based text extraction service.

This module accepts uploaded files as byte streams or file objects.
It supports native PDF text extraction with pdfplumber and falls back
to image-based OCR with Tesseract for scanned PDFs or raster formats.
Noise filtering and minimal normalization are applied to return a
clean UTF-8 text string suitable for downstream parsing.
"""

import io
import logging
import tempfile
import os
from typing import Optional
import re

# OCR toolchain imports with graceful degradation
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

# Fallback text normalizer if shared utility unavailable
try:
    from app.utils.text_cleaner import clean_text
except Exception:
    def clean_text(raw: str) -> str:
        if raw is None:
            return ""
        # Strip blank lines and normalize newline usage
        text = raw.replace("\r", "\n")
        text = "\n".join([ln.strip() for ln in text.splitlines() if ln.strip()])
        return text


logger = logging.getLogger(__name__)


def _write_bytes_to_temp(content: bytes, filename: str = "upload") -> str:
    """
    Persist in-memory bytes to a temporary file on disk.

    This supports OCR libraries that require filesystem input.
    Returns the absolute path to the generated temp file.
    """
    suffix = ""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(content)
        tmp.flush()
    finally:
        tmp.close()
    return tmp.name


def extract_text_bytes(content: bytes, filename: str = "upload") -> str:
    """
    Perform OCR text extraction from raw bytes.

    Dispatch logic selects the correct extractor based on file type.
    A final post-processing stage removes boilerplate and formatting noise.
    """
    temp_path = None
    try:
        temp_path = _write_bytes_to_temp(content, filename=filename)
        lower = (filename or "").lower()
        text: Optional[str] = None

        try:
            # Primary dispatch by file extension
            if lower.endswith(".pdf"):
                text = _process_pdf(temp_path)
            elif lower.endswith((".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif")):
                text = _process_image(temp_path)
            else:
                # Attempt PDF extraction by default if ambiguous
                if pdfplumber is not None:
                    try:
                        text = _process_pdf(temp_path)
                    except Exception:
                        text = _process_image(temp_path)
                else:
                    text = _process_image(temp_path)
        except Exception as e:
            logger.exception("Error during file processing: %s", e)
            raise

        # Apply final cleanup and OCR artifact removal
        cleaned = clean_text(_remove_footer_noise(text or ""))
        return cleaned
    finally:
        # Best-effort deletion of temporary resources
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                logger.debug("Failed to remove temp file %s", temp_path)


def extract_text(upload_file) -> str:
    """
    Wrapper for FastAPI upload objects.

    Reads bytes safely from the file-like object and forwards to the
    main extraction logic.
    """
    try:
        try:
            upload_file.file.seek(0)
        except Exception:
            pass
        content = upload_file.file.read()
        filename = getattr(upload_file, "filename", "upload")
    except Exception as e:
        raise RuntimeError(f"Failed to read uploaded file object: {e}")

    return extract_text_bytes(content, filename=filename)


def _process_pdf(file_path: str) -> str:
    """
    Extract text directly from a PDF if possible.

    Pages lacking extractable text are processed using Tesseract OCR
    as a fallback for scanned or image-based PDFs.
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required for PDF processing but is not installed.")

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            # OCR fallback for rasterized content
            if not page_text.strip():
                try:
                    pil_img = page.to_image(resolution=200).original
                    page_text = pytesseract.image_to_string(
                        pil_img,
                        config="--psm 6 --oem 3",
                        lang="eng"
                    )
                except Exception:
                    page_text = ""

            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts)


def _process_image(file_path: str) -> str:
    """
    OCR processing pipeline for standalone images.

    Converts to grayscale, improves contrast, and applies sharpening
    to enhance Tesseract recognition accuracy.
    """
    if Image is None or pytesseract is None:
        raise RuntimeError("PIL and pytesseract are required for image OCR but are not installed.")

    with Image.open(file_path) as img:
        img = img.convert("L")
        img = ImageOps.invert(img)
        img = img.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(
            img,
            config="--psm 6 --oem 3",
            lang="eng"
        )

    return text


def _remove_footer_noise(text: str) -> str:
    """
    Remove recurring boilerplate such as footers found on generated PDFs.

    This step filters out predictable non-semantic patterns that 
    degrade downstream entity extraction.
    """
    if not text:
        return ""
    noise_patterns = [
        r"POWERED BY SMART APPLICATIONS.*",
        r"PREPARED BY.*",
        r"PARTNER NAME.*",
        r"NET VALUE.*",
        r"PAGE\s*\d+",
    ]
    for pat in noise_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    return text
