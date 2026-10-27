import numpy as np

from src.core.config import EmbeddingSettings


class BGEM3Embedder:
    def __init__(self, settings: EmbeddingSettings):
        from FlagEmbedding import BGEM3FlagModel

        self.settings = settings
        self.model = BGEM3FlagModel(settings.model, use_fp16=settings.use_fp16)

    def encode(self, texts: list[str]) -> np.ndarray:
        output = self.model.encode(texts, max_length=self.settings.max_length)
        return np.asarray(output["dense_vecs"], dtype=np.float32)
