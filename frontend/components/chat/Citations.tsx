'use client'

import React from 'react';
import { Citation } from '@/types';
import { BookMarked, FileText } from 'lucide-react';

interface CitationsProps {
    citations: Citation[];
}

interface GroupedCitation {
    subject?: string;
    chapter?: string;
    concept_name: string;
    source_fields: Set<string>;
    page?: number | null;
    book?: string | null;
}

export function Citations({ citations }: CitationsProps) {
    if (!citations || citations.length === 0) return null;

    // Group citations by book, chapter, and concept
    const groupedCitations = citations.reduce((acc, cit: any) => {
        const key = `${cit.subject}-${cit.chapter}-${cit.concept_id}`;
        if (!acc[key]) {
            acc[key] = {
                subject: cit.subject,
                chapter: cit.chapter,
                concept_name: cit.concept_name,
                source_fields: new Set<string>(),
                page: cit.page || null,
                book: cit.book || null,
            };
        }
        acc[key].source_fields.add(cit.source_field.replace(/_/g, ' '));
        return acc;
    }, {} as Record<string, GroupedCitation>);

    const groupedArray = Object.values(groupedCitations);

    return (
        <div className="mt-6 pt-4 border-t border-slate-800/60">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1">
                <BookMarked className="w-3 h-3" /> Sources
            </h4>
            <div className="flex flex-col gap-2">
                {groupedArray.map((group, idx) => (
                    <div key={idx} className="bg-slate-800/30 hover:bg-slate-800/60 border border-slate-700/50 rounded-md px-3 py-2 text-[11px] transition-colors cursor-default">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span className="font-semibold text-slate-200">
                                {group.subject || "Unknown"} &gt; {group.chapter || "Unknown"}
                            </span>
                            <span className="bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold">
                                {group.concept_name}
                            </span>
                            {group.page && (
                                <span className="flex items-center gap-1 bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-medium">
                                    <FileText className="w-2.5 h-2.5" />
                                    p. {group.page}
                                </span>
                            )}
                        </div>
                        <div className="text-slate-400">
                            Includes: {Array.from(group.source_fields).join(', ')}
                            {group.book && (
                                <span className="text-slate-500 ml-2">({group.book.replace(/_/g, ' ')})</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
