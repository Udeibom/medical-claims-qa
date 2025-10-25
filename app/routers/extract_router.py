from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException, status

# Service imports implementing OCR, parsing, and storage logic
from app.services.ocr_service import extract_text_bytes
from app.services.extraction_service import parse_claim
from app.services.storage_service import save_parsed

# Pydantic response schema for standardized API output
from app.schemas import ExtractResponse

# Router dedicated to document extraction flow
router = APIRouter()


@router.post("/", response_model=ExtractResponse, status_code=status.HTTP_201_CREATED)
async def extract(file: UploadFile = File(...)):
    """
    Accepts an uploaded file (PDF or image), extracts readable text through OCR,
    converts the text into structured claim data, stores that structured data,
    and returns a unique document identifier alongside parsed content.
    """

    # Create a unique identifier for linking subsequent QA requests to this document
    document_id = str(uuid4())

    # Read the uploaded file as raw binary content in a safe asynchronous manner
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed reading uploaded file: {e}",
        )

    # Validate content presence to prevent empty file ingestion
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Perform OCR to transform the binary content into a normalized text payload
    try:
        ocr_text = extract_text_bytes(content, filename=(file.filename or "upload"))
    except HTTPException:
        # Explicitly propagate OCR-related HTTP errors to the client unchanged
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR failed: {e}",
        )

    # Treat cases where OCR cannot find usable text as a user error
    if not ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text could be extracted from the uploaded file.",
        )

    # Convert the textual claim data into a structured entity model suitable for QA
    try:
        parsed = parse_claim(ocr_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {e}",
        )

    # Store the parsed document in memory for retrieval during QA queries
    try:
        save_parsed(document_id, parsed, persist=False)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save parsed document.",
        )

    # Respond with the identifier the client will use in subsequent question requests
    return {"document_id": document_id, "parsed": parsed}
