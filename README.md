# Golem RAG

Standalone RAG (Retrieval-Augmented Generation) system for FemCAD: hybrid dense + lexical retrieval with optional cross-encoder reranking.

Extracted from the [Golem](https://github.com/your-org/Golem) femcad-copilot backend.

## Features

- **Hybrid retrieval**: Dense (vector) + lexical (BM25) with Reciprocal Rank Fusion (RRF)
- **Optional reranking**: Cross-encoder (e.g. ms-marco-MiniLM) for better relevance
- **FemCAD fundamentals**: Always-injected basics + domain-aware retrieval
- **CLI and web app**: `ask_cli.py` and FastAPI `web_app.py`
- **Azure Storage**: Optional chat persistence (Table/Blob)

## Setup

```bash
cd golem-rag
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create a `.env` in the repo root (see `.env.example` if added) with:

- `OPENAI_API_KEY` or Azure OpenAI endpoint/key for LLM
- `FEMCAD_CODE_DB`, `FEMCAD_DOCS_DB` (paths to Chroma vector DBs; optional, have defaults)
- `VECTOR_DB_MODE`, `VECTOR_DB_PROVIDER` for cloud vector DB (optional)

Place FemCAD basics at `data/femcad_basics_compact.md` (or set path via env/config).

## Run

**CLI:**

```bash
python -m rag.rag -q "how do I create a beam?"
```

**Web app:**

```bash
uvicorn rag.web_app:app --reload --host 0.0.0.0 --port 8000
```

**Azure (e.g. golem.histruct.com):** You don’t choose a port — Azure sets `PORT` and the app uses it automatically.

1. **Startup command** (Azure App Service → Configuration → General settings):
   ```bash
   python run_web.py
   ```
2. **Custom domain:** In Azure, add `golem.histruct.com` under your Web App → Custom domains and configure DNS as instructed.
3. **Environment variables** (App Service → Configuration → Application settings) so login works at that URL:
   - `AUTH_OIDC_CLIENT_URL` = `https://golem.histruct.com`
   - (Optional) `AUTH_OIDC_REDIRECT_PATH` = `/callback` if your OIDC provider expects `https://golem.histruct.com/callback`

The app will start even if `data/` or vector DBs are missing (fallback mode with placeholder content).

**FemCAD / HiStruct sign-in not working?** The app must listen on `0.0.0.0` (all interfaces) so OIDC callbacks from HiStruct can reach it. If the Azure startup command is `uvicorn ...` without `--host 0.0.0.0`, the app may bind only to `127.0.0.1` and sign-in will fail. Use **Startup Command** = `python run_web.py` (or `startup.sh`); see `run_web.py` and `startup.sh`.

## Layout

- `rag/` – RAG package (retriever, chain, vectorstores, chunkers, web app, CLI)
- `data/` – Optional: `femcad_basics_compact.md`, documentation
- `vectordb_code/`, `vectordb_docs/` – Local Chroma DBs (gitignored; create via your indexing pipeline)

See `rag/ARCHITECTURE.md` for design details.

## Pushing to GitHub

This folder is already a git repo. To publish it as a new GitHub repository:

1. **Create a new repo on GitHub** (e.g. `golem-rag`) – do *not* initialize with a README.

2. **Add the remote and push:**

   ```bash
   cd /path/to/golem-rag
   git add .
   git commit -m "Initial commit: RAG package from Golem femcad-copilot"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/golem-rag.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` and `golem-rag` with your GitHub username and repo name.

## License

Same as the parent Golem project.
