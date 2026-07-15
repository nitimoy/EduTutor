"""RAG engine using hybrid retrieval (BM25F + Qdrant semantic) with NCERT-only grounding."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from backend.v2.core.concept_graph import ConceptGraph
from backend.v2.core.session_manager import SessionManager, Session
from backend.v2.core.hybrid_retriever import HybridRetriever
from backend.v2.core.cache import TTLCache, RateLimiter, SessionCleanup, make_cache_key
from backend.v2.core.formula_preprocessor import formula_to_natural_language, get_formula_description


class IntentResolver:
    """Uses the LLM to understand student intent from conversation context.

    Instead of regex patterns, this asks the LLM to interpret what the student
    really means given the conversation history.
    """

    SYSTEM_PROMPT = """You convert student messages into search queries for a textbook search engine.

RULES:
1. Replace ALL pronouns (them, it, that, this, those, he, she) with the ACTUAL concept name from history
2. Replace vague words (the thing, the stuff, that part) with the actual concept name
3. Keep the query focused on the educational concept
4. Return ONLY the search query, nothing else

EXAMPLES:
History: "What is a matrix?"
  Student: "another example" → "matrix examples"
  Student: "multiply two of them" → "matrix multiplication"
  Student: "what about the transpose thing" → "transpose of matrix"
  Student: "how do I calculate it" → "matrix calculation"
  Student: "show me a worked example" → "worked example of matrix"

History: "What is entropy?"
  Student: "how does this relate to enthalpy" → "entropy and enthalpy relationship"
  Student: "explain it simply" → "entropy explained simply"

History: "Explain Newton's second law"
  Student: "I don't get it" → "Newton's second law explanation"
  Student: "give me an example" → "Newton's second law example"

History: "What are derivatives?"
  Student: "skip to integrals" → "integrals"
  Student: "what's next" → "next topic after derivatives"

NO HISTORY:
  Student: "What is a matrix?" → "What is a matrix?"
"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import openai
            from backend.api.config import ServiceConfig
            config = ServiceConfig()
            self._client = openai.OpenAI(
                base_url=config.base_url or "https://api.cerebras.ai/v1",
                api_key=config.api_key,
            )
        return self._client

    def resolve(self, query: str, session: Session, intent_cache: Optional[TTLCache] = None) -> str:
        """Resolve ambiguous follow-up queries using LLM + session context.

        Four-stage approach:
        1. Formula-to-natural-language preprocessing (for better embedding)
        2. Pattern detection for math notation (matrices, equations, etc.)
        3. Pronoun/reference replacement using session.active_concept
        4. LLM-based intent resolution for complex cases (with caching)
        """
        q = query.lower().strip()

        # Stage 0: Preprocess formulas to natural language for better embedding
        # Only apply preprocessing if it doesn't change the query significantly
        # (e.g., just symbol replacement, not full concept replacement)
        preprocessed = formula_to_natural_language(query)
        # Don't return early if preprocessed - let other stages handle it
        # The preprocessing is for embedding, not for intent resolution

        # Stage 0.5: Handle follow-up queries using session context
        # If query is vague and we have an active concept, resolve it
        if session.active_concept and len(query.split()) <= 8:
            follow_up_patterns = [
                'show me', 'give me', 'solve', 'solution', 'answer',
                'explain', 'what is', 'tell me', 'help me',
                'another', 'more', 'example', 'hint',
            ]
            if any(pattern in q for pattern in follow_up_patterns):
                # Check if this is a request for solution (vs just explanation)
                if any(word in q for word in ['solution', 'solve', 'answer', 'show me the']):
                    # Student wants the full solution
                    return f"EXERCISE SOLUTION: {session.active_concept}"
                else:
                    # Student wants explanation/hints
                    return f"{session.active_concept} explanation"

        # Stage 1: Detect math notation patterns and resolve to proper queries
        resolved = self._detect_math_patterns(query)
        if resolved != query:
            return resolved

        # Stage 2: Quick pronoun replacement using active concept
        if session.active_concept:
            resolved = self._replace_pronouns(query, session.active_concept)
            if resolved != query:
                return resolved

        # Check intent cache
        cache_key = make_cache_key(query, session.active_subject)
        if intent_cache:
            cached = intent_cache.get(cache_key)
            if cached:
                return cached

        # Stage 2: LLM-based resolution for short/ambiguous queries
        if not session.turns or len(query.split()) > 8:
            return query

        # Build conversation context
        history_lines = []
        for turn in session.turns[-3:]:  # Last 3 turns
            history_lines.append(f"Student: {turn.query}")
            history_lines.append(f"Tutor: {turn.answer[:150]}...")
        history_text = "\n".join(history_lines)

        prompt = f"""Conversation history:
{history_text}

Student's new message: "{query}"

What is the student really asking about? Return only the search query."""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model="gpt-oss-120b",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=100,
            )
            resolved = response.choices[0].message.content.strip()

            # Sanity check
            if not resolved or len(resolved) < 3:
                return query

            # Cache the resolved intent
            if intent_cache:
                intent_cache.set(cache_key, resolved, ttl=3600)

            return resolved

        except Exception:
            return query

    def _detect_math_patterns(self, query: str) -> str:
        """Detect math notation patterns from PDF copy-paste and resolve to queries.

        Handles:
        - Exercise detection: differential equations with initial conditions → guided solving
        - Chapter queries: "chapter 13 of math" → lookup chapter topics
        - Flat matrix notation: "2 4 -1 2" → "matrix operations"
        - Determinant queries: "find determinant of 3 1 2 3" → "determinant of matrix"
        - Matrix operations: "multiply these matrices" → "matrix multiplication"
        - Chemical formulas: "H2O + NaOH" → "chemical reactions"
        - Physics formulas: "F = ma" → "Newton's second law"
        - Calculus: "integrate x^2" → "integration"
        - Specific formulas: "∆ = a11 A21 + ..." → "cofactor expansion"
        """
        q = query.lower().strip()

        # Detect exercise problems (differential equations with initial conditions)
        # Pattern: dy/dx notation + initial conditions (y = N when x = M)
        is_exercise = (
            ('dy' in q and 'dx' in q) or  # dy/dx notation
            ('differential equation' in q) or
            (re.search(r'y\s*=\s*\d+.*x\s*=\s*\d+', q))  # Initial conditions
        )
        if is_exercise:
            # This is an exercise problem - return with guided solving flag
            return f"EXERCISE: {query}"

        # Detect chapter-based queries: "chapter 13 of math", "what's in chapter 7", etc.
        chapter_match = re.search(r'chapter\s+(\d+)', q)
        if chapter_match:
            chapter_num = int(chapter_match.group(1))
            # Determine subject
            subject = None
            if 'math' in q:
                subject = 'mathematics'
            elif 'physics' in q:
                subject = 'physics'
            elif 'chemistry' in q:
                subject = 'chemistry'

            # Look up chapter topics
            from backend.v2.core.chapter_index import get_chapter_index
            index = get_chapter_index()

            if subject:
                data = index.get_chapter_by_number(subject, chapter_num)
            else:
                # Search all subjects
                for s in ['mathematics', 'physics', 'chemistry']:
                    data = index.get_chapter_by_number(s, chapter_num)
                    if data:
                        subject = s
                        break

            if data:
                # Return a query that will find topics in this chapter
                topics = data.get("concepts", [])[:5]
                if topics:
                    return f"topics in {data['chapter']} of {subject}: {', '.join(topics)}"
                else:
                    return f"{data['chapter']} of {subject}"

        # Detect specific formula patterns and resolve to concepts
        formula_patterns = [
            (r'[∆δ]\s*=\s*a\s*11\s*A\s*21', "cofactor expansion determinant"),
            (r'[∆δ]\s*=\s*a\s*11\s*A\s*11', "determinant expansion cofactors"),
            (r'a\s*\d+\s*A\s*\d+', "cofactor expansion determinant"),
            (r'det\s*\(', "determinant of matrix"),
            (r'\|.*\|', "determinant of matrix"),
            (r'A\s*=\s*\[', "matrix"),
            (r'B\s*=\s*\[', "matrix"),
        ]
        for pattern, concept in formula_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return concept

        # Detect flat matrix notation (numbers with spaces/tabs, possibly negative)
        # Pattern: 2+ numbers that could form a matrix
        # Exclude non-matrix contexts that happen to have numbers
        exclude_keywords = [
            # Calculus
            'integral', 'integrate', 'derivative', 'differentiate', 'partial fraction',
            'antiderivative', 'limit', 'sum', 'differential equation', 'dy/dx',
            # Chemistry
            'reaction', 'equation', 'balance', 'acid', 'base', 'ph', 'molecule',
            # Physics
            'force', 'velocity', 'acceleration', 'energy', 'momentum', 'current',
            'voltage', 'resistance', 'pressure', 'temperature',
            # General
            'chapter', 'section', 'exercise', 'problem', 'question', 'example',
        ]
        is_excluded = any(kw in q for kw in exclude_keywords)

        # Also check for matrix-specific keywords to be sure
        matrix_keywords = ['matrix', 'matrices', 'determinant', 'transpose', 'inverse',
                          'adjoint', 'cofactor', 'minor', 'row matrix', 'column matrix',
                          'square matrix', 'diagonal matrix', 'scalar matrix']
        has_matrix_keyword = any(kw in q for kw in matrix_keywords)

        numbers = re.findall(r'-?\d+\.?\d*', query)
        if len(numbers) >= 4 and len(query.split()) <= 20 and not is_excluded and has_matrix_keyword:
            # Check if there are keywords indicating math operation
            if any(word in q for word in ['determinant', 'det', 'find det']):
                return f"determinant of a matrix"
            elif any(word in q for word in ['multiply', 'product', 'times']):
                return f"matrix multiplication"
            elif any(word in q for word in ['add', 'sum', 'plus']):
                return f"matrix addition"
            elif any(word in q for word in ['inverse', 'adjoint', 'transpose']):
                return f"matrix {word}"
            elif any(word in q for word in ['solve', 'evaluate', 'compute', 'calculate']):
                return f"matrix operations example"
            else:
                # Just numbers - likely a matrix problem
                return f"matrix operations example"

        # Detect chemical formulas (only if they look like actual formulas, not words)
        # Must have 2+ capital letters with numbers or charges, OR be a known formula
        # Also require chemistry context keywords
        known_formulas = ['H2O', 'CO2', 'NaCl', 'NaOH', 'HCl', 'H2SO4', 'NH3', 'CH4', 'C2H5OH']
        chemistry_context = ['reaction', 'equation', 'balance', 'acid', 'base', 'ph',
                           'molecule', 'compound', 'element', 'bond', 'solution']
        has_chemistry_context = any(kw in q for kw in chemistry_context)
        has_chemical_formula = (
            any(f in query for f in known_formulas) or
            bool(re.search(r'[A-Z][a-z]?\d+[A-Z]', query)) or  # Like NaCl, H2O
            bool(re.search(r'[A-Z][a-z]?[+-]', query))  # Like Na+, Cl-
        )
        if has_chemical_formula and has_chemistry_context:
            if any(word in q for word in ['reaction', 'equation', 'balance']):
                return f"chemical reactions"
            elif any(word in q for word in ['acid', 'base', 'ph']):
                return f"acid base reactions"
            else:
                return f"chemical formulas and reactions"

        # Detect physics formulas (require physics context)
        physics_keywords = {
            'f = ma': "Newton's second law",
            'f=ma': "Newton's second law",
            'e = mc': "mass energy equivalence",
            'v = ir': "Ohm's law",
            'p = mv': "momentum",
            'w = fd': "work done",
            'ke =': "kinetic energy",
            'pe =': "potential energy",
        }
        for pattern, concept in physics_keywords.items():
            if pattern in q:
                return concept

        # Detect calculus operations (require calculus context)
        calculus_keywords = ['integrate', 'integral', 'antiderivative', 'differentiate',
                           'derivative', 'differentiation', 'partial fraction']
        calculus_context = ['find', 'evaluate', 'compute', 'calculate', 'solve',
                          'dx', 'dy', '∫', '∂', 'limit']
        has_calculus_context = any(kw in q for kw in calculus_context)
        has_calculus_keyword = any(kw in q for kw in calculus_keywords)

        # Check for partial fractions specifically (before general calculus)
        if 'partial fraction' in q:
            return "integration by partial fractions"

        if has_calculus_keyword or (has_calculus_context and any(kw in q for kw in ['dx', 'dy', '∫', '∂'])):
            if any(word in q for word in ['integrate', 'integral', 'antiderivative']):
                return f"integration calculus"
            elif any(word in q for word in ['differentiate', 'derivative', 'differentiation']):
                return f"differentiation calculus"
            elif 'limit' in q:
                # Only return limits calculus if it's clearly about math limits
                if any(word in q for word in ['x→', 'approaches', 'tends to', 'infinity']):
                    return f"limits calculus"

        # Detect quadratic/polynomial (require math context)
        math_keywords = ['solve', 'find', 'evaluate', 'compute', 'calculate', 'graph', 'roots']
        has_math_context = any(kw in q for kw in math_keywords)
        if any(word in q for word in ['quadratic', 'polynomial', 'equation']):
            if has_math_context:
                if 'quadratic' in q:
                    return "quadratic equation formula"
                return "polynomial equations"

        # Detect common math questions (require formula context)
        if any(phrase in q for phrase in ['what is the formula', 'give formula', 'formula for']):
            # Extract what they want formula for
            for word in ['determinant', 'matrix', 'quadratic', 'integration', 'derivative']:
                if word in q:
                    return f"formula for {word}"
            return query

        return query

    def _replace_pronouns(self, query: str, concept: str) -> str:
        """Replace pronouns and vague references with the active concept."""
        q = query.lower().strip()

        # Direct pronoun patterns
        pronoun_patterns = [
            (r'\bthem\b', concept),
            (r'\bit\b', concept),
            (r'\bthat\b', concept),
            (r'\bthis\b', concept),
            (r'\bthose\b', concept),
        ]

        result = query
        for pattern, replacement in pronoun_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Vague reference patterns
        vague_patterns = [
            (r'\bthe thing\b', concept),
            (r'\bthe stuff\b', concept),
            (r'\bthat part\b', concept),
            (r'\bthat concept\b', concept),
            (r'\bthis concept\b', concept),
        ]

        for pattern, replacement in vague_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result


class RAGEngine:
    """Educational RAG engine - NCERT-only, with citations and verification."""

    def __init__(
        self,
        compiled_dir: str = "data/compiled",
        qdrant_path: str = "data/v2/qdrant_full",
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        # Load from config if not provided
        if llm_model is None or api_key is None:
            from backend.api.config import ServiceConfig
            config = ServiceConfig()
            llm_model = llm_model or config.model_id
            api_key = api_key or config.api_key

        self._compiled_dir = compiled_dir
        self._qdrant_path = qdrant_path
        self._llm_model = llm_model
        self._api_key = api_key

        self._graph = ConceptGraph()
        self._session_manager = SessionManager()
        self._hybrid_retriever = HybridRetriever(compiled_dir, qdrant_path)
        self._intent_resolver = IntentResolver()

        # Cache OpenAI client for reuse
        import openai
        self._llm_client = openai.OpenAI(
            base_url="https://api.cerebras.ai/v1",
            api_key=api_key,
        )

        # Caching: response cache + intent cache
        self._response_cache = TTLCache(max_size=500, default_ttl=600)  # 10 min
        self._intent_cache = TTLCache(max_size=1000, default_ttl=3600)  # 1 hour

        # Rate limiting: 30 queries per minute per session
        self._rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

        # Session cleanup: remove sessions older than 24 hours
        self._session_cleanup = SessionCleanup(
            db_path="data/sessions.db",
            ttl_seconds=86400,
            cleanup_interval=3600,
        )
        self._session_cleanup.start()

    def build_index(self) -> int:
        """Build the concept graph."""
        self._graph.build_from_compiled(self._compiled_dir)
        return len(self._graph._concepts)

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        subject_filter: Optional[str] = None,
    ) -> dict:
        """Process a query through the RAG engine with session context."""

        # Pre-filter: reject obviously non-educational queries
        question_lower = question.lower()
        non_educational_keywords = [
            "who is", "who was", "actor", "actress", "movie", "film",
            "cricket", "football", "bollywood", "hollywood", "singer",
            "politician", "president", "prime minister", "celebrity",
            "stock", "crypto", "bitcoin", "weather", "recipe",
        ]
        is_non_educational = any(kw in question_lower for kw in non_educational_keywords)

        if is_non_educational:
            refusal_answer = "I can only help with NCERT Class 12 Mathematics, Physics, and Chemistry topics. Please ask questions related to your syllabus."
            return {
                "answer": refusal_answer,
                "sources": [],
                "citations": [],
                "query": question,
                "session_id": session_id or "",
                "grounded": False,
                "verification": {
                    "passed": False,
                    "reason": "Non-educational query",
                },
            }

        # Get or create session
        if session_id:
            session = self._session_manager.get_session(session_id)
            if not session:
                session = self._session_manager.create_session()
        else:
            session = self._session_manager.create_session()

        # Rate limiting: check if session has exceeded limit
        if not self._rate_limiter.allow(session.session_id):
            return {
                "answer": "You're sending too many requests. Please wait a moment and try again.",
                "sources": [],
                "citations": [],
                "query": question,
                "session_id": session.session_id,
                "grounded": False,
                "rate_limited": True,
                "retry_after_seconds": 60,
                "cache_stats": {
                    "response_cache": self._response_cache.stats(),
                    "intent_cache": self._intent_cache.stats(),
                    "rate_limit_remaining": 0,
                },
                "verification": {
                    "passed": False,
                    "reason": "Rate limit exceeded",
                },
            }

        # Response caching: check for duplicate query
        cache_key = make_cache_key(question, subject_filter)
        cached_response = self._response_cache.get(cache_key)
        if cached_response:
            cached_response["session_id"] = session.session_id
            cached_response["cached"] = True
            return cached_response

        # Step 1: Resolve intent using LLM (handles follow-ups, ambiguous queries)
        resolved_query = self._intent_resolver.resolve(question, session, self._intent_cache)

        # Step 2: Retrieve relevant content using the resolved query
        results = self._hybrid_retriever.search(
            resolved_query, top_k=7, subject_filter=subject_filter
        )

        # Step 3: Build context from retrieved results
        context_parts = []
        sources = []
        citations = []

        for r in results:
            if r.get("text"):
                context_parts.append(f"[{r['concept_name']}] {r['text']}")
            if r.get("example_text"):
                context_parts.append(f"[{r['concept_name']} - Example] {r['example_text']}")
            elif r.get("definition_count", 0) > 0:
                context_parts.append(f"[{r['concept_name']}] ({r['subject']}, {r['chapter']})")

            sources.append({
                "concept_name": r["concept_name"],
                "concept_id": r["concept_id"],
                "subject": r["subject"],
                "chapter": r["chapter"],
                "score": r.get("rrf_score", r.get("score", 0)),
                "text": r.get("text", "")[:300],
                "figure_ids": r.get("figure_ids", []),
            })

            citations.append({
                "concept_id": r["concept_id"],
                "concept_name": r["concept_name"],
                "source_field": "definition" if r.get("definition_count", 0) > 0 else "concept",
                "subject": r["subject"],
                "chapter": r["chapter"],
                "page": r.get("page_start"),
                "book": r.get("book"),
                "figure_ids": r.get("figure_ids", []),
            })

        # Step 4: Generate answer with full conversation context
        context = "\n\n".join(context_parts) if context_parts else "No relevant context found."

        # Build conversation history for the LLM
        history_messages = []
        for turn in session.turns[-5:]:  # Last 5 turns
            history_messages.append({"role": "user", "content": turn.query})
            history_messages.append({"role": "assistant", "content": turn.answer[:300]})

        # Check if this is an exercise problem or solution request
        is_exercise = resolved_query.startswith("EXERCISE:")
        is_exercise_solution = resolved_query.startswith("EXERCISE SOLUTION:")
        exercise_problem = resolved_query.replace("EXERCISE:", "").strip() if is_exercise else ""
        exercise_topic = resolved_query.replace("EXERCISE SOLUTION:", "").strip() if is_exercise_solution else ""

        # Build the system prompt based on query type
        if is_exercise_solution:
            # STUDENT GAVE UP - Provide full solution
            system_prompt = f"""You are an NCERT Class 12 tutor. The student has asked for the complete solution.

TOPIC: {exercise_topic}

YOUR RULES FOR PROVIDING SOLUTIONS:
1. Provide the COMPLETE step-by-step solution
2. Reference the worked example from the textbook that shows the method
3. Show every calculation clearly
4. Explain each step
5. Include the final answer

FORMATTING:
- Start with: "Here's the complete solution:"
- Reference the worked example: "Using the method from Example X..."
- Show each step clearly with calculations
- End with the final answer

EXAMPLE:
Student: "show me the solution" (after asking about a differential equation)
You: Here's the complete solution, using the method from Example 12 (p.108):

Step 1: Identify the type
This is a homogeneous differential equation...

[Continue with full solution]"""

        elif is_exercise:
            # EXERCISE MODE: Guide student, don't solve directly
            system_prompt = f"""You are an NCERT Class 12 tutor. A student has asked about an exercise problem.

EXERCISE PROBLEM: {exercise_problem}

YOUR RULES FOR EXERCISES:
1. DO NOT solve the problem directly. The student needs to learn by doing.
2. Identify the TYPE of problem (e.g., homogeneous differential equation, matrix multiplication, etc.)
3. Reference the RELEVANT WORKED EXAMPLE from the textbook that teaches the method
4. Give HINTS step by step:
   - Hint 1: What method/formula to use
   - Hint 2: What substitution or approach to try
   - Hint 3: First step of the solution
5. Ask: "Would you like another hint, or should I show the complete solution?"
6. ONLY if the student says "show me" or "I give up" or similar, then provide the FULL solution

FORMATTING:
- Start with: "This is a [type of problem]. Let me help you solve it step by step."
- Reference the worked example: "See Example X in your textbook for the method."
- Give hints progressively, not all at once
- End with a question asking if they want more help

EXAMPLE:
Student: "x² dy + (xy + y²) dx = 0; y = 1 when x = 1"
You: This is a homogeneous differential equation with an initial condition.

The method for solving this is shown in Example 12 of your textbook (p.108), which solves a similar homogeneous equation.

Hint 1: For homogeneous equations, try the substitution y = vx (or x = vy).
Hint 2: After substitution, the equation should become separable.
Hint 3: Start by dividing the entire equation by x² to simplify.

Would you like another hint, or should I show the complete solution?"""

        else:
            # CONCEPT MODE: Explain and teach
            system_prompt = f"""You are an NCERT Class 12 tutor. You teach from the textbook context provided below.

RULES:

1. QUOTE the textbook when possible. Use definitions, formulas, and examples that appear in the context.

2. When the textbook provides a specific example, use it and cite it.

3. When the textbook does NOT provide a specific example, you may create a short illustration to help the student understand — BUT you MUST clearly separate it from textbook content. Use this format:
   - First: quote the textbook definition
   - Then: say "For illustration:" or "To illustrate this concept:" before your example
   - Never claim your illustration is from the textbook

4. NEVER add information that contradicts the textbook context.

5. If the context doesn't contain enough information to answer at all, say: "The provided textbook material does not contain information about this."

6. IMPORTANT: The context includes source tags like [Concept Name] or [Concept Name - Example]. Use these tags to correctly attribute content to the right concept. Do NOT confuse the content text with the source tag. For example, if you see "[Integrals - Example] are called indefinite integrals...", the definition belongs to the "Integrals" concept, NOT to "Some Properties of Definite Integrals" even if the text mentions that phrase.

EXAMPLE OF CORRECT BEHAVIOR:
Student: "Give me an example of a row matrix"
You: The textbook defines a row matrix as: "A matrix is said to be a row matrix if it has only one row." (p.51)

For illustration: [3  7  2] is a row matrix of order 1×3, since it has exactly one row and three columns.

Note: The illustration above is not from the textbook — it is provided to help you understand the definition.

EXAMPLE OF INCORRECT BEHAVIOR (DO NOT DO THIS):
"The textbook gives this example: [3 7 2]" — This is WRONG if the textbook doesn't contain this example.

Student follow-up questions may refer to previous topics. Use conversation history for context."""

        # Build the user message with context
        user_message = f"""Textbook context:
{context}

Student question: {question}"""

        # Combine history + current question
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        # Call LLM
        response = self._llm_client.chat.completions.create(
            model=self._llm_model,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
        )
        answer = response.choices[0].message.content

        # Step 5: Grounding check
        answer_text = answer.lower()
        is_refusal = (
            "i can only help" in answer_text
            or "not related to" in answer_text
            or "not contain" in answer_text
            or "no information" in answer_text
            or "i don't have" in answer_text
            or "not in my" in answer_text
            or "cannot answer" in answer_text
            or "no relevant" in answer_text
        )

        source_text = " ".join([s.get("text", "") for s in sources]).lower()
        answer_words = set(answer_text.split())
        source_words = set(source_text.split())

        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "have", "has", "had", "do", "does", "did", "will", "would",
                       "could", "should", "may", "might", "can", "to", "of", "in",
                       "for", "on", "with", "at", "by", "from", "as", "into",
                       "this", "that", "these", "those", "it", "its", "they", "them",
                       "we", "our", "you", "your", "i", "my", "not", "no", "but",
                       "and", "or", "if", "then", "so", "also", "very", "more",
                       "most", "some", "any", "all", "each", "every", "both"}

        answer_technical = answer_words - common_words
        source_technical = source_words - common_words

        if answer_technical and source_technical:
            overlap = len(answer_technical & source_technical)
            overlap_ratio = overlap / len(answer_technical) if answer_technical else 0
        else:
            overlap_ratio = 0

        source_concept_names = [s.get("concept_name", "").lower() for s in sources]
        answer_lower = answer_text.lower()
        mentions_source_concepts = any(name in answer_lower for name in source_concept_names if name)

        has_grounding = len(sources) > 0 and any(
            s.get("subject") in ["mathematics", "physics", "chemistry"]
            for s in sources
        ) and not is_refusal and (overlap_ratio > 0.05 or mentions_source_concepts)

        if not has_grounding and not is_refusal:
            source_names = ", ".join([s.get("concept_name", "") for s in sources[:3]])
            refusal_answer = f"I don't have enough information in my textbook material to answer this question. The available content covers {source_names}, which may not be directly related to your question."
            answer_to_show = refusal_answer
        else:
            answer_to_show = answer

        # Save turn to session
        self._session_manager.add_turn(
            session_id=session.session_id,
            query=question,
            answer=answer_to_show,
            sources=sources,
            citations=citations,
        )

        response = {
            "answer": answer_to_show,
            "sources": sources,
            "citations": citations,
            "query": question,
            "resolved_query": resolved_query,
            "session_id": session.session_id,
            "grounded": has_grounding,
            "cache_stats": {
                "response_cache": self._response_cache.stats(),
                "intent_cache": self._intent_cache.stats(),
                "rate_limit_remaining": self._rate_limiter.remaining(session.session_id),
            },
            "verification": {
                "passed": has_grounding,
                "reason": "Answer based on NCERT content" if has_grounding else "No NCERT content found",
            },
        }

        # Cache the response (only grounded answers)
        if has_grounding:
            self._response_cache.set(cache_key, response, ttl=600)

        return response

    def query_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
        subject_filter: Optional[str] = None,
    ):
        """Generator that yields SSE events for streaming responses.

        Yields dicts with {event: str, data: dict} for each chunk.
        """
        import json

        # Pre-filter
        question_lower = question.lower()
        non_educational_keywords = [
            "who is", "who was", "actor", "actress", "movie", "film",
            "cricket", "football", "bollywood", "hollywood", "singer",
            "politician", "president", "prime minister", "celebrity",
            "stock", "crypto", "bitcoin", "weather", "recipe",
        ]
        if any(kw in question_lower for kw in non_educational_keywords):
            yield {"event": "text", "data": {"text": "I can only help with NCERT Class 12 Mathematics, Physics, and Chemistry topics."}}
            yield {"event": "complete", "data": {"session_id": session_id or "", "sources": [], "citations": [], "grounded": False, "verification": {"passed": False, "reason": "Non-educational query"}}}
            return

        # Get or create session
        if session_id:
            session = self._session_manager.get_session(session_id)
            if not session:
                session = self._session_manager.create_session()
        else:
            session = self._session_manager.create_session()

        # Rate limiting
        if not self._rate_limiter.allow(session.session_id):
            yield {"event": "text", "data": {"text": "You're sending too many requests. Please wait a moment and try again."}}
            yield {"event": "complete", "data": {"session_id": session.session_id, "sources": [], "citations": [], "grounded": False, "rate_limited": True, "verification": {"passed": False, "reason": "Rate limit exceeded"}}}
            return

        # Resolve intent
        resolved_query = self._intent_resolver.resolve(question, session, self._intent_cache)

        # Retrieve
        results = self._hybrid_retriever.search(resolved_query, top_k=7, subject_filter=subject_filter)

        # Build context
        context_parts = []
        sources = []
        citations = []
        for r in results:
            if r.get("text"):
                context_parts.append(f"[{r['concept_name']}] {r['text']}")
            if r.get("example_text"):
                context_parts.append(f"[{r['concept_name']} - Example] {r['example_text']}")
            elif r.get("definition_count", 0) > 0:
                context_parts.append(f"[{r['concept_name']}] ({r['subject']}, {r['chapter']})")
            sources.append({
                "concept_name": r["concept_name"],
                "concept_id": r["concept_id"],
                "subject": r["subject"],
                "chapter": r["chapter"],
                "score": r.get("rrf_score", r.get("score", 0)),
                "text": r.get("text", "")[:300],
                "figure_ids": r.get("figure_ids", []),
            })
            citations.append({
                "concept_id": r["concept_id"],
                "concept_name": r["concept_name"],
                "source_field": "definition" if r.get("definition_count", 0) > 0 else "concept",
                "subject": r["subject"],
                "chapter": r["chapter"],
                "page": r.get("page_start"),
                "book": r.get("book"),
                "figure_ids": r.get("figure_ids", []),
            })

        context = "\n\n".join(context_parts) if context_parts else "No relevant context found."

        # Build conversation history
        history_messages = []
        for turn in session.turns[-5:]:
            history_messages.append({"role": "user", "content": turn.query})
            history_messages.append({"role": "assistant", "content": turn.answer[:300]})

        system_prompt = f"""You are an NCERT Class 12 tutor. You teach from the textbook context provided below.

RULES:

1. QUOTE the textbook when possible. Use definitions, formulas, and examples that appear in the context.

2. When the textbook provides a specific example, use it and cite it.

3. When the textbook does NOT provide a specific example, you may create a short illustration to help the student understand — BUT you MUST clearly separate it from textbook content. Use this format:
   - First: quote the textbook definition
   - Then: say "For illustration:" or "To illustrate this concept:" before your example
   - Never claim your illustration is from the textbook

4. NEVER add information that contradicts the textbook context.

5. If the context doesn't contain enough information to answer at all, say: "The provided textbook material does not contain information about this."

6. IMPORTANT: The context includes source tags like [Concept Name] or [Concept Name - Example]. Use these tags to correctly attribute content to the right concept. Do NOT confuse the content text with the source tag. For example, if you see "[Integrals - Example] are called indefinite integrals...", the definition belongs to the "Integrals" concept, NOT to "Some Properties of Definite Integrals" even if the text mentions that phrase.

EXAMPLE OF CORRECT BEHAVIOR:
Student: "Give me an example of a row matrix"
You: The textbook defines a row matrix as: "A matrix is said to be a row matrix if it has only one row." (p.51)

For illustration: [3  7  2] is a row matrix of order 1×3, since it has exactly one row and three columns.

Note: The illustration above is not from the textbook — it is provided to help you understand the definition.

EXAMPLE OF INCORRECT BEHAVIOR (DO NOT DO THIS):
"The textbook gives this example: [3 7 2]" — This is WRONG if the textbook doesn't contain this example.

Student follow-up questions may refer to previous topics. Use conversation history for context."""

        user_message = f"""Textbook context:
{context}

Student question: {question}"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        # Call LLM with streaming
        stream = self._llm_client.chat.completions.create(
            model=self._llm_model,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
            stream=True,
        )

        # Yield tokens as they arrive from the LLM
        full_answer = ""
        import asyncio
        for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_answer += token
                yield {"event": "text", "data": {"text": token}}

        # Grounding check
        answer_text = full_answer.lower()
        is_refusal = (
            "i can only help" in answer_text
            or "not related to" in answer_text
            or "not contain" in answer_text
            or "no information" in answer_text
            or "i don't have" in answer_text
            or "not in my" in answer_text
            or "cannot answer" in answer_text
            or "no relevant" in answer_text
        )

        source_text = " ".join([s.get("text", "") for s in sources]).lower()
        answer_words = set(answer_text.split())
        source_words = set(source_text.split())
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "have", "has", "had", "do", "does", "did", "will", "would",
                       "could", "should", "may", "might", "can", "to", "of", "in",
                       "for", "on", "with", "at", "by", "from", "as", "into",
                       "this", "that", "these", "those", "it", "its", "they", "them",
                       "we", "our", "you", "your", "i", "my", "not", "no", "but",
                       "and", "or", "if", "then", "so", "also", "very", "more",
                       "most", "some", "any", "all", "each", "every", "both"}

        answer_technical = answer_words - common_words
        source_technical = source_words - common_words
        if answer_technical and source_technical:
            overlap = len(answer_technical & source_technical)
            overlap_ratio = overlap / len(answer_technical) if answer_technical else 0
        else:
            overlap_ratio = 0

        source_concept_names = [s.get("concept_name", "").lower() for s in sources]
        answer_lower = answer_text.lower()
        mentions_source_concepts = any(name in answer_lower for name in source_concept_names if name)

        has_grounding = len(sources) > 0 and any(
            s.get("subject") in ["mathematics", "physics", "chemistry"]
            for s in sources
        ) and not is_refusal and (overlap_ratio > 0.05 or mentions_source_concepts)

        # Save turn
        self._session_manager.add_turn(
            session_id=session.session_id,
            query=question,
            answer=full_answer,
            sources=sources,
            citations=citations,
        )

        # Send completion event
        yield {
            "event": "complete",
            "data": {
                "session_id": session.session_id,
                "sources": sources,
                "citations": citations,
                "grounded": has_grounding,
                "verification": {
                    "passed": has_grounding,
                    "reason": "Answer based on NCERT content" if has_grounding else "No NCERT content found",
                },
            },
        }
