"""FastAPI entrypoint for document APIs."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from db.files import get_document_file_url, list_documents


app = FastAPI(title="PatraRekha API")


@app.get("/get-documents")
def get_documents():
    return {"documents": list_documents()}


@app.get("/get-documents/{file_id}")
def get_document(file_id: str):
    try:
        file_url = get_document_file_url(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document id") from exc

    if not file_url:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"file_id": file_id, "file_url": file_url}
