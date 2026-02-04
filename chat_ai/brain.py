"""brain.py
RAG-style brain: index documents, retrieve, and answer queries using LLM if available.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any, Iterator, Tuple, Union
import os
import logging
import json

from .data import load_text_file, load_csv, load_directory, prepare_documents
from .embeddings import EmbeddingBackend
from .memory import ChatMemory
from .wikipedia import fetch_wikipedia_answer
from .reasoning import ChainOfThoughtReasoner, ConsistencyChecker
from .tools import ToolSystem

logger = logging.getLogger(__name__)


class LLMClient:
    """Lightweight LLM wrapper with OpenAI support and a safe fallback."""

    def __init__(self) -> None:
        self._mode = "fallback"
        self._client = None
        api_key = os.getenv("OPENAI_API_KEY")
        # Allow overriding preferred provider via env var (values: 'openai' or 'huggingface')
        preferred = (os.getenv("PREFERRED_LLM") or os.getenv("LLM_PROVIDER") or "").lower()

        # Support Hugging Face Inference API keys/env
        self._hf_key = os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY")
        self._hf_model = os.getenv("HF_MODEL") or "google/flan-t5-large"
        # Support LangSmith / LangChain API key
        self._langsmith_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
        # Support local Llama model path for on-device inference
        self._local_model_path = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_LLAMA_MODEL_PATH")
        # Support Ollama local model name (first model in list if not set)
        self._ollama_model_name = os.getenv("OLLAMA_MODEL_NAME")

        # Decide mode respecting preference
        if preferred == "huggingface" and self._hf_key:
            self._mode = "huggingface"
        elif preferred == "openai" and api_key:
            try:
                import openai  # type: ignore
                # Support both pre-1.0 and v1+ openai python libs
                if hasattr(openai, "OpenAI"):
                    # Newer openai client (v1+)
                    try:
                        self._client = openai.OpenAI(api_key=api_key)
                        self._client_type = "openai_v1"
                    except Exception as e:
                        logger.warning(f"Failed to initialize OpenAI client with new API: {e}")
                        # fallback to module-level usage if construction fails
                        openai.api_key = api_key
                        self._client = openai
                        self._client_type = "openai_legacy"
                else:
                    openai.api_key = api_key
                    self._client = openai
                    self._client_type = "openai_legacy"
                self._mode = "openai"
            except Exception as e:
                logger.warning(f"Failed to load OpenAI legacy client: {e}")
                self._mode = "fallback"
        elif preferred == "langsmith" and self._langsmith_key:
            self._mode = "langsmith"
        elif preferred == "ollama" and self._ollama_model_name:
            self._mode = "ollama"
        elif preferred == "mock":
            self._mode = "mock"
        else:
            # Default behaviour: prefer OpenAI if key present, otherwise HF, then LangSmith if present
            if api_key:
                try:
                    import openai  # type: ignore
                    if hasattr(openai, "OpenAI"):
                        try:
                            self._client = openai.OpenAI(api_key=api_key)
                            self._client_type = "openai_v1"
                        except Exception as e:
                            logger.warning(f"Failed to initialize OpenAI client with new API: {e}")
                            openai.api_key = api_key
                            self._client = openai
                            self._client_type = "openai_legacy"
                    else:
                        openai.api_key = api_key
                        self._client = openai
                        self._client_type = "openai_legacy"
                    self._mode = "openai"
                except Exception as e:
                    logger.warning(f"Failed to load OpenAI legacy client: {e}")
                    self._mode = "fallback"
            elif self._hf_key:
                self._mode = "huggingface"
            elif self._langsmith_key:
                self._mode = "langsmith"
            elif self._local_model_path:
                # If a local model path is present, allow local mode as fallback
                self._mode = "local"
            elif self._ollama_model_name:
                # If an Ollama model name is present, use Ollama mode
                self._mode = "ollama"

    def chat(self, prompt: str, system: Optional[str] = None, stream: bool = False) -> Union[str, Iterator[str]]:
        # Local llama-cpp path (on-device inference)
        if self._mode == "local" and self._local_model_path:
            try:
                try:
                    from llama_cpp import Llama  # type: ignore
                except Exception:
                    # llama-cpp not installed
                    raise
                # instantiate client lazily
                if not getattr(self, "_local_client", None):
                    self._local_client = Llama(model_path=self._local_model_path)
                # llama-cpp create interface
                params = dict(max_tokens=int(os.getenv("LOCAL_MAX_TOKENS", "256")), temperature=float(os.getenv("LOCAL_TEMPERATURE", "0.2")), stream=stream)
                resp = self._local_client.create(prompt=prompt, **params)
                
                if stream:
                    def _gen():
                        for chunk in resp:
                            try:
                                yield chunk["choices"][0]["text"]
                            except Exception as e:
                                logger.debug(f"Error yielding llama-cpp stream chunk: {e}")
                    return _gen()
                else:
                    # typical shape: {'choices': [{'text': '...'}], ...}
                    try:
                        return resp["choices"][0]["text"].strip()
                    except Exception:
                        try:
                            return resp.choices[0].text.strip()
                        except Exception:
                            return str(resp)
            except Exception:
                logger.exception("Local Llama model invocation failed; falling back")

        # OpenAI path (if available)
        if self._mode == "openai" and self._client is not None:
            try:
                # Build messages correctly: optional system message, then user prompt
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
                temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

                # Support newer openai v1 client vs legacy module
                if getattr(self, "_client_type", None) == "openai_v1":
                    # new client: client.chat.completions.create(...)
                    resp = self._client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        stream=stream
                    )
                    if stream:
                        def _gen_v1():
                            for chunk in resp:
                                content = chunk.choices[0].delta.content
                                if content:
                                    yield content
                        return _gen_v1()
                    else:
                        # try to access content in several possible shapes
                        try:
                            return resp.choices[0].message.content.strip()
                        except Exception:
                            try:
                                return resp["choices"][0]["message"]["content"].strip()
                            except Exception:
                                return str(resp)
                else:
                    resp = self._client.ChatCompletion.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        stream=stream
                    )
                    if stream:
                        def _gen_legacy():
                            for chunk in resp:
                                content = chunk.choices[0].delta.get("content", "")
                                if content:
                                    yield content
                        return _gen_legacy()
                    else:
                        try:
                            return resp["choices"][0]["message"]["content"].strip()
                        except Exception:
                            return str(resp)
            except Exception:
                logger.exception("OpenAI ChatCompletion failed")

            # LangSmith / LangChain client path (lazy)
            if self._mode == "langsmith" or (self._langsmith_key and self._mode == "fallback"):
                # LangChain streaming is complex, fallback to non-streaming for now or implement callback
                pass 

        # Hugging Face Inference API path
        if self._mode in ("huggingface",) or (self._hf_key and self._mode == "fallback"):
             # HF Inference API streaming is not always supported easily via requests
             pass

        # Ollama path (if available)
        if self._mode == "ollama":
            try:
                import ollama
                model = self._ollama_model_name or ollama.list()['models'][0]['name']
                if stream:
                    resp = ollama.generate(model=model, prompt=prompt, stream=True)
                    def _gen_ollama():
                        for chunk in resp:
                            yield chunk.get('response', '')
                    return _gen_ollama()
                else:
                    resp = ollama.generate(model=model, prompt=prompt, stream=False)
                    return resp.get('response', '').strip()
            except Exception:
                logger.exception("Ollama generation failed")

        # Mock path
        if self._mode == "mock":
            msg = f"MOCK RESPONSE: {prompt[-50:]}..."
            if stream:
                def _gen_mock():
                    yield msg
                return _gen_mock()
            return msg

        # Fallback: return trimmed prompt tail as a dumb echo
        tail = prompt[-500:]
        msg = f"(fallback) {tail}"
        if stream:
            def _gen_fallback():
                yield msg
            return _gen_fallback()
        return msg

    def summarize(self, text: str, max_chars: int = 800) -> str:
        """Try to produce a short summary of `text` using the available LLMs.

        If no LLM is available, return a truncated form of the input.
        """
        if not text:
            return ""
        system = "Resume brevemente el historial de conversación en pocas líneas en español."
        try:
            summary = self.chat(prompt=text, system=system)
            if summary:
                return summary[:max_chars]
        except Exception:
            logger.exception("Summarization via LLM failed")
        # fallback: truncate
        return (text[:max_chars] + "...") if len(text) > max_chars else text

    @property
    def mode_name(self) -> str:
        return self._mode


class Brain:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", storage_dir: Optional[str] = None, prefer_faiss: bool = True, user_id: str = "anonymous", db_path: str = None) -> None:
        # Initialize embedder (Lazy / Safe Mode)
        # Force simple embedder for now to avoid hangs if model download fails
        self.embedder = None 
        # If embedder initialization failed (heavy deps missing), provide a
        # lightweight fallback embedder so the service remains responsive.
        try:
            self.embedder = EmbeddingBackend(model_name=model_name)
        except Exception:
            logger.exception("Failed to initialize EmbeddingBackend, falling back to simple embedder.")
            self.embedder = None
        
        # If embedder initialization failed (heavy deps missing), provide a
        # lightweight fallback embedder so the service remains responsive.
        if getattr(self, 'embedder', None) is None:
            class _SimpleEmbedder:
                """Very small embedding fallback using token counts.

                Not semantically rich but allows similarity-based retrieval
                and relatedness checks without heavy native dependencies.
                """
                backend_name = 'simple'

                def encode_texts(self, texts):
                    out = []
                    for t in texts:
                        s = (t or '')
                        # features: length, vowel count, word count
                        words = s.split()
                        vowels = sum(1 for c in s.lower() if c in 'aeiouáéíóú')
                        out.append([len(s), len(words), vowels])
                    return out

                def encode_query(self, q):
                    return self.encode_texts([q])[0]

            self.embedder = _SimpleEmbedder()
        
        # Initialize LLM client
        self.llm = LLMClient()
        
        # Initialize enhanced memory system
        # Initialize enhanced memory system
        self.memory = ChatMemory(max_chars=4000)
        self.enhanced_memory = self.memory # Enhanced memory is currently the same as basic memory
        
        # Initialize advanced intelligence components
        self.cot_reasoner = ChainOfThoughtReasoner(self.llm)
        self.consistency_checker = ConsistencyChecker(self.llm)
        self.tool_system = ToolSystem()
        
        # Initialize Knowledge Graph (inspired by "The Reality Weaver")
        try:
            from .knowledge_graph import KnowledgeGraph
            from .relation_extractor import RelationExtractor
            kg_db_path = os.path.join(storage_dir, 'knowledge_graph.db') if storage_dir else 'knowledge_graph.db'
            self.knowledge_graph = KnowledgeGraph(db_path=kg_db_path)
            self.relation_extractor = RelationExtractor(self.knowledge_graph, self.llm)
            logger.info("Knowledge Graph initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Knowledge Graph: {e}")
            self.knowledge_graph = None
            self.relation_extractor = None
        
        # Choose store (import lazily to avoid heavy deps at module import time)
        try:
            from .vector_store import InMemoryVectorStore, FaissVectorStore  # local import
            self.store = None
            if prefer_faiss:
                try:
                    import faiss  # type: ignore  # noqa: F401
                    self.store = FaissVectorStore()
                except Exception:
                    self.store = InMemoryVectorStore()
            else:
                self.store = InMemoryVectorStore()
        except Exception:
            # If vector_store cannot be imported (e.g., numpy missing), fallback to a minimal in-memory stub
            logger.exception("Failed to import vector_store; using in-process fallback store.")
            class _StubStore:
                def __init__(self):
                    self._data = []
                def add(self, embeddings, metas):
                    self._data.append((embeddings, metas))
                def search(self, q, top_k=4):
                    return []
            self.store = _StubStore()

        # Track original doc chunks for retrieval output
        self._corpus_texts: List[str] = []
        self._corpus_metas: List[Dict[str, str]] = []
        self._storage_dir = storage_dir
        # Autoload if storage given
        if self._storage_dir:
            self.load_index(self._storage_dir)
        
        # Simple in-memory cache for retrieval: {query: results}
        self._retrieve_cache = {}
        self._cache_max_size = 100


    def ingest_files(self, paths: List[str], chunk_chars: int = 800, overlap: int = 150) -> int:
        """Ingest a mix of files or directories."""
        raw_docs: List[Dict[str, str]] = []
        for p in paths:
            if os.path.isdir(p):
                raw_docs.extend(load_directory(p))
            elif os.path.isfile(p):
                lower = os.path.basename(p).lower()
                if lower.endswith('.txt'):
                    raw_docs.extend(load_text_file(p))
                elif lower.endswith('.csv'):
                    raw_docs.extend(load_csv(p))
        prepared = prepare_documents(raw_docs, max_chars=chunk_chars, overlap=overlap)

        texts = [d["text"] for d in prepared]
        # Only fit corpus for backends that require training (e.g., TF-IDF)
        try:
            if getattr(self.embedder, "backend_name", None) == "tfidf":
                self.embedder.fit_corpus(texts)
        except Exception:
            logger.exception("Error fitting embedder corpus during ingest_files; continuing with encode.")

        X = self.embedder.encode_texts(texts)

        metas = [{k: v for k, v in d.items() if k != "text"} for d in prepared]
        self.store.add(embeddings=X, metas=metas)

        self._corpus_texts.extend(texts)
        self._corpus_metas.extend(metas)
        # persist if configured
        if self._storage_dir:
            self.save_index(self._storage_dir)
        return len(prepared)

    def ingest_raw(self, docs: List[Dict[str, str]], chunk_chars: int = 800, overlap: int = 150) -> int:
        """Ingest already-provided raw documents.
        
        Supports standard text docs: {'source': '...', 'text': '...'}
        Supports Experience Objects: {'title': '...', 'context': '...', 'sensory_data': {...}, 'action_plan': [...]}
        """
        if not docs:
            return 0
            
        # Pre-process to detect Experience Objects and flatten them for embedding,
        # while keeping the rich structure in metadata.
        processed_docs = []
        for d in docs:
            if 'sensory_data' in d or 'action_plan' in d:
                # It's an Experience Object
                # Create a rich text representation for embedding
                title = d.get('title', 'Untitled Experience')
                context = d.get('context', '')
                sensory = d.get('sensory_data', {})
                actions = d.get('action_plan', [])
                
                text_repr = f"EXPERIENCE: {title}\nCONTEXT: {context}\n"
                if sensory:
                    text_repr += f"SENSORY: {json.dumps(sensory, ensure_ascii=False)}\n"
                if actions:
                    text_repr += f"ACTIONS: {json.dumps(actions, ensure_ascii=False)}\n"
                
                # Store the full object in metadata as a JSON string
                d_copy = d.copy()
                d_copy['text'] = text_repr
                d_copy['is_experience'] = 'true'
                d_copy['experience_json'] = json.dumps(d, ensure_ascii=False)
                processed_docs.append(d_copy)
            else:
                # Standard doc
                processed_docs.append(d)

        prepared = prepare_documents(processed_docs, max_chars=chunk_chars, overlap=overlap)
        texts = [d["text"] for d in prepared]
        
        # Extract relations to Knowledge Graph (if available)
        if self.relation_extractor:
            for d in processed_docs:
                try:
                    if 'sensory_data' in d or 'action_plan' in d:
                        # Experience Object - extract rich relations
                        self.relation_extractor.extract_from_experience_object(d)
                    elif 'text' in d:
                        # Standard document - extract relations from text
                        source = d.get('source', 'unknown')
                        doc_id = d.get('id') or f"{source}_{hash(d.get('text', '')) % 1000000}"
                        self.relation_extractor.extract_from_text(d.get('text', ''), source, doc_id)
                except Exception as e:
                    logger.warning(f"Error extracting relations: {e}")
        
        # For TF-IDF, fitting incrementally is required. For pre-trained models (sentence-transformers)
        # fitting is unnecessary and expensive; skip it.
        try:
            if getattr(self.embedder, "backend_name", None) == "tfidf":
                corpus_for_fit = [*self._corpus_texts, *texts]
                if corpus_for_fit:
                    self.embedder.fit_corpus(corpus_for_fit)
        except Exception:
            logger.exception("Error fitting embedder corpus during ingest_raw; continuing with encode.")

        try:
            X = self.embedder.encode_texts(texts)
        except Exception:
            logger.exception("Error encoding texts during ingest_raw")
            raise
            
        metas = [{k: v for k, v in d.items() if k != "text"} for d in prepared]
        self.store.add(embeddings=X, metas=metas)
        self._corpus_texts.extend(texts)
        self._corpus_metas.extend(metas)
        if self._storage_dir:
            self.save_index(self._storage_dir)
        return len(prepared)

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, str]]:
        cache_key = f"{query}::{top_k}"
        if cache_key in self._retrieve_cache:
            return self._retrieve_cache[cache_key]

        q = self.embedder.encode_query(query)
        results = self.store.search(q, top_k=top_k)
        enriched: List[Dict[str, str]] = []
        for meta, score in results:
            # Find corresponding text by id
            text = ""
            try:
                # id is source::chunk_i; find first match
                idx = next(i for i, m in enumerate(self._corpus_metas) if m.get("id") == meta.get("id"))
                text = self._corpus_texts[idx]
            except StopIteration:
                text = ""
            enriched.append({
                **meta,
                "score": f"{score:.4f}",
                "text": text,
            })
        
        # Update cache
        if len(self._retrieve_cache) > self._cache_max_size:
            self._retrieve_cache.pop(next(iter(self._retrieve_cache)))
        self._retrieve_cache[cache_key] = enriched
        
        return enriched

    def ask(self, question: str, top_k: int = 4, tone: str | None = None, prefs: Dict[str, str] | None = None, stream: bool = False, conversation_id: Optional[int] = None) -> Union[Dict[str, object], Tuple[Iterator[str], List[Dict[str, str]]]]:
        # Determine previous user message (if any) BEFORE recording current question
        try:
            # Try enhanced memory first
            if hasattr(self.enhanced_memory, 'get_recent'):
                prev_msgs = self.enhanced_memory.get_recent(limit=10)
            else:
                prev_msgs = self.memory.get()
            
            prev_user_text = None
            for m in reversed(prev_msgs):
                if (m.get("role") or "").lower() in ("user", "usuario"):
                    prev_user_text = m.get("content") or ""
                    break
        except Exception:
            prev_user_text = None

        # Retrieve relevant messages from long-term memory using semantic search
        relevant_memory_context = ""
        try:
            if hasattr(self.enhanced_memory, 'get_relevant'):
                relevant_msgs = self.enhanced_memory.get_relevant(question, limit=5, min_importance=0.4)
                if relevant_msgs:
                    memory_lines = []
                    for msg in relevant_msgs:
                        role = msg.get('role', '').capitalize()
                        content = msg.get('content', '')[:200]  # Truncate for context
                        memory_lines.append(f"{role}: {content}")
                    relevant_memory_context = "\n".join(memory_lines)
                    logger.info(f"Retrieved {len(relevant_msgs)} relevant messages from long-term memory")
        except Exception as e:
            logger.warning(f"Error retrieving relevant memory: {e}")

        # --- ADVANCED INTELLIGENCE START ---
        # 1. Detect if a tool is needed
        tool_needed = self.tool_system.detect_tool(question, self.llm)
        if tool_needed:
            logger.info(f"Tool detected: {tool_needed}")
            tool_result = self.tool_system.use_tool(tool_needed, question, self.llm)
            
            # If tool was used successfully, handle the result
            
            # Case A: Direct answer tools (simple facts/calcs)
            if tool_needed in ['calculator', 'datetime', 'system_info']:
                answer = tool_result
                # Save to memory
                try:
                    if hasattr(self.enhanced_memory, 'add'):
                        self.enhanced_memory.add("user", question, conversation_id=conversation_id)
                        self.enhanced_memory.add("assistant", answer, 
                                               metadata={'tool_used': tool_needed},
                                               conversation_id=conversation_id)
                    else:
                        self.memory.add("assistant", answer)
                except Exception as e:
                    logger.warning(f"Failed to save direct answer to memory: {e}")
                
                if stream:
                    def _gen_tool():
                        yield answer
                    return _gen_tool(), []
                return {"answer": answer, "references": []}
            
            # Case B: Context tools (web search, python analysis) -> Synthesize answer
            elif tool_needed in ['web_search', 'python_repl']:
                # Generate a final answer using the tool output as context
                synthesis_prompt = f"""
                Pregunta del usuario: {question}
                
                Herramienta utilizada: {tool_needed}
                Resultado de la herramienta:
                {tool_result}
                
                Instrucción: Usa la información anterior para responder a la pregunta del usuario de forma natural y completa.
                Si el resultado contiene errores, explícalos.
                """
                
                answer = self.llm.chat(prompt=synthesis_prompt, system="Eres un asistente útil que integra información de herramientas.")
                
                # Save to memory
                try:
                    if hasattr(self.enhanced_memory, 'add'):
                        self.enhanced_memory.add("user", question, conversation_id=conversation_id)
                        self.enhanced_memory.add("assistant", answer, 
                                               metadata={'tool_used': tool_needed, 'tool_output': tool_result[:500]},
                                               conversation_id=conversation_id)
                    else:
                        self.memory.add("assistant", answer)
                except Exception as e:
                    logger.warning(f"Failed to save tool synthesis to memory: {e}")

                if stream:
                    def _gen_synth():
                        yield answer
                    return _gen_synth(), []
                return {"answer": answer, "references": []}

        # 2. Detect if complex reasoning (CoT) is needed
        # Simple heuristic: "paso a paso", "explícame cómo", "resuelve", complex math/logic
        is_complex = any(kw in question.lower() for kw in 
                        ['paso a paso', 'step by step', 'analiza', 'resuelve', 'complejo', 'razona'])
        
        if is_complex and not stream: # CoT works best in non-streaming mode for now
            logger.info("Complex reasoning detected, using CoT")
            cot_result = self.cot_reasoner.solve(question, context=relevant_memory_context)
            answer = cot_result['answer']
            full_reasoning = cot_result['reasoning_steps']
            
            # Save to memory with reasoning metadata
            try:
                if hasattr(self.enhanced_memory, 'add'):
                    self.enhanced_memory.add("user", question, conversation_id=conversation_id)
                    self.enhanced_memory.add("assistant", answer, 
                                           metadata={'reasoning': full_reasoning, 'is_cot': True},
                                           conversation_id=conversation_id)
                else:
                    self.memory.add("assistant", answer)
            except Exception as e:
                logger.warning(f"Failed to save CoT answer to memory: {e}")
                
            return {
                "answer": answer,
                "references": [],
                "metadata": {"reasoning": full_reasoning}
            }
        # --- ADVANCED INTELLIGENCE END ---

        # Use Knowledge Graph to enhance retrieval (inspired by "The Reality Weaver")
        kg_context = ""
        if self.knowledge_graph:
            try:
                # Try to find solution paths for problem-like questions
                solution_paths = self.knowledge_graph.find_solution_path(question, max_depth=3)
                if solution_paths:
                    kg_lines = ["CAMINOS DE SOLUCIÓN ENCONTRADOS:"]
                    for i, path in enumerate(solution_paths[:2], 1):  # Top 2 paths
                        kg_lines.append(f"\nCamino {i}:")
                        for step in path.get("path", []):
                            node_info = step.get("node", {})
                            relation = step.get("relation", "")
                            kg_lines.append(f"  {relation.upper()}: {node_info.get('label', '')} - {node_info.get('description', '')[:100]}")
                    kg_context = "\n".join(kg_lines)
                    logger.info(f"Found {len(solution_paths)} solution paths in Knowledge Graph")
                
                # Also find related nodes
                problem_nodes = self.knowledge_graph.find_nodes(question, node_type="problem", limit=3)
                if problem_nodes:
                    related_info = []
                    for node in problem_nodes:
                        related = self.knowledge_graph.get_related_nodes(node.id, direction="out")
                        if related:
                            related_info.append(f"Problema: {node.label}")
                            for target_node, edge in related[:3]:
                                related_info.append(f"  → {edge.relation_type}: {target_node.label}")
                    if related_info:
                        kg_context += "\n\nRELACIONES ENCONTRADAS:\n" + "\n".join(related_info)
            except Exception as e:
                logger.warning(f"Error using Knowledge Graph: {e}")

        # We'll record the current user message into memory after we produce the answer
        retrieved = self.retrieve(question, top_k=top_k)
        # Small-talk / greetings handler
        if self._is_smalltalk(question):
            answer = self._smalltalk_answer(question)
            try:
                if hasattr(self.enhanced_memory, 'add'):
                    self.enhanced_memory.add("user", question, conversation_id=conversation_id)
                    self.enhanced_memory.add("assistant", answer, conversation_id=conversation_id)
                else:
                    self.memory.add("assistant", answer)
            except Exception as e:
                logger.warning(f"Failed to save smalltalk answer to memory: {e}")
            if stream:
                def _gen_st():
                    yield answer
                return _gen_st(), []
            return {"answer": answer, "references": [], "projection": None}
        # Date/time handler
        if self._is_datetime_query(question):
            answer = self._datetime_answer()
            try:
                if hasattr(self.enhanced_memory, 'add'):
                    self.enhanced_memory.add("user", question, conversation_id=conversation_id)
                    self.enhanced_memory.add("assistant", answer, conversation_id=conversation_id)
                else:
                    self.memory.add("assistant", answer)
            except Exception as e:
                logger.warning(f"Failed to save datetime answer to memory: {e}")
            if stream:
                def _gen_dt():
                    yield answer
                return _gen_dt(), []
            return {"answer": answer, "references": [], "projection": None}
        # No corpus available
        if not self._corpus_texts:
            answer = "Aún no tengo información indexada. Usa 'Agregar texto' para cargar contenido y preguntar sobre eso."
            try:
                self.memory.add("user", question)
                self.memory.add("assistant", answer)
            except Exception as e:
                logger.warning(f"Failed to save no corpus answer to memory: {e}")
            if stream:
                def _gen_no_corpus():
                    yield answer
                return _gen_no_corpus(), []
            return {"answer": answer, "references": [], "projection": None}
        context = "\n\n".join([r.get("text", "") for r in retrieved if r.get("text")])
        # Build conversational history from memory (exclude current question) and inject into prompt so the LLM has context
        try:
            mem_messages = self.memory.get()
            history_lines: List[str] = []
            for m in mem_messages:
                role = (m.get("role") or "").lower()
                content = m.get("content") or ""
                if role in ("user", "usuario"):
                    history_lines.append(f"Usuario: {content}")
                elif role in ("assistant", "asistente"):
                    history_lines.append(f"Asistente: {content}")
                elif role == "system":
                    history_lines.append(f"Sistema: {content}")
                else:
                    # generic
                    history_lines.append(f"{role.capitalize()}: {content}")
            memory_text = "\n".join(history_lines).strip()
        except Exception:
            logger.exception("Failed to build memory history; continuing without it")
            memory_text = ""

        # Determine whether the current question is related to the previous user question.
        def _semantic_related(a: Optional[str], b: Optional[str]) -> tuple[bool, float]:
            """Return (related_bool, similarity_score) using embeddings when possible,
            or a simple token-overlap fallback."""
            if not a or not b:
                return True, 1.0
            try:
                # Try embeddings-based similarity
                vecs = self.embedder.encode_texts([a, b])
                # attempt numpy operations if available
                try:
                    import numpy as _np
                    v0 = _np.asarray(vecs[0], dtype=_np.float32)
                    v1 = _np.asarray(vecs[1], dtype=_np.float32)
                    denom = (_np.linalg.norm(v0) * _np.linalg.norm(v1)) + 1e-8
                    sim = float(float(_np.dot(v0, v1)) / denom)
                except Exception as e:
                    logger.warning(f"Failed embeddings-based similarity calculation; falling back: {e}")
                    # vecs may be plain python lists
                    v0 = list(vecs[0])
                    v1 = list(vecs[1])
                    dot = sum(x * y for x, y in zip(v0, v1))
                    import math
                    norm0 = math.sqrt(sum(x * x for x in v0))
                    norm1 = math.sqrt(sum(x * x for x in v1))
                    denom = (norm0 * norm1) + 1e-8
                    sim = float(dot / denom)
                # clamp
                sim = max(min(sim, 1.0), -1.0)
                return (sim >= 0.30, sim)
            except Exception as e:
                logger.warning(f"Failed token-Jaccard similarity calculation; falling back: {e}")
                # fallback: simple token-Jaccard
                try:
                    import re
                    def tokens(s: str):
                        return set(re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (s or "").lower()))
                    t0 = tokens(a)
                    t1 = tokens(b)
                    if not t0 or not t1:
                        return True, 0.0
                    inter = t0 & t1
                    union = t0 | t1
                    j = len(inter) / (len(union) + 1e-9)
                    return (j >= 0.20, float(j))
                except Exception:
                    return True, 0.0

        related, related_score = _semantic_related(prev_user_text, question)
        coherence_note = ""
        if not related:
            coherence_note = (
                f"NOTA_DE_COHERENCIA: La pregunta actual parece no estar relacionada con la anterior (sim={related_score:.2f}). "
                "Responderé de forma independiente y lo indicaré claramente al inicio de la respuesta."
            )
        # If no context found, try Wikipedia fallback
        wiki_used = False
        if not context.strip():
            wiki = fetch_wikipedia_answer(question, lang="es")
            if wiki and wiki.get("extract"):
                wiki_used = True
                context = wiki.get("extract", "")
                # also add as a reference
                retrieved = [{
                    'id': f"wikipedia::{wiki.get('title','')}",
                    'source': f"Wikipedia: {wiki.get('title','')}",
                    'chunk_index': '0',
                    'text': wiki.get('extract',''),
                    'score': '1.0000',
                    'url': wiki.get('url','')
                }]
                # learn: ingest the extract into vector store so future queries retrieve it locally
                try:
                    self.ingest_raw([
                        {'source': f"wikipedia:{wiki.get('title','')}", 'text': wiki.get('extract','')}
                    ], chunk_chars=800, overlap=150)
                except Exception as e:
                    logger.warning(f"Failed to ingest Wikipedia extract: {e}")

        tone_text = {
            'formal': 'Usa un tono formal y profesional.',
            'casual': 'Usa un tono casual y cercano.',
            'neutral': 'Usa un tono neutral y claro.',
        }.get((tone or 'neutral').lower(), 'Usa un tono neutral y claro.')

        extra_prefs = ''
        if prefs:
            try:
                # sintetizar preferencias simples si existen
                likes = prefs.get('likes') or prefs.get('prefer') or ''
                if likes:
                    extra_prefs = f" Ten en cuenta la preferencia del usuario: {likes}."
            except Exception as e:
                logger.warning(f"Failed to process user preferences: {e}")

        system = (
            "Eres un asistente útil. Usa estrictamente el CONTEXTO para responder. "
            "Si la respuesta no está en el contexto, responde: 'No encontré esa información'. "
            + tone_text + extra_prefs
        )
        # If memory is long, attempt to summarize it with LLM to keep prompt concise
        if memory_text and len(memory_text) > 1200:
            try:
                summary = self.llm.summarize(memory_text, max_chars=700)
                memory_text = f"Resumen del historial:\n{summary}"
            except Exception:
                logger.exception("Memory summarization failed; using full memory_text")

        # If the current question is not related, do not inject the conversational history
        if coherence_note:
            # omit memory_text to avoid confusing the LLM with irrelevant history
            memory_text = ""

        # Build references list (numbered) for the LLM to cite
        references_text = ""
        if retrieved:
            ref_lines: List[str] = []
            for i, r in enumerate(retrieved, start=1):
                src = r.get("source") or r.get("id") or ""
                url = r.get("url") or r.get("source_url") or ""
                ref_lines.append(f"[{i}] {src}" + (f" - {url}" if url else ""))
            references_text = "\n".join(ref_lines)

        # Compose final prompt: relevant memory (if any) -> history (if any) -> context -> references -> question
        prompt_parts: List[str] = []
        
        # Add relevant long-term memory context if available
        if relevant_memory_context:
            prompt_parts.append(f"MEMORIA RELEVANTE (conversaciones pasadas):\n{relevant_memory_context}")
        
        if memory_text:
            prompt_parts.append(f"HISTORIAL RECIENTE:\n{memory_text}")
        
        # Add Knowledge Graph context if available (inspired by "The Reality Weaver")
        if kg_context:
            prompt_parts.append(f"GRAFO DE CONOCIMIENTO (relaciones causales):\n{kg_context}")
        
        prompt_parts.append(f"CONTEXTO:\n{context}")
        if references_text:
            prompt_parts.append(f"REFERENCIAS:\n{references_text}")
        prompt_parts.append(f"PREGUNTA:\n{question}")
        prompt_parts.append("Responde de forma breve y precisa en español. Cita las referencias usando [n] si aplican.")
        prompt = "\n\n".join(prompt_parts)

        if self.llm.mode_name in ("openai", "huggingface", "ollama", "local"):
            try:
                if stream:
                    # Return generator immediately, but wrap it to save to memory after completion
                    gen = self.llm.chat(prompt=prompt, system=system, stream=True)
                    if isinstance(gen, str):
                        # Fallback if chat returned string despite stream=True
                        def _g(): 
                            yield gen
                        gen_wrapped = _g()
                    else:
                        gen_wrapped = gen
                    
                    # Wrap generator to collect answer and save to memory
                    def _streaming_wrapper():
                        collected = []
                        try:
                            for chunk in gen_wrapped:
                                collected.append(chunk)
                                yield chunk
                        finally:
                            # Save to memory after streaming completes
                            try:
                                full_answer = "".join(collected)
                                
                                if hasattr(self.enhanced_memory, 'add'):
                                    # Calculate importance
                                    importance = 0.5
                                    if len(question) > 100:
                                        importance += 0.1
                                    
                                    self.enhanced_memory.add(
                                        "user", 
                                        question, 
                                        conversation_id=conversation_id,
                                        importance=min(importance, 1.0)
                                    )
                                    
                                    final_answer = full_answer
                                    if coherence_note:
                                        final_answer = f"Nota: tu pregunta no parece relacionada con la anterior. {full_answer}"
                                    
                                    self.enhanced_memory.add(
                                        "assistant", 
                                        final_answer,
                                        metadata={'streaming': True},
                                        conversation_id=conversation_id,
                                        importance=0.6
                                    )
                                else:
                                    self.memory.add("user", question)
                                    if coherence_note:
                                        full_answer = f"Nota: tu pregunta no parece relacionada con la anterior. {full_answer}"
                                    self.memory.add("assistant", full_answer)
                            except Exception:
                                logger.exception("Failed to save streaming conversation to memory")
                    
                    logger.info(f"Streaming mode activated for question: {question[:50]}...")
                    return _streaming_wrapper(), retrieved
                logger.info(f"Non-streaming mode for question: {question[:50]}...")
                answer = self.llm.chat(prompt=prompt, system=system)
            except Exception:
                logger.exception("LLM chat failed; falling back to extractive answer")
                answer = self._extractive_answer(question, retrieved)
        else:
            answer = self._extractive_answer(question, retrieved)
        # If the LLM returned an obvious fallback/echo or a very short/empty reply,
        # fall back to the extractive answer to avoid repeating the same text.
        try:
            if isinstance(answer, str):
                a_norm = answer.strip()
                # common fallback marker from our LLMClient
                if a_norm.startswith("(fallback)") or len(a_norm) < 20:
                    logger.info("LLM produced fallback/short output; using extractive fallback")
                    answer = self._extractive_answer(question, retrieved)
                # if LLM accidentally echoed the prompt (long substring present), fallback
                elif len(prompt) > 0 and a_norm and (a_norm in prompt or prompt[:80] in a_norm):
                    logger.info("LLM echoed prompt; using extractive fallback")
                    answer = self._extractive_answer(question, retrieved)
        except Exception:
            logger.exception("Failed to validate LLM output; using it as-is")
        # Ensure we record the user's question and the assistant answer in memory
        try:
            # Before saving to memory, attempt to record the run in LangSmith (if configured)
            try:
                if getattr(self.llm, '_langsmith_key', None):
                    try:
                        import uuid
                        rs = None
                        import langsmith  # type: ignore
                        Client = getattr(langsmith, 'Client', None)
                        if Client:
                            client = Client(api_key=getattr(self.llm, '_langsmith_key'))
                            run_id = str(uuid.uuid4())
                            # Build a compact inputs/outputs object
                            inputs = {
                                'question': question,
                                'context_snippet': (context[:1000] + '...') if context else '',
                            }
                            outputs = {
                                'answer': answer if isinstance(answer, str) else str(answer)
                            }
                            try:
                                client.create_run(id=run_id, name=f"chat-run-{run_id[:8]}", inputs=inputs, outputs=outputs, run_type='llm')
                                try:
                                    # try to obtain a human-friendly URL for the run; may not be supported
                                    if hasattr(client, 'get_run_url'):
                                        rs = client.get_run_url(run_id)
                                except Exception:
                                    rs = None
                                # attach reference url to answer metadata by injecting a short note (not to memory content)
                                if rs:
                                    # store run url in a lightweight place in the returned references
                                    if isinstance(retrieved, list):
                                        retrieved.insert(0, {'id': f'langsmith://{run_id}', 'source': 'LangSmith', 'url': rs, 'score': '1.0000', 'text': ''})
                            except Exception:
                                logger.exception("Failed to create LangSmith run")
                    except Exception:
                        logger.debug("LangSmith instrumentation skipped (init failed)", exc_info=True)
            except Exception:
                logger.exception("Unexpected error while trying to record run in LangSmith")

            # Save to enhanced memory with metadata
            try:
                if hasattr(self.enhanced_memory, 'add'):
                    # Calculate importance based on question complexity
                    importance = 0.5
                    if len(question) > 100:
                        importance += 0.1
                    if any(kw in question.lower() for kw in ['importante', 'recordar', 'siempre', 'preferencia']):
                        importance += 0.2
                    
                    self.enhanced_memory.add(
                        "user", 
                        question, 
                        conversation_id=conversation_id,
                        importance=min(importance, 1.0)
                    )
                    
                    # If coherence_note, prepend a short human-friendly note to the assistant's reply
                    final_answer = answer
                    if coherence_note:
                        final_answer = f"Nota: tu pregunta no parece relacionada con la anterior. {answer}"
                    
                    self.enhanced_memory.add(
                        "assistant", 
                        final_answer,
                        metadata={
                            'has_references': len(retrieved) > 0,
                            'wiki_used': wiki_used,
                            'num_references': len(retrieved)
                        },
                        conversation_id=conversation_id,
                        importance=0.6  # Assistant responses slightly more important
                    )
                else:
                    # Fallback to old memory
                    self.memory.add("user", question)
                    if coherence_note:
                        answer = f"Nota: tu pregunta no parece relacionada con la anterior. {answer}"
                    self.memory.add("assistant", answer)
            except Exception:
                logger.exception("Failed to save conversation to memory")
        except Exception:
            logger.exception("Failed to save conversation to memory")

        # Check for Experience Objects in retrieved docs to return as "projection"
        projection = None
        for r in retrieved:
            if r.get('is_experience') == 'true' and r.get('experience_json'):
                try:
                    projection = json.loads(r.get('experience_json'))
                    # Only return the top relevant projection
                    break
                except Exception as e:
                    logger.debug(f"Error loading experience JSON: {e}")

        return {
            "answer": answer,
            "references": retrieved,
            "projection": projection
        }

    def _extractive_answer(self, question: str, contexts: List[Dict[str, str]]) -> str:
        """Build a concise answer by selecting the most relevant sentences from retrieved contexts.

        This is a lightweight heuristic fallback when no LLM is available.
        """
        import re
        from collections import Counter

        def normalize(text: str) -> List[str]:
            tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", text.lower())
            stop = {
                'el','la','los','las','un','una','unos','unas','de','del','a','y','o','u','en','con','por','para','es','son','al','se','su','sus','que','qué','como','cómo','cuando','cuándo','donde','dónde','si','sí','no','lo','le','les','ya','más','menos','muy','esto','esta','estas','estos','ese','esa','eso','esas','esos','también','pero','porque','sobre','entre'
            }
            return [t for t in tokens if t not in stop and len(t) > 1]

        q_terms = set(normalize(question))
        if not q_terms:
            return "No encontré esa información."

        candidate_sentences: List[tuple[float, str]] = []
        for r in contexts:
            text = r.get('text', '') or ''
            # split into sentences
            sentences = re.split(r"(?<=[\.\!\?])\s+", text)
            for s in sentences:
                terms = set(normalize(s))
                if not terms:
                    continue
                overlap = len(q_terms & terms)
                if overlap == 0:
                    continue
                score = overlap / (len(q_terms) ** 0.5 * len(terms) ** 0.5)
                candidate_sentences.append((score, s.strip()))

        if not candidate_sentences:
            return "No encontré esa información."

        # pick top few sentences and assemble a brief answer
        candidate_sentences.sort(key=lambda x: x[0], reverse=True)
        selected = []
        used = set()
        for _, s in candidate_sentences[:8]:
            if s in used:
                continue
            used.add(s)
            selected.append(s)
            if len(selected) >= 3:
                break
        answer = " ".join(selected)
        return answer if answer else "No encontré esa información."

    def _is_smalltalk(self, question: str) -> bool:
        q = (question or "").strip().lower()
        greetings = ["hola", "buenas", "hello", "hi", "hey"]
        return any(q == g or q.startswith(g + " ") for g in greetings)

    def _smalltalk_answer(self, question: str) -> str:
        return "¡Hola! ¿En qué puedo ayudarte? Puedes agregar texto y hacer preguntas sobre eso."

    def _is_datetime_query(self, question: str) -> bool:
        q = (question or "").strip().lower()
        keywords = [
            "hora", "qué hora", "que hora", "qué fecha", "que fecha",
            "fecha", "día", "que dia", "qué día", "hoy", "dia de hoy"
        ]
        return any(k in q for k in keywords)

    def _datetime_answer(self) -> str:
        from datetime import datetime
        import time as _time
        # Map Spanish names manually to avoid system locale dependency
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        now = datetime.now()
        dia_semana = dias[now.weekday()]
        mes_nombre = meses[now.month - 1]
        tz = " ".join([p for p in _time.tzname if p]) or ""
        fecha = f"{dia_semana.capitalize()}, {now.day} de {mes_nombre} de {now.year}"
        hora = now.strftime("%H:%M:%S")
        return f"Hoy es {fecha}. La hora actual es {hora} ({tz})."

    def save_index(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        # Save vector store
        try:
            if hasattr(self.store, 'save'):
                self.store.save(directory)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
        # Save corpus texts and metas
        import json
        data = {
            'texts': self._corpus_texts,
            'metas': self._corpus_metas,
        }
        with open(os.path.join(directory, 'corpus.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def load_index(self, directory: str) -> None:
        # Load vector store if available
        try:
            if hasattr(self.store, 'load'):
                self.store.load(directory)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
        # Load corpus
        import json
        path = os.path.join(directory, 'corpus.json')
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._corpus_texts = data.get('texts', [])
                self._corpus_metas = data.get('metas', [])
            except Exception as e:
                logger.error(f"Failed to load corpus from {path}: {e}")
                self._corpus_texts = []
                self._corpus_metas = []

    def remove_sources(self, patterns: List[str]) -> int:
        """Remove all chunks whose meta['source'] matches any pattern.

        patterns support '*' suffix for prefix matching, e.g., 'wikipedia:*'.
        Rebuilds the vector index from remaining corpus and persists if configured.
        Returns number of removed chunks.
        """
        if not patterns:
            return 0

        def matches(src: str) -> bool:
            for p in patterns:
                if p.endswith('*'):
                    if src.startswith(p[:-1]):
                        return True
                else:
                    if src == p:
                        return True
            return False

        keep_texts: List[str] = []
        keep_metas: List[Dict[str, str]] = []
        removed = 0
        for text, meta in zip(self._corpus_texts, self._corpus_metas):
            src = meta.get('source', '')
            if matches(src):
                removed += 1
            else:
                keep_texts.append(text)
                keep_metas.append(meta)

        # Rebuild store from kept items
        self._corpus_texts = keep_texts
        self._corpus_metas = keep_metas
        # Refit embedder (only if backend requires fitting, e.g., TF-IDF)
        X = None
        try:
            if keep_texts:
                if getattr(self.embedder, "backend_name", None) == "tfidf":
                    # TF-IDF needs a refit on the full corpus
                    self.embedder.fit_corpus(keep_texts)
                # In all cases we need embeddings/representations for the store
                X = self.embedder.encode_texts(keep_texts)
            else:
                X = None
        except Exception:
            logger.exception("Failed to refit/embed texts while rebuilding index after remove_sources")
            X = None

        # Recreate store
        try:
            from .vector_store import FaissVectorStore, InMemoryVectorStore  # reimport types
            # keep same type
            self.store = FaissVectorStore() if hasattr(self.store, 'save') and type(self.store).__name__ == 'FaissVectorStore' else InMemoryVectorStore()
        except Exception as e:
            logger.error(f"Failed to recreate store after removing sources: {e}")

        if X is not None and len(keep_metas) == (X.shape[0] if hasattr(X, 'shape') else len(keep_texts)):
            self.store.add(X, keep_metas)  # type: ignore[arg-type]

        if self._storage_dir:
            self.save_index(self._storage_dir)
        return removed