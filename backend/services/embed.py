import os
from google import genai

# create a client object to connect to the Gemini API using your API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# use gemini-embedding-001 that outputs a 3072-dimension vector
EMBED_MODEL = os.getenv("EMBEDDING_MODEL")


"""
Convert a piece of text into an embedding vector.
An embedding is a list of 3072 floats that represents the *meaning* of the text.
Texts with similar meaning produce vectors that are close together — which is
what lets Qdrant find "similar" style principles or past outfits.

@param texts: a list of strings, each embedded independently
@return: a list of vectors — one 3072-float vector per input text,
         in the same order as the input
"""
def embed_texts(texts: list[str]) -> list[list[float]]:
    response = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
    )
    # one embedding per input text — return all their .values
    return [e.values for e in response.embeddings]


"""
Convenience wrapper: embed a single string.
@param text: the text to embed
@return: one 3072-float vector
"""
def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]