'use client'

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/MainLayout';
import { listSessions } from '@/services/api';

export default function HistoryPage() {
    const [sessions, setSessions] = useState<Array<{session_id: string, title: string, updated_at: string}>>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let mounted = true;
        async function fetchHistory() {
            try {
                const data = await listSessions();
                if (mounted) {
                    setSessions(data);
                    setIsLoading(false);
                }
            } catch (err) {
                console.error("Failed to load history", err);
                if (mounted) setIsLoading(false);
            }
        }
        fetchHistory();
        return () => { mounted = false; };
    }, []);

    return (
        <MainLayout>
            <div className="p-8 max-w-4xl mx-auto space-y-6">
                <h1 className="text-3xl font-bold text-slate-100">Session History</h1>
                {isLoading ? (
                    <div className="flex justify-center p-12">
                        <div className="w-8 h-8 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin"></div>
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 text-slate-400 text-center">
                        <p>No previous sessions found.</p>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {sessions.map(s => (
                            <Link key={s.session_id} href={`/session/${s.session_id}`}>
                                <div className="bg-slate-900/50 hover:bg-slate-800/80 p-5 rounded-2xl border border-slate-800 transition-colors flex justify-between items-center group">
                                    <div>
                                        <h3 className="text-lg font-semibold text-slate-200 group-hover:text-blue-400 transition-colors">{s.title}</h3>
                                        <p className="text-sm text-slate-500 mt-1">ID: {s.session_id.split('-')[0]}...</p>
                                    </div>
                                    <div className="text-slate-400 text-sm bg-slate-950 px-3 py-1 rounded-full">
                                        {new Date(s.updated_at).toLocaleDateString()}
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
