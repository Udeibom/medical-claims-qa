from fastapi.testclient import TestClient
from app.main import app
from app.services.storage_service import save_parsed

client = TestClient(app)


def test_ask_endpoint_returns_answer(monkeypatch):
    """
    Verifies that a valid question against a stored document returns an answer.

    The test injects a parsed claim record directly into the store, then
    replaces the real QA function with a simple lambda to keep the result
    predictable.
    """
    document_id = "abc123"
    parsed_doc = {
        "patient": {"name": "Jane Doe", "age": 34},
        "diagnoses": ["Malaria"],
        "medications": [{"name": "Paracetamol", "dosage": "500mg", "quantity": "10 tablets"}],
        "procedures": ["Malaria test"],
        "admission": {
            "was_admitted": True,
            "admission_date": "2023-06-10",
            "discharge_date": "2023-06-12",
        },
        "total_amount": "₦15,000",
    }

    # preload the extracted data we expect
    save_parsed(document_id, parsed_doc)

    # mock QA evaluation to isolate service behavior from the LLM backend
    monkeypatch.setattr(
        "app.services.qa_service.answer_question",
        lambda d, q: "10 tablets"
    )

    payload = {
        "document_id": document_id,
        "question": "How many tablets of paracetamol were prescribed?"
    }
    response = client.post("/ask/", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "10 tablets"


def test_ask_returns_404_for_unknown_doc():
    """
    Requests against a missing document should return a 404 response.
    """
    payload = {"document_id": "no_such_id", "question": "Any?"}
    response = client.post("/ask/", json=payload)
    assert response.status_code == 404
