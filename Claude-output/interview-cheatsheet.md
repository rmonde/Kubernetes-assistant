# Kubernetes Assistant — RAG Interview Cheat Sheet
*Read before any interview on Azure AI, RAG, or GenAI architecture.*

---

## The 60-Second Mental Model

RAG = Retrieval-Augmented Generation.
LLMs hallucinate when they don't know something. RAG gives them a document to read first.
Step 1: find relevant docs (retrieval via embeddings + vector search).
Step 2: give those docs to the LLM as context and ask it to answer (generation).
The LLM never needs to "know" the answer — it just needs to read and summarise.

---

## Core Definitions

| Term | One-Line Definition |
|---|---|
| **RAG** | A pattern that retrieves relevant docs first, then passes them as context to an LLM for generation |
| **Embedding** | A vector (list of numbers) that represents the meaning of text in mathematical space |
| **Vector** | A list of numbers (e.g., 1536 floats) — the numerical fingerprint of a text chunk |
| **Cosine similarity** | How to measure if two vectors point in the same direction — 1.0 = identical meaning, 0 = unrelated |
| **Chunking** | Splitting large documents into smaller pieces before embedding — LLMs have context limits |
| **Index** | AI Search's structured store for documents + their vectors |
| **Deployment (AOAI)** | Your named instance of a model with reserved capacity (TPM) |
| **TPM** | Tokens Per Minute — the capacity unit for Azure OpenAI; 50K TPM ≈ 50 requests/minute |
| **Grounding** | Using retrieved context to make LLM answers factual and source-based, not hallucinated |

---

## RAG Flow — Draw This in an Interview

```
User: "My pod keeps crashing with OOMKilled"
     │
     ▼
text-embedding-3-small → [0.23, -0.87, 0.41, ...]  (question vector)
     │
     ▼
Azure AI Search → cosine similarity search → top 3-5 matching chunks
     │
     ▼
Prompt = "Use ONLY the context below to answer:\n[chunk1]\n[chunk2]\nQuestion: ..."
     │
     ▼
gpt-4o → "OOMKilled means your container exceeded its memory limit. Run
          kubectl describe pod <name> and increase the memory limit..."
```

**Key point to say out loud:** The embedding model converts text to vectors. The chat model reads context and generates answers. They never swap roles.

---

## Azure OpenAI vs OpenAI API — When Asked "Why Azure?"

| | OpenAI API | Azure OpenAI |
|---|---|---|
| Data residency | Leaves your infrastructure | Stays in your Azure tenant |
| Compliance | Standard OpenAI terms | Azure compliance certs (SOC2, HIPAA, ISO) |
| Network | Public internet | Private VNet, private endpoints |
| Management | OpenAI console | Azure RBAC, Azure Monitor, Azure Policy |

**Interview answer:** "For enterprise customers with data residency requirements or regulated industries, Azure OpenAI is the only viable option. Same models, same API surface, but data never leaves the customer's Azure environment."

---

## Model vs Deployment — The Abstraction That Matters

```
Azure OpenAI Resource
├── deployment: "embedding"  → text-embedding-3-small  (your code calls this name)
└── deployment: "chat"       → gpt-4o 2024-11-20       (your code calls this name)
```

- **Model** = Microsoft's infrastructure, shared, you can't control it
- **Deployment** = your reservation of that model with a specific TPM allocation
- **Code calls deployment name** — when you upgrade from gpt-4o to gpt-4o-turbo, your code doesn't change, only the deployment in Azure does
- **Name by role** (`embedding`, `chat`) not by model (`gpt-4o-mini`) — roles are stable, model names change

---

## Vector Search vs Keyword Search

| | Keyword Search | Vector Search |
|---|---|---|
| Finds | Pages containing exact words | Pages with similar meaning |
| "OOMKilled pod crash" finds | Docs with "OOMKilled" | Docs about memory limits, container resources, even if "OOMKilled" not present |
| How | Inverted index (like a book index) | Cosine similarity between vectors |
| Best for | Exact terms, IDs, known phrases | Natural language questions, synonyms, concepts |

**Hybrid search** (Azure AI Search supports this) = keyword + vector combined. Best results for most real-world queries.

---

## What Three Things Does Code Need to Call Azure OpenAI?

1. **Endpoint** — `https://<resource>.openai.azure.com/`
2. **API Key** — authenticates the request
3. **Deployment name** — which model to use (`embedding` or `chat`)

**Why `.env` and not hardcoded?**
- API keys in source code get pushed to GitHub
- GitHub secret scanning or a bad actor finds it within minutes
- Anyone with the key can bill your subscription for API calls
- `.env` stays local, never committed (`.gitignore`), loaded at runtime by `python-dotenv`

---

## Azure AI Search — Key Concepts

- **Index** = a table with defined fields; must include a vector field with correct dimensions (1536 for text-embedding-3-small)
- **Document** = one row in the index (one chunk of text + its vector + metadata)
- **Admin key** = full read/write access (use for indexing documents)
- **Query key** = read-only (use in your app for search queries)
- **Free tier** = 50MB, 3 indexes, no SLA — fine for dev/learning

---

## Hot Interview Questions

**"What is RAG and why do you need it?"**
→ LLMs are trained on public data up to a cutoff. RAG adds a retrieval step that finds relevant private/recent documents first, then passes them as context to the LLM. This grounds the answer in real data and eliminates hallucination for domain-specific questions.

**"What is an embedding?"**
→ A numerical representation of text's meaning — a vector of ~1536 floats. Similar meaning = similar vectors. This allows semantic search: finding docs that mean the same thing even if they share no words.

**"Why chunk documents instead of embedding the whole thing?"**
→ LLMs have a context window limit (e.g., 128K tokens for gpt-4o). Embedding the whole doc would also produce one generic vector that doesn't represent any specific part well. Smaller chunks = more precise retrieval = better answers.

**"What is the difference between keyword search and vector search?"**
→ Keyword finds exact word matches. Vector finds semantic similarity — meaning, not words. In practice, hybrid search (both combined) gives the best results.

**"How do you prevent the LLM from making things up in a RAG system?"**
→ Prompt engineering: "Answer ONLY using the provided context. If the answer is not in the context, say 'I don't know'." Also: retrieve more chunks for better coverage, and cite the source document in the response.

---

## Architecture in One Diagram

```
Knowledge Base (K8s docs)
        │
        ▼
Chunking → text-embedding-3-small → vectors
        │
        ▼
Azure AI Search Index (text + vectors)

        ← at query time →

User Question → text-embedding-3-small → question vector
                        │
                        ▼
              Azure AI Search (cosine similarity)
                        │
                     Top 3-5 chunks
                        │
                        ▼
              gpt-4o (context + question → answer)
```

---

*Last updated: 2026-06-09 | Next: create project files, write 01_test_embedding.py*
