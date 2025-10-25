from fastapi import FastAPI
from app.routers import extract_router, ask_router

app = FastAPI(
    title="Medical Claims Extraction and QA Service",
    version="1.0.0",
    description="A microservice that extracts structured data from claim documents and answers questions about them.",
)

# include routers
app.include_router(extract_router.router, prefix="/extract", tags=["extract"])
app.include_router(ask_router.router, prefix="/ask", tags=["ask"])


@app.get("/", tags=["root"])
async def root():
    """
    Quick health-check endpoint to confirm the service is running.
    """
    return {"message": "Claims extraction service is live."}
