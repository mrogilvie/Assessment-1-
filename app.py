from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader


ROOT = Path(__file__).parent
DEFAULT_PDF = ROOT / "Clause-Notes-Residential-Parks-Bill-2026 copy.pdf"
CHROMA_DIR = ROOT / ".chroma"
COLLECTION_NAME = "residential-parks-bill"

load_dotenv(ROOT / ".env")


def get_openai_api_key() -> str | None:
    """Read the key from the environment or Streamlit secrets."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def split_text(text: str) -> list[str]:
    """Normalize extracted text and return one retrieval chunk per paragraph."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", paragraph).strip() for paragraph in paragraphs if paragraph.strip()]


def read_pdf(pdf_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    metadata: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        for paragraph_number, paragraph in enumerate(split_text(page.extract_text() or ""), start=1):
            chunks.append(paragraph)
            metadata.append({"page": page_number, "paragraph": paragraph_number})
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
    return [
        {
            "text": text,
            "page": metadata.get("page", "?"),
            "paragraph": metadata.get("paragraph", "?"),
        }
        for text, metadata in zip(documents, metadatas)
    ]


def answer_with_openai(
    question: str, sources: list[dict[str, Any]], model: str, detail: str
) -> str | None:
    api_key = get_openai_api_key()
    if not api_key:
        return None

    context = "\n\n".join(
        f"[Page {source['page']}, Paragraph {source['paragraph']}] {source['text']}"
        for source in sources[:5]
    )
    word_limit = {"Concise": 120, "Balanced": 250, "Detailed": 450}[detail]
    prompt = (
        "Summarize and synthesize the supplied document excerpts; do not copy them "
        "or list them one after another. Combine overlapping points, remove repetition, "
        "and explain the practical meaning in plain language. Answer the question using "
        "only the supplied document excerpts. Be specific and answer the exact question "
        f"asked. Start with the direct answer, then add relevant supporting detail. Use at most {word_limit} "
        "words and cite relevant page and paragraph locations in square brackets, "
        "such as [Page 4, Paragraph 2]. Do not repeat the "
        "question or discuss your process. "
        "If the excerpts do not contain the answer, say: 'The supplied PDF does not "
        "provide enough information to answer this.'\n\n"
        f"EXCERPTS:\n{context}\n\nQUESTION: {question}"
    )
    response = OpenAI(api_key=api_key).chat.completions.create(
        model=model,
        temperature=0.1,
        max_tokens=650 if detail == "Detailed" else 400,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise legal-document assistant. Summarize the supplied "
                    "Residential Parks Bill notes without adding outside knowledge."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def fallback_answer(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "No relevant passage was found in the PDF."
    source = sources[0]
    excerpt = source["text"][:600].rstrip()
    return (
        "OpenAI synthesis is unavailable. The most relevant passage is:\n\n"
        f"**Page {source['page']}, Paragraph {source['paragraph']}**\n{excerpt}"
    )


st.set_page_config(page_title="Residential Parks Bill", page_icon="📄", layout="wide")
st.title("Residential Parks Bill assistant")
st.caption("Ask questions about the supplied clause notes. Answers are grounded in the PDF.")

with st.sidebar:
    st.header("Settings")
    retrieval_count = st.slider("Retrieved passages", min_value=1, max_value=6, value=4)
    answer_detail = st.radio("Answer detail", ["Concise", "Balanced", "Detailed"], index=1)
    model = st.text_input("OpenAI model", value="gpt-4o-mini")
    has_key = bool(get_openai_api_key())
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
                answer = answer_with_openai(question, sources, model, answer_detail) or fallback_answer(sources)
            except Exception as error:
                answer = f"I could not generate the model response: {error}\n\n{fallback_answer(sources)}"
            st.markdown(answer)
            with st.expander("Retrieved passages"):
                for source in sources:
                    st.markdown(
                        f"**Page {source['page']}, Paragraph {source['paragraph']}**\n\n"
                        f"{source['text']}"
                    )
    st.session_state.messages.append({"role": "assistant", "content": answer})