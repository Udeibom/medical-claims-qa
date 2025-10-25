import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_extract_endpoint_returns_valid_response(monkeypatch):
    """
    Validates that the /extract endpoint creates a parsed record and returns it
    together with a newly generated document_id.

    The OCR and parsing steps are mocked to keep the test isolated from
    external tooling such as Tesseract or PDF processing.
    """
    # Mocked OCR text and the expected parsed result structure
    fake_text = "Patient Name: Jane Doe\nAge: 34\nDiagnosis: Malaria"
    fake_parsed = {
        "patient": {"name": "Jane Doe", "age": 34},
        "diagnoses": ["Malaria"],
        "medications": [],
        "procedures": [],
        "admission": {"was_admitted": False, "admission_date": None, "discharge_date": None},
        "total_amount": "₦15,000",
    }

    # Inject deterministic behavior for OCR and parsing logic
    monkeypatch.setattr("app.routers.extract_router.extract_text", lambda f: fake_text)
    monkeypatch.setattr("app.routers.extract_router.parse_claim", lambda t: fake_parsed)

    # Construct an in-memory PDF upload to simulate client submission
    file_data = io.BytesIO(b"dummy file content")
    response = client.post(
        "/extract/",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )

    assert response.status_code == 201

    data = response.json()

    # Response is expected to contain both ID and structured data
    assert "document_id" in data
    assert "parsed" in data

    # Basic checks confirming that parsing fits expected shape
    assert data["parsed"]["patient"]["name"] == "Jane Doe"
    assert isinstance(data["parsed"]["diagnoses"], list)
