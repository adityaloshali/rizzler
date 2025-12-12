# Project Blueprint: "Rizzler" (AI Dating Coach & Companion)

## 1. Executive Summary

**The Product:** An all-in-one AI dating assistant that acts as a personal coach, a roleplay partner, and a real-time wingman. Unlike generic chatbots, this system is **context-aware**, **customizable** (learning from user-uploaded data), and **uncensored** (allowing for genuine romantic/NSFW roleplay practice).

**The Core differentiator:** The Agent is not a static bot. It possesses a persistent "Long Term Memory" (RAG) based on specific knowledge bases (PDFs, guides) provided by the user, and it maintains state across devices and time.

### The Problem
*   **Knowledge Gap:** Users have access to dating guides/books but struggle to internalize the information.
*   **Anxiety & Lack of Practice:** Users have no safe space to practice flirting or intimate conversations without fear of rejection.
*   **Analysis Paralysis:** When facing a real crush, users often freeze, not knowing how to reply to a text or interpret a screenshot.
*   **Sanitization:** Mainstream AI (ChatGPT, Claude) is heavily censored, making it useless for practicing romantic, flirtatious, or intimate (NSFW) dynamics.

### The Solution
A 3-Mode AI Application:
1.  **Tutor Mode:** Ingests user-provided knowledge (PDFs, screen grabs, notes) to teach and answer questions based *strictly* on that material.
2.  **Practice Mode:** An uncensored roleplay sandbox to practice skills with customizable personas (e.g., "The Crush," "The Ex," "The Flirt").
3.  **Analysis Mode:** A multimodal tool where users upload screenshots of real chats, and the AI suggests responses based on the "Tutor" knowledge base.

---

## 2. Technical Architecture (Low-Cost & Asynchronous)

To keep costs minimal while supporting complex RAG and sessions that span days, we will move away from expensive dedicated GPU hosting. Instead, we will use a **Smart Orchestration Backend** combined with **Pay-Per-Token APIs**.

### The Stack
*   **Backend:** `Python` with `FastAPI` (Async support is native).
*   **Database (The Brain):** `PostgreSQL` (via **Supabase** - Free Tier).
    *   Stores User Auth & Profiles.
    *   Stores Chat Logs (Persistence).
    *   **Vector Store:** Uses `pgvector` extension within Postgres for RAG (eliminates the need for expensive Pinecone).
*   **Orchestration:** `LangChain` or `LangGraph`.
*   **Task Queue:** `Celery` + `Redis` (For processing large PDF uploads asynchronously without freezing the app).
*   **AI Inference (The Intelligence):**
    *   *Router:* Decides which model to call.
    *   *Tutor/Analysis:* **Gemini 1.5 Flash** (Extremely cheap, huge context window, supports Vision) or **GPT-4o-mini**.
    *   *Practice (NSFW):* **OpenRouter API** accessing models like `Mythomax-L2-13b`, `Midnight-Miqu`, or `Dolphin-Mixtral` (Uncensored & Cheap).

### Why this architecture?
1.  **Statefulness:** The "Agent" logic lives in Python/Postgres. It retrieves chat history from the DB every time the user logs in, enabling sessions to pause for days and resume on any device.
2.  **Cost:** You only pay for what you use (tokens). No idle GPU server costs ($0 vs $500/month).
3.  **Async:** FastAPI handles the chat websocket; Celery handles the heavy document reading in the background.

---

## 3. Detailed Feature Breakdown

### Mode A: Tutor Mode (The RAG Knowledge Base)
*   **Input:** User uploads `.pdf`, `.md`, `.txt`, or images of text.
*   **Process (Async):**
    1.  File uploaded to storage.
    2.  Background worker extracts text.
    3.  Text is chunked and embedded (using a cheap model like `text-embedding-3-small`).
    4.  Embeddings stored in `pgvector`.
*   **Interaction:** User asks, "How do I handle a flake?" -> System searches DB -> Retrieves relevant paragraphs from uploaded books -> LLM synthesizes answer.

### Mode B: Practice Mode (Uncensored Roleplay)
*   **Persona Config:** User sets: Name, Age, Vibe (e.g., "Hard to get"), and Relationship Status.
*   **The Brain:** The prompt includes instructions to *ignore safety filters* and engage in adult/NSFW themes if the conversation leads there.
*   **Memory:** Fetches the last 10 messages + a summary of the conversation so far from Postgres.

### Mode C: Analysis Mode (The Wingman)
*   **Input:** Screenshot of a chat (Tinder/WhatsApp/iMessage).
*   **Process:**
    1.  Image sent to Multimodal LLM (Gemini Flash or GPT-4o).
    2.  Prompt: "Extract text and analyze the emotional sentiment. Based on the *Tutor Knowledge Base* (RAG), suggest 3 replies: Risky, Funny, and Safe."
*   **Output:** Text analysis + 3 clickable reply options.

---

## 4. Database Schema (Simplified)

To support the "Agent" persistence:

```sql
-- 1. Users
TABLE users (
  id UUID PRIMARY KEY,
  email TEXT,
  preferences JSONB -- Stores user style/goals
);

-- 2. Knowledge Base (RAG)
TABLE documents (
  id UUID PRIMARY KEY,
  user_id UUID,
  content TEXT,
  embedding VECTOR(1536) -- For semantic search
);

-- 3. Sessions (The persistent Agent state)
TABLE sessions (
  id UUID PRIMARY KEY,
  user_id UUID,
  mode VARCHAR, -- 'TUTOR', 'PRACTICE', 'ANALYSIS'
  persona_settings JSONB, -- Settings for the specific roleplay
  created_at TIMESTAMP,
  last_active TIMESTAMP
);

-- 4. Chat History
TABLE chat_logs (
  id UUID PRIMARY KEY,
  session_id UUID,
  role VARCHAR, -- 'user' or 'assistant'
  content TEXT,
  timestamp TIMESTAMP
);
```

---

## 5. Development Roadmap

### Phase 1: The Core (Backend & DB)
*   **Goal:** A working API that can remember chats and switch models.
*   **Tasks:**
    1.  Setup Supabase (Postgres + pgvector).
    2.  Setup FastAPI project.
    3.  Implement OpenRouter API connection (for switching between Safe and Uncensored models).
    4.  Create the `/chat` endpoint which accepts a `session_id`.

### Phase 2: RAG Implementation (The Tutor)
*   **Goal:** Upload a PDF and ask questions about it.
*   **Tasks:**
    1.  Create `/upload` endpoint.
    2.  Implement text extraction (PyPDF2).
    3.  Implement Embedding generation and storage in Postgres.
    4.  Modify `/chat` to perform a vector search before answering if in Tutor Mode.

### Phase 3: The Vision & Roleplay
*   **Goal:** Enable Sexting/Roleplay and Screenshot analysis.
*   **Tasks:**
    1.  **Roleplay:** Engineer the "System Prompts" to strip away AI mannerisms ("As an AI language model...").
    2.  **Vision:** Integrate Gemini Flash/GPT-4o Vision API for screenshot analysis.

### Phase 4: Frontend & State Management
*   **Goal:** Mobile interface.
*   **Tasks:**
    1.  Build UI in Flutter or React Native.
    2.  Create a "Mode Switcher" (Tutor | Practice | Analyze).
    3.  Implement WebSocket or Polling for real-time typing effect.

---

## 6. Cost Analysis (Estimated)

*   **Database & Auth:** **$0** (Supabase Free Tier - up to 500MB database, usually enough for text/vectors).
*   **Backend Hosting:** **$5/mo** (DigitalOcean Droplet or Render) - *Backend runs lightly; heavy lifting is done by APIs.*
*   **AI Intelligence (Variable):**
    *   *Gemini 1.5 Flash (Vision/Tutor):* ~$0.35 per 1 million tokens (Extremely cheap).
    *   *OpenRouter (Uncensored Models):* ~$0.20 - $0.50 per 1 million tokens.
    *   *Embeddings:* Pennies.

**Total Fixed Cost:** ~$5.00 / month.
**Total Variable Cost:** Scale linearly with user activity.

---

## 7. Next Steps
1.  **Clone Repo/Init Project:** Set up the Python environment.
2.  **Get API Keys:** Sign up for **OpenRouter** (for uncensored models) and **Google AI Studio** (for Gemini Flash vision).
3.  **Database:** Spin up a free Supabase project.