# PatraRekha

PatraRekha is an end-to-end document ingestion, processing, and vector search pipeline. It automatically pre-processes raw PDF documents using OCR, chunks them semantically, generates vector embeddings using the Gemini API, and uploads the results to a Pinecone vector database.

---

## 🏗️ Architecture

```
                    ┌────────────────────────┐
                    │      Input (PDF)       │
                    └───────────┬────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │     Stage 1: Document Preprocessing (OCR)    │
         │  • Converts PDF pages to high-resolution images
         │  • Extracts text & tables using PaddleOCR    │
         │  • Produces structured JSON & metadata        │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │          Stage 2: Semantic Chunking          │
         │  • Groups text blocks into semantic sections │
         │  • Splits sections into token-bounded chunks  │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │        Stage 3: Embedding Generator          │
         │  • Generates high-quality vector embeddings   │
         │    using the Gemini API                      │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │         Stage 4: Vector DB (Pinecone)        │
         │  • Upserts embeddings + metadata tags        │
         │  • Ready for high-speed semantic retrieval   │
         └──────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

* **`document preprocessing/`**: OCR extraction engine, table detection, metadata formatting, and PDF converters.
* **`AI pipeline/`**:
  * **`Chunking/`**: Semantic and token-based document segmenter.
  * **`embedding/`**: Gemini API interface for batch embedding generation.
  * **`vectorstore/`**: Pinecone database connector, index manager, and query system.
* **`ingestion/`**: Folder for input PDFs and output parsed JSON files.
* **`main.py`**: The unified entrypoint connecting preprocessing and the AI pipeline.
* **`requirements.txt`**: Consolidated dependencies for all backend and pipeline stages.

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- **Python**: version `3.10` or higher is recommended.
- **Poppler**: Required by `pdf2image` on Windows.
  - Download Poppler (e.g., from [poppler-windows](https://github.com/oschwartz10612/poppler-windows)).
  - Extract and place the binary directory under `D:\OCR\poppler-25.12.0\Library\bin` or update the path `POPPLER_PATH` in `document preprocessing/config.py`.

### 2. Installation
Create a virtual environment and install the combined dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows Powershell)
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Variables
Create a file named `.env` inside `AI pipeline/` (or copy/modify the existing one):

```env
GEMINI_API_KEY=your_gemini_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
```

---

## 🚀 Usage

You can run the full pipeline end-to-end on any PDF document using the root `main.py` entrypoint.

```bash
# Run on default sample PDF (ingestion/EJ1172284.pdf)
python main.py

# Run on a custom PDF file
python main.py "path/to/your/document.pdf"
```

### Flow Execution Outputs:
1. **Document Preprocessing (OCR)**: Runs PaddleOCR to extract text and tables. Saves a `.json` transcript in the same folder as the input PDF.
2. **Semantic Chunking**: Reads the `.json` and divides the document into semantic paragraphs/chunks.
3. **Embedding Generation**: Sends chunks in batches to Gemini's embedding model.
4. **Vector DB Upsert**: Connects to your Pinecone index and uploads the vector representations.
