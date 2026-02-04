# Chat IA — Prototipo

Frontend: Futuristic single-page app served by FastAPI.

Quick start (Windows PowerShell):

```powershell
# install deps
py -3 -m pip install -r requirements.txt
# run server
py -3 -m uvicorn chat_ai.serve:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ in your browser.

Notes:
- The /chat endpoint uses the RAG pipeline; currently the generator is a stub unless `OPENAI_API_KEY` or `HF_API_KEY` is set.
- The UI uses a streaming endpoint `/chat_stream` to show progressive output.
- Use `run_server.ps1` for a one-line run on Windows.
