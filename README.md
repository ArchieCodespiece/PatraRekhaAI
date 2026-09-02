# PatraRekhaAI

PatraRekhaAI is an end-to-end document intelligence platform that ingests, processes, and semantic searches through documents using AI. It features a modern Next.js frontend with multilingual support for 13 Indian languages, a FastAPI backend, and a sophisticated AI pipeline for OCR, chunking, embedding, and vector search.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                             │
│  • Dashboard with document management                                       │
│  • Multi-document PDF chat with AI                                          │
│  • Calendar with deadline extraction                                        │
│  • 13 Indian languages + RTL support                                        │
│  • Dark mode with flash prevention                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Backend (FastAPI)                                   │
│  • JWT authentication via Supabase                                          │
│  • Rate limiting (slowapi)                                                  │
│  • CORS protection                                                          │
│  • Request validation (Pydantic)                                            │
│  • Document CRUD + semantic search                                          │
│  • Chat with streaming (SSE)                                                │
│  • Gmail integration (OAuth + heartbeat)                                    │
│  • Calendar event management                                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI Pipeline (Python)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 1: Document Preprocessing (OCR)                                │   │
│  │  • PaddleOCR for text extraction                                     │   │
│  │  • Table detection and reconstruction                                │   │
│  │  • Multi-format support (PDF, DOCX, PPTX, XLSX)                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 2: Semantic Chunking                                           │   │
│  │  • Groups text into semantic sections                                │   │
│  │  • Token-bounded chunks for optimal embedding                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 3: Embedding Generator                                         │   │
│  │  • Gemini API for high-quality vector embeddings                     │   │
│  │  • File-based caching for cost optimization                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 4: Vector DB (Pinecone)                                        │   │
│  │  • Upserts embeddings + metadata                                     │   │
│  │  • High-speed semantic retrieval                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Database (Supabase)                                │
│  • PostgreSQL for structured data                                           │
│  • Supabase Storage for file storage                                        │
│  • Realtime subscriptions                                                   │
│  • Row-level security                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### Document Intelligence
- **OCR Processing**: Extract text from scanned PDFs using PaddleOCR
- **Semantic Chunking**: Intelligent document segmentation
- **Vector Search**: Find relevant content across documents
- **Multi-format Support**: PDF, DOCX, PPTX, XLSX, images

### AI-Powered Chat
- **Multi-document Chat**: Ask questions across multiple documents
- **Streaming Responses**: Real-time SSE streaming for fast feedback
- **Citation Tracking**: Source references for AI responses
- **Markdown Rendering**: Rich formatting in responses

### Multilingual Support (13 Languages)
- English, Hindi, Bengali, Tamil, Telugu, Marathi
- Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu
- **RTL Support**: Full right-to-left layout for Urdu
- **Script Detection**: Automatic language and script identification
- **Romanized Query Normalization**: Hinglish/Benglish/Tanglish support

### Calendar & Deadlines
- **Automatic Deadline Extraction**: Extract dates from documents
- **Priority Classification**: High/Medium/Low priority events
- **Visual Calendar**: Interactive date picker with event indicators
- **Workload Analytics**: Weekly workload visualization

### Gmail Integration
- **OAuth Authentication**: Secure Gmail connection
- **Email Ingestion**: Auto-import document attachments
- **Heartbeat Monitoring**: Real-time connection status
- **Activity Listeners**: Browser event integration

### User Experience
- **Dark Mode**: System-preference aware with flash prevention
- **Responsive Design**: Mobile-friendly sidebar and layouts
- **Batch Operations**: Multi-select and bulk delete
- **Keyboard Shortcuts**: Ctrl+K for search focus
- **Error Boundaries**: Graceful error handling

---

## 📁 Repository Structure

```
PatraRekhaAI/
├── backend/                    # FastAPI backend
│   ├── api/                    # API routers and endpoints
│   │   ├── main.py            # App factory, middleware
│   │   ├── documents.py       # Document CRUD + search
│   │   ├── chat.py            # Chat + streaming
│   │   ├── calendar.py        # Calendar events
│   │   ├── gmail.py           # Gmail integration
│   │   └── conversations.py   # Conversation management
│   ├── db/                     # Database access layer
│   │   ├── supabase_client.py # Supabase client init
│   │   ├── files.py           # File storage operations
│   │   └── document_metadata.py # Document metadata
│   ├── services/               # Business logic
│   │   ├── language_detection.py # Unicode-based detection
│   │   └── romanized_normalizer.py # Hinglish normalization
│   ├── webhooks/               # Webhook handling
│   └── tests/                  # Unit tests
│
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/               # App Router pages
│   │   │   ├── (dashboard)/   # Dashboard routes
│   │   │   └── auth/          # Authentication
│   │   ├── components/        # React components
│   │   │   ├── documents.jsx  # Document management
│   │   │   ├── chatpdf.jsx    # PDF chat
│   │   │   ├── calendar.jsx   # Calendar view
│   │   │   └── sidebar.jsx    # Navigation
│   │   └── lib/               # Utilities
│   │       ├── i18n/          # Internationalization
│   │       └── supabaseAuth.js # Auth helpers
│   └── package.json
│
├── AI pipeline/                # Python AI pipeline
│   ├── Chunking/              # Semantic chunking
│   ├── embedding/             # Gemini embeddings
│   ├── vectorstore/           # Pinecone integration
│   ├── retrieval/             # Query processing
│   └── summarization-deadline/ # Deadline extraction
│
├── document_preprocessing/     # OCR and document processing
│   ├── ocr_engine.py          # PaddleOCR wrapper
│   ├── pdf_processor.py       # PDF pipeline
│   └── converter.py           # Multi-format converter
│
└── graphify-out/               # Knowledge graph output
```

---

## 🛠️ Setup & Installation

### Prerequisites

- **Python**: 3.10+
- **Node.js**: 18+
- **Poppler**: Required for PDF processing on Windows
  - Download from [poppler-windows](https://github.com/oschwartz10612/poppler-windows)
  - Extract to `D:\OCR\poppler-25.12.0\Library\bin` or update `POPPLER_PATH` in `document_preprocessing/config.py`

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r ../requirements.txt
```

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install
```

### 3. Environment Variables

#### Backend (`backend/.env`)

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# AI Services
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_index_name

# Security
WEBHOOK_SECRET=your_webhook_secret
GMAIL_OAUTH_STATE_SECRET=your_oauth_secret

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Rate Limiting
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_CHAT=20/minute
RATE_LIMIT_UPLOAD=10/minute
```

#### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
```

---

## 🚀 Running the Application

### Start Backend

```bash
cd backend
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

### Start Frontend

```bash
cd frontend
npm run dev
```

The application will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

---

## 📡 API Endpoints

### Documents
- `GET /get-documents` - List user documents
- `POST /upload-document` - Upload new document
- `DELETE /delete-document/{file_id}` - Delete document
- `POST /documents/{file_id}/reprocess` - Re-process document
- `POST /semantic-document-search` - Semantic search

### Chat
- `POST /chat` - Chat with documents
- `POST /chat/stream` - Streaming chat (SSE)

### Calendar
- `GET /calendar-events` - Get calendar events

### Gmail
- `GET /gmail/connect/start` - Start Gmail OAuth
- `GET /gmail/connect/callback` - OAuth callback
- `POST /gmail/connect/heartbeat` - Connection heartbeat
- `GET /gmail/connect/status` - Connection status

### Conversations
- `GET /conversations` - List conversations
- `POST /conversations` - Create conversation
- `DELETE /conversations/{id}` - Delete conversation

---

## 🔒 Security Features

- **JWT Authentication**: Supabase-issued tokens
- **CORS Protection**: Configurable allowed origins
- **Rate Limiting**: Per-endpoint rate limits
- **Request Validation**: Pydantic models with constraints
- **Webhook Authentication**: HMAC-signed webhook secrets
- **Path Traversal Prevention**: Sanitized file storage paths
- **Input Sanitization**: File type and size validation

---

## 🧪 Testing

```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend lint
cd frontend
npm run lint
```

---

## 📊 Knowledge Graph

The project includes a knowledge graph generated by graphify:

```bash
# Query the graph
graphify query "How does the chat system work?"

# Find relationships
graphify path "chat.py" "documents.py"

# Explain a concept
graphify explain "vector search"

# Update the graph after code changes
graphify update .
```

---

## 🌐 Multilingual Support

### Supported Languages
| Language | Code | Script |
|----------|------|--------|
| English | en | Latin |
| Hindi | hi | Devanagari |
| Bengali | bn | Bengali |
| Tamil | ta | Tamil |
| Telugu | te | Telugu |
| Marathi | mr | Devanagari |
| Gujarati | gu | Gujarati |
| Kannada | kn | Kannada |
| Malayalam | ml | Malayalam |
| Punjabi | pa | Gurmukhi |
| Odia | or | Odia |
| Assamese | as | Bengali |
| Urdu | ur | Arabic (RTL) |

### Usage
- Language selection persists across sessions
- Automatic script detection for uploads
- Romanized query normalization (Hinglish support)
- RTL layout for Urdu

---

## 🚢 Deployment

### Backend (FastAPI)
```bash
# Production
uvicorn api.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Frontend (Next.js)
```bash
# Build
npm run build

# Start
npm start
```

### Environment Variables for Production
- Set `CORS_ALLOWED_ORIGINS` to your production domain
- Use secure `WEBHOOK_SECRET` and `GMAIL_OAUTH_STATE_SECRET`
- Configure Supabase production credentials

---

## 📝 License

This project is proprietary software. All rights reserved.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

## 📞 Support

For support, email support@patrarekha.ai or create an issue on GitHub.
