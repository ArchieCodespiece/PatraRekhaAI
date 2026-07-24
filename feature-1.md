# PatraRekha AI Pipeline

This repository contains the AI ingestion pipeline used by PatraRekha. The pipeline converts OCR-generated JSON documents into searchable vector embeddings stored in Pinecone, enabling efficient Retrieval-Augmented Generation (RAG).

---

# Pipeline Overview

```
PDF
 │
 ▼
OCR
 │
 ▼
Chunking
 │
 ▼
Embedding
 │
 ▼
Vector Store (Pinecone)
 │
 ▼
Retriever (Upcoming)
 │
 ▼
LLM Generator (Upcoming)
```

---

# Project Structure

```
AI pipeline/
│
├── Chunking/
├── embedding/
├── vectorstore/
├── Retriever/        (Upcoming)
└── Generator/        (Upcoming)
```

---

# 1. Chunking

The Chunking module converts OCR JSON into semantically meaningful chunks while preserving document hierarchy and metadata.

## Flow

```
OCR JSON
    │
    ▼
Document Model
    │
    ▼
Semantic Section Detection
    │
    ▼
Chunk Splitting
    │
    ▼
Metadata Attachment
    │
    ▼
Chunks
```

---

## Files

### `__init__.py`

Exports the public classes of the package.

---

### `models.py`

Contains all data models used throughout the chunking pipeline.

Includes:

- Document
- Page
- Table
- Section
- Chunk
- ChunkMetadata
- ProcessedDocument

These dataclasses act as the common language between all chunking components.

---

### `config.py`

Stores configurable parameters such as

- chunk size
- overlap
- tokenizer
- thresholds

Centralizes all chunking configuration.

---

### `semantic.py`

Builds semantic sections from OCR pages.

Responsibilities include

- Heading detection
- Section hierarchy
- Page tracking
- Table association

Output:

```
Document
      ↓
List[Section]
```

---

### `splitter1.py`

Performs semantic text splitting.

Responsibilities

- Token counting
- Recursive chunk splitting
- Paragraph preservation
- Table conversion to text

Produces plain text pieces.

---

### `splitter2.py`

Generates final Chunk objects.

Responsibilities

- Split sections into chunks
- Preserve tables
- Create ChunkMetadata
- Attach document metadata

Output:

```
List[Chunk]
```

---

### `postprocess.py`

Final cleanup stage.

Responsibilities

- Remove empty chunks
- Merge small chunks
- Normalize whitespace
- Final validation

---

### `chunking.py`

Main orchestration layer for chunk generation.

Pipeline:

```
Document
      ↓
Semantic Builder
      ↓
Section Splitter
      ↓
Post Processing
      ↓
Chunks
```

---

### `pipeline.py`

Public API of the Chunking module.

Responsibilities

- Load OCR JSON
- Convert JSON → Document
- Execute chunking pipeline

Example

```python
pipeline = ChunkPipeline()
chunks = pipeline.process("document.json")
```

---

### `test_semantic.py`

Standalone testing script for validating the chunking pipeline.

Useful for debugging

- section detection
- chunk generation
- metadata

---

### `requirements.txt`

Dependencies required only for the Chunking module.

---

# 2. Embedding

The Embedding module converts chunks into dense vector embeddings using Google's Gemini embedding model.

## Flow

```
Chunks
    │
    ▼
Text Extraction
    │
    ▼
Gemini Embedding API
    │
    ▼
Embedded Chunks
```

---

## Files

### `__init__.py`

Exports embedding classes.

---

### `config.py`

Contains

- Gemini API key
- Embedding model name
- Batch size

---

### `models.py`

Defines embedding-specific models.

Includes

- EmbeddedChunk
- EmbeddingResult

These wrap chunks together with their vector representations.

---

### `embedder.py`

Wrapper around Gemini Embedding API.

Responsibilities

- Embed single text
- Embed batches
- Error handling

---

### `pipeline.py`

High-level embedding pipeline.

Pipeline:

```
Chunks
      ↓
Extract Text
      ↓
Gemini
      ↓
EmbeddingResult
```

---

### `utils.py`

Utility/helper functions used by the embedding module.

Examples

- batching
- validation
- preprocessing

---

### `test_embedding.py`

Standalone embedding test.

Typical workflow

```
OCR JSON
      ↓
Chunking
      ↓
Embedding
      ↓
Print Embeddings
```

---

### `requirements.txt`

Dependencies for embedding module.

---

# 3. VectorStore

Stores embedded vectors in Pinecone for semantic retrieval.

## Flow

```
EmbeddingResult
      │
      ▼
Vector Formatting
      │
      ▼
Pinecone
```

---

## Files

### `__init__.py`

Exports vector store classes.

---

### `config.py`

Contains

- Pinecone API key
- Index name
- Cloud
- Region
- Distance metric
- Vector dimension

---

### `pinecone_store.py`

Low-level Pinecone wrapper.

Responsibilities

- Create index
- Upload vectors
- Query vectors
- Delete vectors
- Delete documents
- Describe index

Handles all Pinecone communication.

---

### `pipeline.py`

High-level vector storage pipeline.

Responsibilities

```
EmbeddingResult
      ↓
Format Metadata
      ↓
Upload
```

Provides a simplified interface for interacting with Pinecone.

---

### `requirements.txt`

Dependencies required for Pinecone integration.

---

# Upcoming Modules

## Retriever

Responsible for semantic search.

Pipeline

```
Question
      ↓
Embedding
      ↓
Pinecone Search
      ↓
Metadata Filtering
      ↓
(Optional Reranking)
      ↓
Retrieved Chunks
```

Responsibilities

- Query embedding
- Top-K retrieval
- Metadata filtering
- Score thresholding
- Context preparation

---

## Generator

Responsible for answer generation.

Pipeline

```
Question
      ↓
Retrieved Context
      ↓
Prompt Construction
      ↓
Gemini LLM
      ↓
Answer
```

Responsibilities

- Prompt engineering
- Citation handling
- Hallucination reduction
- Answer generation

---

# Design Principles

The project follows a modular architecture where each module has a single responsibility.

```
Chunking
    │
    ▼
Embedding
    │
    ▼
VectorStore
    │
    ▼
Retriever
    │
    ▼
Generator
```

Each module is independent and communicates through well-defined data models, making the pipeline easy to test, maintain, and extend.

---

# Current Status

| Module | Status |
|----------|--------|
| OCR | ✅ Complete |
| Chunking | ✅ Complete |
| Embedding | ✅ Complete |
| VectorStore | ✅ Complete |
| Retriever | 🚧 Next |
| Generator | ⏳ Planned |
| Chat Interface | ⏳ Planned |