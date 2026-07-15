"""Load compiled NCERT data into LlamaIndex documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from llama_index.core import Document


class NCERTDocumentLoader:
    """Load compiled NCERT educational data into LlamaIndex documents."""

    def __init__(self, compiled_dir: str | Path = "data/compiled"):
        self._compiled_dir = Path(compiled_dir)

    def load_all(self) -> list[Document]:
        """Load all compiled books into documents."""
        documents = []

        for subject_dir in self._compiled_dir.iterdir():
            if not subject_dir.is_dir():
                continue

            for book_dir in subject_dir.iterdir():
                if not book_dir.is_dir():
                    continue

                docs = self._load_book(book_dir)
                documents.extend(docs)

        return documents

    def _load_book(self, book_dir: Path) -> list[Document]:
        """Load a single compiled book."""
        documents = []
        ci_path = book_dir / "concept_index.json"
        ir_path = book_dir / "educational_ir.json"

        if not ci_path.exists():
            return documents

        ci_data = json.loads(ci_path.read_text())

        # Load IR for object details
        ir_data = {}
        if ir_path.exists():
            ir_data = json.loads(ir_path.read_text())

        # Build object lookup
        object_map = {}
        for obj in ir_data.get("book", {}).get("objects", []):
            object_map[obj["id"]] = obj

        # Convert concepts to documents
        for concept in ci_data.get("concepts", []):
            docs = self._concept_to_documents(concept, object_map)
            documents.extend(docs)

        return documents

    def _concept_to_documents(
        self, concept: dict, object_map: dict
    ) -> list[Document]:
        """Convert a concept to multiple LlamaIndex documents."""
        documents = []
        concept_id = concept.get("id", "")
        concept_name = concept.get("name", "")
        subject = concept.get("subject", "")
        chapter = concept.get("chapter", "")

        metadata = {
            "concept_id": concept_id,
            "concept_name": concept_name,
            "subject": subject,
            "chapter": chapter,
        }

        # Definition document
        definitions = []
        for def_id in concept.get("definition_ids", []):
            obj = object_map.get(def_id)
            if obj and obj.get("text"):
                definitions.append(obj["text"])

        if definitions:
            doc_text = f"Definition of {concept_name}: " + " ".join(definitions)
            documents.append(Document(
                text=doc_text,
                metadata={**metadata, "doc_type": "definition"},
            ))

        # Example documents
        examples = []
        for ex_id in concept.get("example_ids", [])[:5]:  # Limit to 5
            obj = object_map.get(ex_id)
            if obj and obj.get("text"):
                examples.append(obj["text"])

        if examples:
            doc_text = f"Examples of {concept_name}: " + " ".join(examples)
            documents.append(Document(
                text=doc_text,
                metadata={**metadata, "doc_type": "example"},
            ))

        # Formula document
        formulas = []
        for form_id in concept.get("formula_ids", []):
            obj = object_map.get(form_id)
            if obj and obj.get("latex"):
                formulas.extend(obj["latex"])

        if formulas:
            doc_text = f"Formulas for {concept_name}: " + " ".join(formulas)
            documents.append(Document(
                text=doc_text,
                metadata={**metadata, "doc_type": "formula"},
            ))

        # Main concept document (combined)
        all_text = []
        if definitions:
            all_text.append("Definitions: " + " ".join(definitions))
        if examples:
            all_text.append("Examples: " + " ".join(examples[:2]))
        if formulas:
            all_text.append("Formulas: " + " ".join(formulas))

        if all_text:
            doc_text = f"{concept_name} ({subject}, {chapter}): " + " ".join(all_text)
            documents.append(Document(
                text=doc_text,
                metadata=metadata,
            ))

        return documents

    def load_for_subject(self, subject: str) -> list[Document]:
        """Load documents for a specific subject."""
        all_docs = self.load_all()
        return [doc for doc in all_docs if doc.metadata.get("subject") == subject]
