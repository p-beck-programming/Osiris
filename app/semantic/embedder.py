from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = SentenceTransformer(MODEL_NAME)


def embed_text(text: str):
    return _model.encode(
        text,
        normalize_embeddings=True
    )
