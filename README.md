# Residential Parks Bill chatbot

A Streamlit RAG chatbot that indexes the supplied PDF with ChromaDB and retrieves
the most relevant passages for each question.

## Utilise the copilot AI chatbot to assist to build

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

Alternatively, create `.streamlit/secrets.toml` locally and add:

```toml
OPENAI_API_KEY = "your-key"
```

Do not commit `secrets.toml` or share the key. Revoke any key that has been
posted in chat, source code, screenshots, or GitHub.

## Answer ratings

Each assistant answer has thumbs-up and thumbs-down controls. Ratings are saved
locally in `ratings.sqlite3`, one vote per answer; a user can change their vote.
Aggregate vote totals appear below the chat input.
Only the rating and timestamp are stored, not the question, answer, or user
identity. The database is ignored by Git. For a multi-instance deployment, use a
shared database instead of a local SQLite file.

ChromaDB stores its local index in `.chroma/`. The supplied PDF is automatically
re-indexed when its extracted chunk count changes.
## LLM answers now enabled streamlit api key working

## testing with questions and checking answers against the hard copy Clause Notes document (see powerpoint presentation). Questions being tested are "Are there penalties?, "which clauses contain penalties?" and "how many clauses are there in the bill?". 

## noting when using the GitHUB side bar chatbot to direct code it appears in appy.py but does not update Readme file

## would be helpful to have somem sort of user rating system so the app can be improved over time

## adding widget streamlit 1.64.0, attaching stable ID and thumbs widget, ran python -m py_compile

## lets add some personality and colour

## can i change the avatars? 🦆

## update the colours and background of the app via streamlit app themes

## lets get a logo onto the site - using chat gpt 5 to design an image of a duck with a bow on its bill

## lets use the duck bill logo as the question avatar

## Google tells me Dracula is the coolest theme. Lets try that

## hard to see the logo need to increse its size

## more widgets - clear chat button?

## now Im trying to change the opening para to say what BillBow is about 
## need to get my contact details on there somehow

## download answer button too