'use client'

import React, { useRef, useEffect, useState } from 'react';
import { useSession } from '@/lib/SessionContext';
import { TurnCard } from './TurnCard';
import { ChatInput } from './ChatInput';

interface ChatInterfaceProps {
    onSend: (query: string) => void;
    activeStream?: { query: string; text: string } | null;
    error?: string | null;
}

export function ChatInterface({ onSend, activeStream, error }: ChatInterfaceProps) {
    const { session, isLoading } = useSession();
    const endOfMessagesRef = useRef<HTMLDivElement>(null);
    const [showSpinner, setShowSpinner] = useState(false);

    // Show spinner when loading starts, hide when text appears or streaming ends
    useEffect(() => {
        if (isLoading && activeStream && !activeStream.text) {
            setShowSpinner(true);
        } else if (activeStream?.text || !activeStream || !isLoading) {
            setShowSpinner(false);
        }
    }, [isLoading, activeStream?.text, activeStream]);

    useEffect(() => {
        endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [session?.history, isLoading, activeStream?.text]);

    const history = session?.history || [];
    const hasHistory = history.length > 0 || activeStream;

    return (
        <div className="flex flex-col h-full relative max-w-4xl mx-auto w-full">
            {/* Scrollable messages area */}
            <div className="flex-1 overflow-y-auto px-4 pb-32">
                {!hasHistory ? (
                    <div className="flex items-center justify-center h-full text-slate-500">
                        <p>Ask a question to start the session.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {history.map((turn, idx) => {
                            const isLast = idx === history.length - 1;
                            const response = isLast && session?.last_response ? session.last_response : undefined;

                            return (
                                <TurnCard key={idx} turn={turn} response={response} />
                            );
                        })}

                        {/* Show user's question and response when streaming */}
                        {activeStream && (
                            <TurnCard
                                turn={{
                                    user_query: activeStream.query,
                                    resolved_query: activeStream.query,
                                    retrieval_metadata: {},
                                    intent: "Processing",
                                    strategy: "Formulating",
                                    primary_concept: "Pending",
                                    tutor_response: activeStream.text || "",
                                    verification_passed: true,
                                    timestamp: new Date().toISOString()
                                }}
                            />
                        )}

                        {/* Spinner - shows below the question while waiting for first token */}
                        {showSpinner && (
                            <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/50 rounded-lg ml-12 animate-pulse">
                                <div className="flex gap-1.5">
                                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></div>
                                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.15s' }}></div>
                                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.3s' }}></div>
                                </div>
                                <span className="text-sm text-slate-400">Thinking...</span>
                            </div>
                        )}
                    </div>
                )}

                {isLoading && !activeStream && (
                    <div className="py-8 pl-12 flex gap-2">
                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></div>
                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                    </div>
                )}

                {error && (
                    <div className="mx-4 mb-4 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-sm">
                        {error}
                    </div>
                )}
                <div ref={endOfMessagesRef} />
            </div>

            {/* Input fixed at the bottom */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent pt-12 pb-6 px-4 pointer-events-none">
                <div className="pointer-events-auto">
                    <ChatInput onSend={onSend} disabled={isLoading} />
                </div>
            </div>
        </div>
    );
}
