export interface PipelineTrace {
    resolved_query: string;
    intent: string;
    response_profile: Record<string, string>;
    retrieval: Record<string, any>;
    teaching_plan: Record<string, any>;
    prompt: Record<string, any>[];
    verification: Record<string, any>;
}

export interface SessionTurn {
    user_query: string;
    resolved_query: string;
    retrieval_metadata: Record<string, any>;
    intent: string;
    strategy: string;
    question_type?: string;    // e.g. "conceptual_reasoning", "comparison"
    educational_goal?: string; // e.g. "understand_principle", "structured_comparison"
    primary_concept: string;
    tutor_response: string;
    verification_passed: boolean;
    notes?: string[];
    timestamp: string;
}

export interface StudentProfileState {
    completed_concepts: string[];
    misconceptions: Record<string, string>;
    learning_style: Record<string, any>;
}

export interface StudentProfile {
    student_id: string;
    state: StudentProfileState;
}

export interface Citation {
    concept_id: string | null;
    concept_name: string;
    source_field: string;
    locator: string;
    object_type: string | null;
    subject?: string;
    chapter?: string;
    book?: string;
    page?: number;
    figure_ids?: string[];
}

export interface Section {
    kind: string;
    status: string;
    items: string[];
    citations: Citation[];
    note: string | null;
}

export interface TutorPlan {
    query: string;
    intent: string;
    strategy: string;
    question_type?: string;    // e.g. "conceptual_reasoning", "comparison"
    educational_goal?: string; // e.g. "understand_principle", "exam_preparation"
    primary_concept_id: string;
    primary_concept_name: string;
    references: Citation[];
    notes: string[];
    grounded_facts: Section;   // disclaimer + facts when WHY cannot be answered
    prerequisites: Section;
    main_explanation: Section;
    formula: Section;
    worked_example: Section;
    proof: Section;
    exercise: Section;
    comparison: Section;
    related_concepts: Section;
    suggested_next_topics: Section;
    summary: Section;
}

export interface RenderedResponse {
    query: string;
    text: string;
    sections: any[];
}

export interface VerificationReport {
    coverage: Record<string, any>;
    citations: Record<string, any>;
    grounding: Record<string, any>;
    completeness: Record<string, any>;
    contract: Record<string, any>;
    provider: Record<string, any>;
    metrics: Record<string, any>;
    passed: boolean;
}

export interface TutorResponse {
    query: string;
    rendered_response: RenderedResponse;
    tutor_plan: TutorPlan;
    verification_report: VerificationReport;
    personalization: Record<string, any>;
    citations: Citation[];
    retrieval_metadata: Record<string, any>;
    execution_metadata: Record<string, any>;
    execution_trace: Record<string, any>;
    timing: Record<string, any>;
    prompt_documents?: Record<string, any>[];
    passed: boolean;
    evidence_report?: Record<string, any>;
}

export interface LearningSession {
    session_id: string;
    student_profile: StudentProfile;
    active_subject: string | null;
    active_chapter: string | null;
    active_concept: string | null;
    history: SessionTurn[];
    misconceptions: string[];
    completed_concepts: string[];
    last_response: TutorResponse | null;
}
