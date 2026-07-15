"""Builds the canonical embedding *text* for a KnowledgeDocument and turns a
batch of documents into vectors via an EmbeddingProvider.

Only the Knowledge Index is used. Exactly the allowed KnowledgeDocument fields are
embedded — never raw PDF text, parser output, or LLM-generated metadata.
"""

from __future__ import annotations

from backend.compiler.constants import compute_checksum
from backend.retrieval.embedding.provider import EmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument

# The exact, ordered fields embedded per document. Frozen in Phase 3.35 by a
# BGE-M3 ablation: the lean, label-free "name -> aliases -> definitions" form beat
# every alternative on all three subjects. Adding field labels, metadata
# prefixes, examples/related/prerequisites, truncating definitions, or reordering
# either reduced quality or failed to improve it consistently across subjects.
# See docs/phase_3_35_embedding_representation_report.md.
_EMBEDDING_FIELDS: tuple[str, ...] = ("name", "aliases", "definition_texts")


def document_text(document: KnowledgeDocument) -> str:
    """Compose the deterministic text embedded for a document.

    Representation: concept name, then aliases, then definitions — one line each,
    no field labels. Only the Knowledge Index is used; never PDF text, parser
    output, or LLM-generated metadata.
    """
    name = document.name.strip()
    aliases = " ".join(a.strip() for a in document.aliases if a.strip())
    definitions = " ".join(d.strip() for d in document.definition_texts if d.strip())
    return "\n".join(part for part in (name, aliases, definitions) if part)


def document_checksum(document: KnowledgeDocument, provider: EmbeddingProvider) -> str:
    """Content checksum tying a document's embedding text to a provider/model/dim.

    Any change to the embed-able fields, the provider, the model, or the dimension
    changes the checksum, which is what drives incremental rebuilds.
    """
    return compute_checksum(
        document_text(document),
        provider.provider_id,
        provider.model_id,
        provider.dimension,
    )


class EmbeddingBuilder:
    """Stateless transform: KnowledgeDocuments -> {concept_id: vector}."""

    def vectors(
        self,
        documents: list[KnowledgeDocument],
        provider: EmbeddingProvider,
    ) -> dict[str, list[float]]:
        """Embed every document. Incremental reuse is handled by EmbeddingIndex."""
        if not documents:
            return {}
        texts = [document_text(doc) for doc in documents]
        embeddings = provider.embed_documents(texts)
        return {doc.concept_id: vec for doc, vec in zip(documents, embeddings)}
