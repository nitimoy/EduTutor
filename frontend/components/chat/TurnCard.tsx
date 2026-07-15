'use client'

import React, { useState } from 'react';
import { SessionTurn, TutorResponse } from '@/types';
import { SessionTimeline } from './SessionTimeline';
import { MarkdownRenderer } from '../markdown/MarkdownRenderer';
import { Citations } from './Citations';
import { User, Sparkles, Code2, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { FigureDisplay } from './FigureDisplay';
import { motion, AnimatePresence } from 'framer-motion';

interface TurnCardProps {
    turn: SessionTurn;
    response?: TutorResponse;
}

export function TurnCard({ turn, response }: TurnCardProps) {
    const [isDevModeOpen, setIsDevModeOpen] = useState(false);

    // Extract figure IDs from sources
    const figureIds = response?.citations
        ?.filter((c: any) => c.figure_ids && c.figure_ids.length > 0)
        ?.flatMap((c: any) => c.figure_ids)
        ?.slice(0, 3) || [];

    const figureSubject = response?.citations?.[0]?.subject || 'mathematics';
    const figureBook = response?.citations?.[0]?.book || 'mathematics_part_1';

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-6 py-6 border-b border-slate-800/50"
        >
            {/* User Query */}
            <div className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0">
                    <User className="w-4 h-4 text-slate-400" />
                </div>
                <div className="pt-1">
                    <p className="text-slate-200 text-lg font-medium">{turn.user_query}</p>
                </div>
            </div>

            {/* AI Response Container */}
            <div className="flex gap-4 md:pl-12">
                <div className="flex-1 max-w-none w-full min-w-0">
                    <SessionTimeline turn={turn} />

                    <div className="bg-slate-900/40 rounded-2xl p-6 border border-slate-800/60 shadow-sm overflow-x-auto relative">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-blue-400" />
                                <h3 className="text-sm font-semibold text-slate-300">EduTutor</h3>
                            </div>

                            {/* Dev Mode Toggle */}
                            <button
                                onClick={() => setIsDevModeOpen(!isDevModeOpen)}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700 transition-colors text-xs font-medium text-slate-400 hover:text-slate-200"
                            >
                                <Code2 className="w-3.5 h-3.5" />
                                <span>Dev Trace</span>
                                {isDevModeOpen ? <ChevronDown className="w-3 h-3 ml-1" /> : <ChevronRight className="w-3 h-3 ml-1" />}
                            </button>
                        </div>

                        <AnimatePresence>
                            {isDevModeOpen && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="overflow-hidden mb-6"
                                >
                                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 font-mono text-xs text-slate-400 flex flex-col gap-3">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <span className="text-slate-500 block mb-1 uppercase tracking-wider text-[10px]">Intent</span>
                                                <span className="text-indigo-400">{turn.intent}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-500 block mb-1 uppercase tracking-wider text-[10px]">Strategy</span>
                                                <span className="text-purple-400">{turn.strategy}</span>
                                            </div>
                                        </div>

                                        {(turn.question_type || turn.educational_goal) && (
                                            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800/50">
                                                {turn.question_type && (
                                                    <div>
                                                        <span className="text-slate-500 block mb-1 uppercase tracking-wider text-[10px]">Question Type</span>
                                                        <span className="text-cyan-400">{turn.question_type}</span>
                                                    </div>
                                                )}
                                                {turn.educational_goal && (
                                                    <div>
                                                        <span className="text-slate-500 block mb-1 uppercase tracking-wider text-[10px]">Educational Goal</span>
                                                        <span className="text-teal-400">{turn.educational_goal}</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {turn.notes && turn.notes.length > 0 && (
                                            <div className="pt-2 border-t border-slate-800/50 mt-1">
                                                <span className="text-slate-500 block mb-2 uppercase tracking-wider text-[10px]">Orchestrator Notes</span>
                                                <ul className="flex flex-col gap-2">
                                                    {turn.notes.map((note, i) => (
                                                        <li key={i} className="flex gap-2 items-start text-amber-200/80 bg-amber-900/10 p-2 rounded-md border border-amber-900/20">
                                                            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-500/70" />
                                                            <span>{note}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}

                                        {turn.strategy === 'refusal' && (
                                            <div className="pt-2 border-t border-slate-800/50 mt-1 text-amber-400/90 bg-amber-950/30 p-2 rounded-md border border-amber-900/30">
                                                <span>Unsupported query — content not in compiled corpus.</span>
                                            </div>
                                        )}
                                        {!turn.verification_passed && turn.strategy !== 'refusal' && (
                                            <div className="pt-2 border-t border-slate-800/50 mt-1 text-rose-400/90 bg-rose-950/30 p-2 rounded-md border border-rose-900/30">
                                                <span>Grounding Verification Failed!</span>
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <MarkdownRenderer content={turn.tutor_response} />

                        {/* Figures from textbook */}
                        {figureIds.length > 0 && (
                            <FigureDisplay
                                figureIds={figureIds}
                                subject={figureSubject}
                                book={figureBook}
                            />
                        )}

                        {response && response.citations && response.citations.length > 0 && (
                            <Citations citations={response.citations} />
                        )}
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
