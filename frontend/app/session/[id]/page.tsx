'use client'

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { useSession } from '@/lib/SessionContext';
import { getSession, getV2Session, queryV2, queryV2Stream, askQuestion } from '@/services/api';

export default function SessionPage() {
    const params = useParams();
    const router = useRouter();
    const sessionId = params.id as string;
    const { session, setSession, isLoading, setIsLoading, engineVersion } = useSession();
    const [isFetching, setIsFetching] = useState(true);
    const [activeStream, setActiveStream] = useState<{ query: string; text: string } | null>(null);
    const [streamError, setStreamError] = useState<string | null>(null);

    // Load session from backend
    useEffect(() => {
        let mounted = true;

        async function loadSession() {
            try {
                if (engineVersion === 'v2') {
                    // Load v2 session from backend — now returns full turns array
                    const v2Session = await getV2Session(sessionId);
                    if (v2Session && !v2Session.error && mounted) {
                        const turns: any[] = Array.isArray(v2Session.turns) ? v2Session.turns : [];

                        // Convert v2 session turns to frontend history format
                        const history = turns.map((turn: any) => ({
                            user_query: turn.query,
                            resolved_query: turn.query,
                            retrieval_metadata: {},
                            intent: 'definition',
                            strategy: 'concept_explanation',
                            primary_concept: turn.sources?.[0]?.concept_name || '',
                            tutor_response: turn.answer,
                            verification_passed: true,
                            timestamp: turn.timestamp,
                            v2_citations: turn.citations || [],
                            v2_sources: turn.sources || [],
                        }));

                        // Derive completed concepts from unique concept names seen in sources
                        const completedConceptsSet = new Set<string>();
                        turns.forEach((turn: any) => {
                            (turn.sources || []).forEach((src: any) => {
                                if (src.concept_name) completedConceptsSet.add(src.concept_name);
                            });
                        });
                        const completedConcepts = Array.from(completedConceptsSet);

                        setSession({
                            session_id: sessionId,
                            student_profile: {
                                state: {
                                    student_id: 'anonymous',
                                    completed_concepts: completedConcepts,
                                }
                            },
                            active_concept: v2Session.active_concept || null,
                            active_subject: v2Session.active_subject || null,
                            history: history,
                            last_response: history.length > 0 ? {
                                query: history[history.length - 1].user_query,
                                execution_metadata: { intent: "V2_RAG_QUERY" },
                                tutor_plan: { question_type: "hybrid_search", educational_goal: "answer_with_context" },
                                retrieval_metadata: {
                                    strategy_name: "Vector + BM25 Hybrid",
                                    retrieved_concepts: (history[history.length - 1].v2_sources || []).map((s: any) => ({
                                        name: s.concept_name || s.file_name || 'Document',
                                        score: s.score || 0,
                                        breakdown: { reasons: [`Source: ${s.source || 'N/A'}`, `Distance: ${s.distance || 'N/A'}`] }
                                    }))
                                },
                                verification_report: {
                                    passed: true,
                                    grounding: { passed: true },
                                    coverage: { passed: true },
                                    citations: { passed: true },
                                    completeness: { passed: true }
                                },
                                citations: history[history.length - 1].v2_citations || [],
                                prompt_documents: history[history.length - 1].v2_sources || [],
                                rendered_response: { sections: [], text: history[history.length - 1].tutor_response },
                            } as any : null,
                        } as any);
                    } else {
                        // Session doesn't exist or error — show empty chat
                        setSession({
                            session_id: sessionId,
                            student_profile: { state: { student_id: 'anonymous', completed_concepts: [] } },
                            history: [],
                            last_response: null,
                        } as any);
                    }
                } else {
                    // v1: load session from SQLite-backed store
                    try {
                        const data = await getSession(sessionId);
                        if (mounted) {
                            setSession(data);
                        }
                    } catch {
                        // Session doesn't exist
                        setSession({
                            session_id: sessionId,
                            student_profile: { state: { student_id: 'anonymous', completed_concepts: [] } },
                            history: [],
                            last_response: null,
                        } as any);
                    }
                }
            } catch (err) {
                console.error("Failed to load session", err);
            } finally {
                if (mounted) setIsFetching(false);
            }
        }

        loadSession();
        return () => { mounted = false; };
    }, [sessionId, engineVersion]);


    const handleSend = async (query: string) => {
        setIsLoading(true);
        setActiveStream({ query, text: '' });
        setStreamError(null);

        try {
            if (engineVersion === 'v2') {
                // Use streaming for v2
                let streamedAnswer = '';
                let sources: any[] = [];
                let citations: any[] = [];
                let grounded = false;
                let verification: any = {};

                await queryV2Stream(query, sessionId, (event, data) => {
                    if (event === 'text') {
                        streamedAnswer += data.text || '';
                        setActiveStream({ query, text: streamedAnswer });
                    } else if (event === 'complete') {
                        sources = data.sources || [];
                        citations = data.citations || [];
                        grounded = data.grounded || false;
                        verification = data.verification || {};
                    }
                });

                const newTurn = {
                    user_query: query,
                    resolved_query: query,
                    retrieval_metadata: {},
                    intent: 'definition',
                    strategy: 'concept_explanation',
                    primary_concept: sources[0]?.concept_name || '',
                    tutor_response: streamedAnswer,
                    verification_passed: verification.passed ?? true,
                    timestamp: new Date().toISOString(),
                    v2_citations: citations,
                    v2_sources: sources,
                    v2_grounded: grounded,
                };

                const prevCompleted: string[] = (session as any)?.student_profile?.state?.completed_concepts || [];
                const newConceptNames = sources.map((s: any) => s.concept_name).filter(Boolean);
                const mergedConcepts = Array.from(new Set([...prevCompleted, ...newConceptNames]));

                setSession({
                    session_id: sessionId,
                    student_profile: { state: { student_id: 'anonymous', completed_concepts: mergedConcepts } },
                    active_concept: sources[0]?.concept_name || (session as any)?.active_concept || null,
                    active_subject: sources[0]?.subject || (session as any)?.active_subject || null,
                    history: [...((session as any)?.history || []), newTurn],
                    last_response: {
                        query,
                        execution_metadata: { intent: "V2_RAG_QUERY" },
                        tutor_plan: { question_type: "hybrid_search", educational_goal: "answer_with_context" },
                        retrieval_metadata: {
                            strategy_name: "Vector + BM25 Hybrid",
                            retrieved_concepts: sources.map((s: any) => ({
                                name: s.concept_name || s.file_name || 'Document',
                                score: s.score || 0,
                                breakdown: { reasons: [`Source: ${s.source || 'N/A'}`, `Distance: ${s.distance || 'N/A'}`] }
                            }))
                        },
                        verification_report: verification || {
                            passed: grounded,
                            grounding: { passed: grounded },
                            coverage: { passed: true },
                            citations: { passed: true },
                            completeness: { passed: true }
                        },
                        citations,
                        prompt_documents: sources,
                        rendered_response: { sections: [], text: streamedAnswer },
                    },
                } as any);
            } else {
                await askQuestion(sessionId, query);
                const updated = await getSession(sessionId);
                setSession(updated);
            }
        } catch (err) {
            console.error("Failed to get response", err);
            setStreamError("Failed to get response. Please try again.");
        } finally {
            setActiveStream(null);
            setIsLoading(false);
        }
    };

    return (
        <MainLayout>
            {isFetching ? (
                <div className="flex h-full items-center justify-center">
                    <div className="text-slate-400 flex flex-col items-center">
                        <div className="w-8 h-8 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mb-4"></div>
                        <p>Loading session...</p>
                    </div>
                </div>
            ) : (
                <ChatInterface onSend={handleSend} activeStream={activeStream} error={streamError} />
            )}
        </MainLayout>
    );
}
