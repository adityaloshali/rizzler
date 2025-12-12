# 🔥 Rizzler - AI Dating Coach & Companion

An all-in-one AI dating assistant that acts as a personal coach, roleplay partner, and real-time wingman.

> 📖 **[Architecture Documentation →](docs/ARCHITECTURE.md)** - System design, data models, Mermaid diagrams
> 
> 🤖 **[AI Agents Documentation →](docs/AGENTS.md)** - Agent architecture, prompts, LLM routing

## ✨ Features

### Three Powerful Modes

1. **📚 Tutor Mode** - Learn from your uploaded dating guides
   - Upload PDFs, books, and notes
   - Ask questions and get advice based on YOUR knowledge base
   - RAG-powered responses grounded in real dating wisdom

2. **💬 Practice Mode** - Roleplay with customizable personas
   - Create any persona (The Crush, The Ex, The Flirt)
   - Practice conversations in a safe environment
   - Uncensored responses for realistic practice

3. **📱 Analysis Mode** - Get reply suggestions for real chats
   - Upload screenshots of conversations
   - AI analyzes the emotional dynamics
   - Get 3 reply options: 🔥 Risky, 😂 Funny, ✅ Safe

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL + pgvector (via Supabase)
- **Auth**: Supabase Auth
- **AI**: 
  - Gemini 1.5 Flash (Tutor/Analysis)
  - OpenRouter (Practice Mode - uncensored)
  - OpenAI Embeddings (RAG)
- **Task Queue**: Celery + Redis
- **Deployment**: Docker (Coolify/Render/Railway compatible)

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- API Keys:
  - [Supabase](https://supabase.com) (free tier)
  - [OpenAI](https://platform.openai.com) (for embeddings)
  - [Google AI Studio](https://aistudio.google.com) (for Gemini)
  - [OpenRouter](https://openrouter.ai) (for uncensored models)

### 1. Clone & Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/rizzler.git
cd rizzler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Application
APP_NAME=Rizzler
APP_ENV=development
DEBUG=true
SECRET_KEY=your-super-secret-key-change-me

# Server
HOST=0.0.0.0
PORT=8000

# CORS (your frontend URL)
CORS_ORIGINS=http://localhost:3000

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLIC_KEY=your-public-key
SUPABASE_SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://postgres:password@db.your-project.supabase.co:5432/postgres

# AI Providers
OPENAI_API_KEY=sk-your-openai-key
GOOGLE_API_KEY=your-google-ai-key
OPENROUTER_API_KEY=sk-or-your-openrouter-key

# Models
EMBEDDING_MODEL=text-embedding-3-small
TUTOR_MODEL=gemini-1.5-flash
PRACTICE_MODEL=mythomax-l2-13b

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0
```

### 3. Setup Database

**Option A: Use Supabase (Recommended)**

1. Create a project at [supabase.com](https://supabase.com)
2. Enable pgvector extension in SQL editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy your connection string to `DATABASE_URL`

**Option B: Local Postgres**

```bash
# Start local Postgres + Redis
docker compose up -d postgres redis
```

### 4. Run the Server

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --port 8000

# Or using the module
python -m app.main
```

Visit http://localhost:8000/docs to see the API documentation.

### 5. (Optional) Run Celery Worker

For async document processing:

```bash
# In a separate terminal
celery -A app.workers.celery_app worker --loglevel=info
```

## 📁 Project Structure

```
rizzler/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # Environment configuration
│   ├── database.py          # DB connection & Supabase client
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── document.py
│   │   └── chat.py
│   ├── routers/             # API endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── sessions.py      # Session management
│   │   ├── chat.py          # Chat interactions
│   │   └── upload.py        # Document upload
│   ├── services/            # Business logic
│   │   ├── llm_router.py    # LLM provider abstraction
│   │   ├── rag_service.py   # Vector search
│   │   └── document_service.py
│   └── workers/             # Celery tasks
│       └── document_processor.py
├── scripts/
│   └── init-db.sql
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🔌 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create new account |
| POST | `/api/v1/auth/login` | Login & get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sessions/` | Create new session |
| GET | `/api/v1/sessions/` | List sessions |
| GET | `/api/v1/sessions/{id}` | Get session details |
| PATCH | `/api/v1/sessions/{id}` | Update session |
| DELETE | `/api/v1/sessions/{id}` | Delete session |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/` | Send message |
| GET | `/api/v1/chat/history/{session_id}` | Get chat history |

### Upload (Knowledge Base)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload/` | Upload document |
| GET | `/api/v1/upload/` | List documents |
| DELETE | `/api/v1/upload/{source_id}` | Delete document |
| POST | `/api/v1/upload/search` | Search knowledge base |

## 🐳 Deployment

### Docker Build

```bash
# Build image
docker build -t rizzler:latest .

# Run container
docker run -p 8000:8000 --env-file .env rizzler:latest
```

### Coolify (Self-Hosted)

1. Connect your Git repository to Coolify
2. Set environment variables in Coolify dashboard
3. Deploy! Coolify will auto-detect the Dockerfile

### Render

1. Create a new Web Service
2. Connect your repository
3. Render auto-detects Python/Docker
4. Add environment variables
5. Deploy!

### Railway

1. Create new project from GitHub
2. Add environment variables
3. Railway auto-deploys on push

## 🧪 Development

```bash
# Run tests
pytest

# Format code
black app/
ruff check app/ --fix

# Type checking
mypy app/
```

## 📝 License

MIT License - feel free to use this for your own projects!

---

## 🗺️ Roadmap

- [x] Phase 1: Core Backend & Auth
- [x] Phase 2: RAG Implementation (Tutor Mode)
- [ ] Phase 3: Practice Mode (Uncensored Roleplay)
- [ ] Phase 4: Analysis Mode (Vision)
- [ ] Phase 5: Frontend (Next.js PWA)
- [ ] Phase 6: Voice Input/Output
- [ ] Phase 7: Mobile Apps

---

Built with 💜 by the Rizzler team
