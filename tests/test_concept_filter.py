from backend.compiler.models import Book, EducationalIR, EducationalObject, Subject
from backend.semantic.concepts.concept_models import Concept, ConceptIndex, ConceptReference
from backend.semantic.concepts.concept_filter import ConceptFilter, ConceptStatus

def test_concept_filter_rejection_long_sentence():
    ir = EducationalIR(
        book=Book(id="book.1", title="Test", subject="mathematics", source_pdf="test.pdf", page_count=1),
        formulas=[], tables=[], figures=[]
    )
    ir.book.objects.append(EducationalObject(id="obj.1", type="paragraph", text="This is a long sentence that should not be a concept.", reading_order=1, page=1, subject="mathematics", book="Test", confidence=1.0))
    
    index = ConceptIndex(book_id="book.1", concepts=[], references=[], unlinked_object_ids=[])
    concept = Concept(id="c.1", name="This is a long sentence that should not be a concept.", subject="mathematics", book="Test", chapter="1", metadata={"source_type": "paragraph"})
    index.concepts.append(concept)
    index.references.append(ConceptReference(concept_id="c.1", object_id="obj.1", object_type="paragraph", link_reason="title_match"))
    
    filter_engine = ConceptFilter()
    filtered = filter_engine.filter(index, ir)
    assert len(filtered.concepts) == 0

def test_concept_filter_acceptance_valid_concept():
    ir = EducationalIR(
        book=Book(id="book.1", title="Test", subject="mathematics", source_pdf="test.pdf", page_count=1),
        formulas=[], tables=[], figures=[]
    )
    ir.book.objects.append(EducationalObject(id="obj.1", type="definition", text="Definition: Electric Field", reading_order=1, page=1, subject="mathematics", book="Test", confidence=1.0))
    
    index = ConceptIndex(book_id="book.1", concepts=[], references=[], unlinked_object_ids=[])
    concept = Concept(id="c.1", name="Electric Field", subject="mathematics", book="Test", chapter="1", definition_ids=["obj.1"], metadata={"source_type": "definition"})
    index.concepts.append(concept)
    index.references.append(ConceptReference(concept_id="c.1", object_id="obj.1", object_type="definition", link_reason="heading_match"))
    
    filter_engine = ConceptFilter()
    filtered = filter_engine.filter(index, ir)
    assert len(filtered.concepts) == 1
    assert filtered.concepts[0].name == "Electric Field"

def test_concept_filter_rejection_stop_words():
    ir = EducationalIR(
        book=Book(id="book.1", title="Test", subject="mathematics", source_pdf="test.pdf", page_count=1),
        formulas=[], tables=[], figures=[]
    )
    ir.book.objects.append(EducationalObject(id="obj.1", type="paragraph", text="why is it so", reading_order=1, page=1, subject="mathematics", book="Test", confidence=1.0))
    
    index = ConceptIndex(book_id="book.1", concepts=[], references=[], unlinked_object_ids=[])
    concept = Concept(id="c.1", name="why is it so", subject="mathematics", book="Test", chapter="1", metadata={"source_type": "paragraph"})
    index.concepts.append(concept)
    index.references.append(ConceptReference(concept_id="c.1", object_id="obj.1", object_type="paragraph", link_reason="title_match"))
    
    filter_engine = ConceptFilter()
    filtered = filter_engine.filter(index, ir)
    assert len(filtered.concepts) == 0

def test_concept_filter_rejection_punctuation():
    ir = EducationalIR(
        book=Book(id="book.1", title="Test", subject="mathematics", source_pdf="test.pdf", page_count=1),
        formulas=[], tables=[], figures=[]
    )
    ir.book.objects.append(EducationalObject(id="obj.1", type="paragraph", text="1.2.3 ***", reading_order=1, page=1, subject="mathematics", book="Test", confidence=1.0))
    
    index = ConceptIndex(book_id="book.1", concepts=[], references=[], unlinked_object_ids=[])
    concept = Concept(id="c.1", name="1.2.3 ***", subject="mathematics", book="Test", chapter="1", metadata={"source_type": "paragraph"})
    index.concepts.append(concept)
    index.references.append(ConceptReference(concept_id="c.1", object_id="obj.1", object_type="paragraph", link_reason="title_match"))
    
    filter_engine = ConceptFilter()
    filtered = filter_engine.filter(index, ir)
    assert len(filtered.concepts) == 0
