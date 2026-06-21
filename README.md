# Kubernetes Troubleshooting Assistant

A RAG-based assistant that answers Kubernetes error questions using **Azure OpenAI** and **Azure AI Search**. Ask a question in plain English — the assistant retrieves relevant knowledge from its knowledge base and returns a grounded, context-only answer.

---

## How it works

```
Your question (text)
    │
    ▼
01. Embed          → Azure OpenAI (text-embedding-3-small) converts question to 1536-dim vector
    │
    ▼
02. Vector Search  → Azure AI Search finds top 3 closest knowledge chunks (HNSW)
    │
    ▼
03. Build Prompt   → Retrieved chunks + question assembled into a grounded prompt
    │
    ▼
04. Chat           → GPT-4o answers using ONLY the retrieved context
    │
    ▼
JSON response via POST /ask
```

---

## Project structure

```
Kubernetes-assistant/
│
├── 01_test_embedding.py     # Verify Azure OpenAI connection → prints vector length (expect 1536)
├── 02_create_index.py       # Create k8s-knowledge index in Azure AI Search with HNSW config
├── 03_upload_docs.py        # Chunk knowledge_base/k8s_errors.md and upload to AI Search
├── 04_rag_pipeline.py       # Core RAG pipeline: embed → search → build_prompt → answer
├── app.py                   # Flask wrapper: exposes POST /ask as an HTTP endpoint
│
├── knowledge_base/
│   └── k8s_errors.md        # 11 Kubernetes error entries (OOMKilled, CrashLoopBackOff, etc.)
│
├── requirements.txt         # Python dependencies
├── .env                     # Azure credentials (not committed — see setup below)
└── .gitignore
```

---

## Errors covered

The knowledge base currently covers:

- OOMKilled
- CrashLoopBackOff
- ImagePullBackOff
- Pending — Insufficient Resources
- Evicted
- Readiness Probe Failing
- Liveness Probe Failing
- DNS Resolution Failure
- PVC Not Bound
- Node NotReady
- CreateContainerConfigError

---

## Prerequisites

- Python 3.9+
- An Azure subscription with:
  - Azure OpenAI resource with two deployments:
    - `embedding` → `text-embedding-3-small`
    - `chat` → `gpt-4o`
  - Azure AI Search resource (free tier works)

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Kubernetes-assistant
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

Create a `.env` file in the project root:

```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_API_VERSION=2024-06-01
AZURE_OPENAI_DEPLOYMENT=chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding
AZURE_SEARCH_ENDPOINT=https://<your-search-resource>.search.windows.net
AZURE_SEARCH_ADMIN_KEY=<your-admin-key>
AZURE_SEARCH_INDEX_NAME=k8s-knowledge
```

> Never commit `.env` to version control. It is already listed in `.gitignore`.

### 5. Verify the Azure OpenAI connection

```bash
python3 01_test_embedding.py
```

Expected output:
```
Embedding created successfully!
 Length: 1536
```

### 6. Create the AI Search index

```bash
python3 02_create_index.py
```

Expected output:
```
Search index 'k8s-knowledge' created successfully.
```

### 7. Upload the knowledge base

```bash
python3 03_upload_docs.py
```

Expected output: 12 documents uploaded, all `status: True`, `statusCode: 201`.

---

## Running the assistant

### Option A — Command line (quick test)

```bash
python3 04_rag_pipeline.py
```

Edit the `question` variable in `main()` to test different queries.

### Option B — HTTP API (Flask)

```bash
python3 app.py
```

The server starts on `http://127.0.0.1:5000`. Send questions via POST:

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "My pod keeps restarting and the status shows OOMKilled"}'
```

Example response:

```json
{
  "answer": "Your pod is OOMKilled because the container exceeded its memory limit. Check current usage with `kubectl top pod <name>`, then increase `resources.limits.memory` in your pod spec..."
}
```

### Error responses

| Status | Meaning |
|---|---|
| 400 | `question` field missing from request body |
| 404 | Route not found |
| 405 | Wrong HTTP method used |

---

## Extending the knowledge base

To add new error entries, edit `knowledge_base/k8s_errors.md` using this structure:

```markdown
## Error Name

**What it means:** ...

**Symptoms:**
- ...

**Common causes:**
- ...

**How to fix:**
1. ...

---
```

Then re-run `03_upload_docs.py` to upload the new chunks. The script is idempotent — re-running it overwrites existing documents safely.

---

## Built with

- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) — embeddings + chat completions
- [Azure AI Search](https://azure.microsoft.com/en-us/products/ai-services/ai-search) — vector index with HNSW
- [openai Python SDK](https://github.com/openai/openai-python)
- [azure-search-documents](https://pypi.org/project/azure-search-documents/)
- [Flask](https://flask.palletsprojects.com/)
