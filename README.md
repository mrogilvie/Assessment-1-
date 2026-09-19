# Residential Parks Bill chatbot

A Streamlit RAG chatbot that indexes the supplied PDF with ChromaDB and retrieves
the most relevant passages for each question.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app works in retrieval-only mode without credentials. To enable concise,
synthesized answers, export an OpenAI key before starting Streamlit:

```bash
export OPENAI_API_KEY="your-key"
streamlit run app.py
```

ChromaDB stores its local index in `.chroma/`. The supplied PDF is automatically
re-indexed when its extracted chunk count changes.
