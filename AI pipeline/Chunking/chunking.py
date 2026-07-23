from parser import load_json
from semantic import build_sections
from splitter import split_chunks
from metadata import enrich_chunks

chunks = chunk_document("KMRL.json")