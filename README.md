# ✨ Sift: The Universal Startup Validator

**Bring your startup. We'll tell you the truth in 10 seconds.**

Sift is a lightning-fast, highly dynamic startup validator designed to bridge the gap between founders and venture capital. Simply drop a pitch deck, and Sift instantly evaluates it against core VC pillars, generates a structured readiness score, and launches an interactive AI Co-Pilot to help you fix the critical gaps standing between you and a term sheet.

Built with a premium, glassmorphism design system, Sift strips away the noise to focus entirely on actionable, brutal, and productive feedback.

---

## 🚀 Key Features

* **Universal Ingestion**: Drag and drop a `.pdf` or `.pptx` deck, paste a website or GitHub URL, or just type out your raw idea. Sift handles the rest.
* **The VC Radar Chart**: Go beyond a simple score. Sift visually indexes your startup across 5 core VC pillars (Market, Execution, Moat, Team-Product, and Economics) using an interactive Radar Chart.
* **Instant Actionable Feedback**: The moment your evaluation completes, Sift Co-Pilot proactively identifies your #1 critical gap and immediately offers a concrete rewrite for that specific slide.
* **Fluid & Premium UI**: Enjoy a frictionless experience with dynamic micro-animations, optimistic loading states, and a beautiful HSL dark-mode aesthetic.
* **BYO-Key Support**: Use Sift's default local inference, or supply your own API key for maximum power.

---

## 🏗️ Architecture & Stack

Sift is a lightweight React frontend backed by a robust Python FastAPI intelligence layer.

| Layer | Technology Stack |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Vanilla CSS, Recharts |
| **Backend** | FastAPI, Uvicorn, SQLite |
| **Model Router**| Groq, Anthropic, OpenAI, Cerebras, OpenRouter, Gemini, Ollama |
| **Local RAG** | ChromaDB, SentenceTransformers |

---

## ⚡ Quick Start (Local Development)

Get Sift running locally in minutes:

```bash
git clone git@github.com:saimihirj/Sift.git
cd Sift

# 1. Start the Backend Intelligence Layer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Start the Frontend Application
npm --prefix frontend install
npm --prefix frontend run dev
```

The frontend will be instantly available at `http://localhost:5173`.

---

## 🌍 Deployment

**Frontend (Vercel)**
1. Connect the repository to Vercel.
2. Set Framework Preset to **Vite**.
3. Add the `VITE_API_BASE_URL` environment variable pointing to your deployed backend.

**Backend (Render/Railway)**
1. Connect the repository to your host.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

## 📄 License
Proprietary. All rights reserved.
