'use client'

import React, { useState, useEffect } from 'react';
import { useSession } from '@/lib/SessionContext';
import { useAuth } from '@/lib/AuthContext';
import { BookOpen, CheckCircle, GraduationCap, X, Trash2 } from 'lucide-react';
import Link from 'next/link';

export function StudentSidebar({ onClose }: { onClose?: () => void }) {
    const { session, engineVersion } = useSession();
    const { user } = useAuth();
    const studentId = user?.user_id || user?.username || 'anonymous';

    // Derive completed concepts from two sources (works for both v1 and v2):
    // 1. session.student_profile.state.completed_concepts (v1 stores concept IDs here)
    // 2. session.history[*].primary_concept (readable names, works for v2)
    const completedConceptsFromProfile: string[] =
        (session as any)?.student_profile?.state?.completed_concepts || [];

    // Collect human-readable concept names from history turns
    const conceptNamesFromHistory: string[] = Array.from(
        new Set(
            ((session as any)?.history || [])
                .map((turn: any) => turn.primary_concept)
                .filter(Boolean)
        )
    );

    // Merge: prefer names from history (readable), fall back to profile IDs formatted nicely
    const completedConceptIds = completedConceptsFromProfile.filter(
        id => !conceptNamesFromHistory.some(name =>
            name.toLowerCase().includes(id.replace(/^concept\./, '').replace(/_/g, ' ').toLowerCase().substring(0, 10))
        )
    );
    const formattedIds = completedConceptIds.map(id =>
        id.replace(/^concept\./, '').replace(/_/g, ' ')
    );

    const allCompletedConcepts: string[] = Array.from(
        new Set([...conceptNamesFromHistory, ...formattedIds])
    );

    return (
        <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-[100dvh] text-slate-200">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <Link href="/">
                    <h1 className="text-xl font-bold flex items-center gap-2 text-white hover:text-blue-400 transition-colors">
                        <GraduationCap className="w-6 h-6 text-blue-400" />
                        EduTutor
                    </h1>
                </Link>
                {onClose && (
                    <button onClick={onClose} className="md:hidden text-slate-400 hover:text-slate-200">
                        <X className="w-5 h-5" />
                    </button>
                )}
            </div>

            <div className="p-4 flex-1 overflow-y-auto">
                {/* Current Focus */}
                <div className="mb-6">
                    <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">Current Focus</h2>
                    <div className="bg-slate-800 rounded p-3">
                        {session?.active_concept ? (
                            <div className="flex items-start gap-2">
                                <BookOpen className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                                <div>
                                    <p className="font-medium text-slate-100">{session.active_concept}</p>
                                    <p className="text-xs text-slate-400 mt-1">{session.active_subject || "General"} / {session.active_chapter || "-"}</p>
                                </div>
                            </div>
                        ) : (
                            <p className="text-slate-400 text-sm">No active concept</p>
                        )}
                    </div>
                </div>

                {/* Completed Concepts */}
                <div className="mb-6">
                    <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                        Completed Concepts
                        {allCompletedConcepts.length > 0 && (
                            <span className="ml-2 text-xs font-normal text-slate-500 normal-case">
                                ({allCompletedConcepts.length})
                            </span>
                        )}
                    </h2>
                    <div className="space-y-2">
                        {allCompletedConcepts.length > 0 ? (
                            allCompletedConcepts.map((name, idx) => (
                                <div key={idx} className="flex items-center gap-2 text-sm text-slate-300">
                                    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                                    <span className="truncate capitalize">{name}</span>
                                </div>
                            ))
                        ) : (
                            <p className="text-slate-500 text-sm italic">No completed concepts yet.</p>
                        )}
                    </div>
                </div>

                {/* Recent Sessions */}
                <div className="mb-6">
                    <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider flex items-center justify-between">
                        Recent Sessions
                        <Link
                            href="/session"
                            className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 text-xs lowercase"
                        >
                            + new
                        </Link>
                    </h2>
                    <RecentSessionsList
                        currentSessionId={session?.session_id}
                        engineVersion={engineVersion}
                        historyLength={(session as any)?.history?.length || 0}
                        studentId={studentId}
                    />
                </div>

                {/* Flashcards */}
                <div className="mb-6">
                    <Link
                        href="/flashcards"
                        className="flex items-center gap-2 px-3 py-2 bg-slate-800 rounded hover:bg-slate-700 transition-colors"
                    >
                        <BookOpen className="w-4 h-4 text-blue-400" />
                        <span className="text-sm text-slate-300">Chapter Flashcards</span>
                    </Link>
                </div>
            </div>
        </div>
    );
}

function RecentSessionsList({ currentSessionId, engineVersion, historyLength, studentId }: {
    currentSessionId?: string;
    engineVersion: 'v1' | 'v2';
    historyLength?: number;
    studentId?: string;
}) {
    const [sessions, setSessions] = React.useState<Array<{session_id: string, title: string, updated_at: string, turn_count?: number}>>([]);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        let mounted = true;
        setLoading(true);
        import('@/services/api').then(m => m.listAllSessions(engineVersion, studentId || 'anonymous')).then(data => {
            if (mounted) {
                setSessions(data.filter((s: any) => s.turn_count === undefined || s.turn_count > 0));
                setLoading(false);
            }
        }).catch(err => {
            console.error("Failed to load sessions", err);
            if (mounted) setLoading(false);
        });
        return () => { mounted = false; };
    }, [currentSessionId, engineVersion, historyLength, studentId]);

    const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
        e.preventDefault();
        e.stopPropagation();
        if (confirm('Delete this session?')) {
            try {
                const api = await import('@/services/api');
                if (engineVersion === 'v2') {
                    await api.deleteV2Session(sessionId);
                } else {
                    await api.deleteSession(sessionId);
                }
                setSessions(prev => prev.filter(s => s.session_id !== sessionId));
            } catch (err) {
                console.error("Failed to delete session", err);
            }
        }
    };

    if (loading) return <p className="text-slate-500 text-sm italic">Loading...</p>;
    if (sessions.length === 0) return <p className="text-slate-500 text-sm italic">No recent sessions.</p>;

    return (
        <div className="space-y-1">
            {sessions.map(s => (
                <Link
                    key={s.session_id}
                    href={`/session/${s.session_id}`}
                    className={`group flex items-center justify-between px-3 py-2 rounded text-sm transition-colors ${currentSessionId === s.session_id ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
                >
                    <span className="truncate flex-1">{s.title || "New Session"}</span>
                    <button
                        onClick={(e) => handleDelete(e, s.session_id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-opacity ml-2"
                        title="Delete session"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                </Link>
            ))}
        </div>
    );
}
