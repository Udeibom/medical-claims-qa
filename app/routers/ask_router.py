from fastapi import APIRouter, HTTPException, status
from app.services.storage_service import get_parsed
from app.services.qa_service import answer_question

# API schemas define request and response payloads for the endpoint
from app.schemas import AskRequest, AskResponse

# Initialize router specifically for the question-answer functionality
router = APIRouter()


@router.post("/", response_model=AskResponse)
async def ask(req: AskRequest):
    """
    Handles question-answering requests for a previously extracted document.

    Flow:
    1. Retrieve the parsed document from storage using the provided document_id.
    2. Pass the parsed data with the user’s question to the QA inference service.
    3. Return the generated answer in a normalized response model.
    """

    # Retrieve previously extracted structured document data by ID
    parsed = get_parsed(req.document_id)

    # If the document does not exist in storage, return 404 to the client
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    # Invoke the QA service to compute the best answer from the structured data
    try:
        answer = answer_question(parsed, req.question)
    except Exception:
        # Handle any inference or runtime failures with a 500 internal server error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to answer question",
        )

    # Send back a clean response formatted via AskResponse model
    return {"answer": answer}
