'use client'

import React from 'react';
import { SessionTurn } from '@/types';
import { BrainCircuit, Search, CheckCircle2, XCircle, MessageSquare, Target, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

interface SessionTimelineProps {
    turn: SessionTurn;
}

export function SessionTimeline({ turn }: SessionTimelineProps) {
    const steps = [
        { label: "Query", value: turn.resolved_query, icon: MessageSquare, color: "text-blue-400" },
        { label: "Concept", value: turn.primary_concept, icon: Search, color: "text-indigo-400" },
        { label: "Strategy", value: turn.strategy, icon: BrainCircuit, color: "text-purple-400" },
        ...(turn.educational_goal ? [{
            label: "Goal",
            value: turn.educational_goal.replace(/_/g, ' '),
            icon: Target,
            color: "text-teal-400"
        }] : []),
        {
            label: "Verification",
            value: turn.strategy === 'refusal' ? 'Refused' : (turn.verification_passed ? "Passed" : "Failed"),
            icon: turn.strategy === 'refusal' ? AlertCircle : (turn.verification_passed ? CheckCircle2 : XCircle),
            color: turn.strategy === 'refusal' ? "text-amber-400" : (turn.verification_passed ? "text-emerald-400" : "text-rose-400")
        },
    ];

    return (
        <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1 scrollbar-hide text-[11px] whitespace-nowrap">
            {steps.map((step, idx) => (
                <React.Fragment key={step.label}>
                    <motion.div 
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-center gap-1.5 bg-slate-900/50 border border-slate-800 rounded-full px-3 py-1.5"
                    >
                        <step.icon className={`w-3.5 h-3.5 ${step.color}`} />
                        <span className="text-slate-500 font-medium">{step.label}:</span>
                        <span className="text-slate-300 truncate max-w-[150px]">{step.value}</span>
                    </motion.div>
                    {idx < steps.length - 1 && (
                        <div className="text-slate-700">→</div>
                    )}
                </React.Fragment>
            ))}
        </div>
    );
}
