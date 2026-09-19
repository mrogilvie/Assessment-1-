from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from pypdf import PdfReader


ROOT = Path(__file__).parent
DEFAULT_PDF = ROOT / "Clause-Notes-Residential-Parks-Bill-2026 copy.pdf"
CHROMA_DIR = ROOT / ".chroma"
COLLECTION_NAME = "residential-parks-bill"


def split_text(text: str) -> list[str]:
    """Normalize extracted text and return one retrieval chunk per paragraph."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", paragraph).strip() for paragraph in paragraphs if paragraph.strip()]


def read_pdf(pdf_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    metadata: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        for chunk_number, chunk in enumerate(split_text(page.extract_text() or "")):
            chunks.append(chunk)
            metadata.append({"page": page_number, "chunk": chunk_number})
    return chunks, metadata


@st.cache_resource(show_spinner=False)
def get_collection(pdf_path: str, pdf_hash: str):
    texts, metadata = read_pdf(Path(pdf_path))
    if not texts:
        raise ValueError("No selectable text was found in the PDF.")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    existing = collection.get(include=[])
    collection_hash = (collection.metadata or {}).get("source_hash")
    if len(existing["ids"]) != len(texts) or collection_hash != pdf_hash:
        client.delete_collection(COLLECTION_NAME)
        collection = client.create_collection(COLLECTION_NAME, metadata={"source_hash": pdf_hash})
        document_hash = pdf_hash[:8]
        ids = [f"{document_hash}-{index}" for index in range(len(texts))]
        collection.add(ids=ids, documents=texts, metadatas=metadata)
    return collection, len(texts)


def retrieve(collection: Any, question: str, count: int) -> list[dict[str, Any]]:
    available = collection.count()
    if available == 0:
        return []
    result = collection.query(query_texts=[question], n_results=min(count, available))
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    return [{"text": text, "page": metadata.get("page", "?")} for text, metadata in zip(documents, metadatas)]


def answer_with_openai(question: str, sources: list[dict[str, Any]], model: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    from openai import OpenAI

    context = "\n\n".join(f"[Page {source['page']}] {source['text']}" for source in sources)
    prompt = (
        "Answer the question using only the supplied document excerpts. "
        "If the excerpts do not contain the answer, say so clearly. "
        "Keep the response concise and cite page numbers in square brackets.\n\n"
        f"EXCERPTS:\n{context}\n\nQUESTION: {question}"
    )
    response = OpenAI(api_key=api_key).chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a careful legal-document assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def fallback_answer(sources: list[dict[str, Any]]) -> str:
    return (
        "I found these relevant passages in the PDF. Add `OPENAI_API_KEY` to generate a "
        "synthesized answer.\n\n" + "\n\n".join(
            f"**Page {source['page']}**\n{source['text']}" for source in sources
        )
    )


st.set_page_config(page_title="Residential Parks Bill", page_icon="📄", layout="wide")
st.title("Residential Parks Bill assistant")
st.caption("Ask questions about the supplied clause notes. Answers are grounded in the PDF.")

with st.sidebar:
    st.header("Settings")
    retrieval_count = st.slider("Retrieved passages", min_value=1, max_value=6, value=4)
    model = st.text_input("OpenAI model", value="gpt-4o-mini")
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    st.info("LLM answers enabled." if has_key else "Retrieval-only mode. Set OPENAI_API_KEY for synthesized answers.")

if not DEFAULT_PDF.exists():
    st.error(f"PDF not found: {DEFAULT_PDF.name}")
    st.stop()

pdf_hash = hashlib.sha256(DEFAULT_PDF.read_bytes()).hexdigest()
try:
    collection, chunk_count = get_collection(str(DEFAULT_PDF), pdf_hash)
except Exception as error:
    st.error(f"Could not index the PDF: {error}")
    st.stop()

st.caption(f"Indexed {chunk_count} passages from `{DEFAULT_PDF.name}`")

if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about a clause, obligation, or definition...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    sources = retrieve(collection, question, retrieval_count)
    with st.chat_message("assistant"):
        with st.spinner("Searching the bill..."):
            try:
                answer = answer_with_openai(question, sources, model) or fallback_answer(sources)
            except Exception as error:
                answer = f"I could not generate the model response: {error}\n\n{fallback_answer(sources)}"
            st.markdown(answer)
            with st.expander("Retrieved passages"):
                for source in sources:
                    st.markdown(f"**Page {source['page']}**\n\n{source['text']}")
    st.session_state.messages.append({"role": "assistant", "content": answer})
