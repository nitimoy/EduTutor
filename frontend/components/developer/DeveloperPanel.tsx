'use client'

import React from 'react';
import { useSession } from '@/lib/SessionContext';
import { Code, Server, Activity, FileText } from 'lucide-react';

export function DeveloperPanel() {
    const { session, isDeveloperMode } = useSession();

    if (!isDeveloperMode) return null;

    const response = session?.last_response;

    return (
        <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-[100dvh] text-slate-300 text-sm overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex-shrink-0">
                <h2 className="font-semibold text-slate-100 flex items-center gap-2">
                    <Code className="w-4 h-4 text-indigo-400" />
                    Pipeline Inspector
                </h2>
            </div>
            <div className="p-4 flex-1 overflow-y-auto space-y-2">
                {!response ? (
                    <p className="text-slate-500 italic">No interaction history yet.</p>
                ) : (
                    <>
                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Server className="w-3 h-3" /> User Query</h3>
                            <p className="font-mono text-[12px] text-blue-300">{response.query}</p>
                        </div>
                        
                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Activity className="w-3 h-3" /> Response Profile</h3>
                            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                                <div className="bg-slate-900 p-2 rounded">
                                    <div className="text-slate-500 uppercase text-[9px] mb-1">Intent</div>
                                    <div className="text-purple-300">{response.execution_metadata?.intent}</div>
                                </div>
                                <div className="bg-slate-900 p-2 rounded">
                                    <div className="text-slate-500 uppercase text-[9px] mb-1">Question Type</div>
                                    <div className="text-cyan-300">{response.tutor_plan?.question_type ?? '—'}</div>
                                </div>
                                <div className="bg-slate-900 p-2 rounded col-span-2">
                                    <div className="text-slate-500 uppercase text-[9px] mb-1">Educational Goal</div>
                                    <div className="text-teal-300">{response.tutor_plan?.educational_goal ?? '—'}</div>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Activity className="w-3 h-3" /> Evidence Assessment</h3>
                            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                                <div className="bg-slate-900 p-2 rounded col-span-2">
                                    <div className="text-slate-500 uppercase text-[9px] mb-1">Evidence Relevance</div>
                                    <div className={response.evidence_report?.relevance === 'NOT_RELEVANT' ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                                        {response.evidence_report?.relevance ?? '—'}
                                    </div>
                                </div>
                                {response.evidence_report?.issues?.length > 0 && (
                                    <div className="bg-slate-900 p-2 rounded col-span-2">
                                        <div className="text-slate-500 uppercase text-[9px] mb-1">Issues</div>
                                        <ul className="list-inside list-disc text-rose-300 text-[9px] space-y-1">
                                            {response.evidence_report?.issues.map((issue: string, i: number) => (
                                                <li key={i}>{issue}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><FileText className="w-3 h-3" /> Retrieved Concepts</h3>
                            <div className="font-mono text-[11px] space-y-3">
                                <p><span className="text-emerald-500 font-semibold">Strategy:</span> <span className="text-slate-300">{response.retrieval_metadata?.strategy_name}</span></p>
                                
                                {response.retrieval_metadata?.retrieved_concepts && response.retrieval_metadata.retrieved_concepts.length > 0 ? (
                                    <div className="space-y-2">
                                        {response.retrieval_metadata.retrieved_concepts.map((concept: any, i: number) => (
                                            <div key={i} className="bg-slate-900 p-2 rounded border border-slate-800/50">
                                                <div className="flex justify-between items-center mb-1">
                                                    <span className="text-emerald-300 font-semibold truncate" title={concept.name}>{concept.name}</span>
                                                    <span className="text-slate-400 text-[10px] bg-slate-950 px-1.5 py-0.5 rounded">{concept.score?.toFixed(2) ?? "N/A"}</span>
                                                </div>
                                                {concept.breakdown && concept.breakdown.reasons && concept.breakdown.reasons.length > 0 && (
                                                    <div className="text-[9px] text-slate-500">
                                                        <span className="uppercase text-slate-600 block mb-0.5">Ranking Breakdown:</span>
                                                        <ul className="list-inside list-disc pl-1 space-y-0.5">
                                                            {concept.breakdown.reasons.map((r: string, j: number) => (
                                                                <li key={j}>{r}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <ul className="list-disc list-inside pl-2 space-y-1">
                                        {response.retrieval_metadata?.result_concept_ids?.map((id: string, i: number) => (
                                            <li key={i} className="text-slate-400">{id}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Code className="w-3 h-3" /> Teaching Plan</h3>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800/50 max-h-32 overflow-y-auto font-mono text-[10px] text-slate-400 scrollbar-thin scrollbar-thumb-slate-700">
                                <pre className="whitespace-pre-wrap">
                                    {JSON.stringify(response.tutor_plan, null, 2)}
                                </pre>
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><FileText className="w-3 h-3" /> Prompt</h3>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800/50 max-h-32 overflow-y-auto font-mono text-[10px] text-amber-200/80 scrollbar-thin scrollbar-thumb-slate-700">
                                <pre className="whitespace-pre-wrap">
                                    {response.prompt_documents ? JSON.stringify(response.prompt_documents, null, 2) : "Prompt not available"}
                                </pre>
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><FileText className="w-3 h-3" /> LLM Response</h3>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800/50 max-h-32 overflow-y-auto font-mono text-[10px] text-cyan-200/80 scrollbar-thin scrollbar-thumb-slate-700">
                                <pre className="whitespace-pre-wrap">
                                    {response.rendered_response?.text ?? "Response not available"}
                                </pre>
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Activity className="w-3 h-3" /> Verification</h3>
                            <div className="font-mono text-[11px] space-y-2">
                                <div className={`px-2 py-1.5 rounded flex justify-between font-semibold ${response.verification_report?.passed ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-800/50' : 'bg-rose-900/30 text-rose-400 border border-rose-800/50'}`}>
                                    <span>Outcome:</span>
                                    <span>{response.verification_report?.passed ? 'PASSED' : 'FAILED'}</span>
                                </div>
                                <div className="grid grid-cols-2 gap-1.5 mt-2">
                                    <div className="p-2 bg-slate-900 rounded border border-slate-800/50 flex flex-col items-center">
                                        <div className="text-slate-500 uppercase text-[9px] mb-1 text-center tracking-wider">Grounding</div>
                                        <div className={`font-bold ${response.verification_report?.grounding?.passed ? "text-emerald-400" : "text-rose-400"}`}>
                                            {response.verification_report?.grounding?.passed ? '✓' : '✗'}
                                        </div>
                                    </div>
                                    <div className="p-2 bg-slate-900 rounded border border-slate-800/50 flex flex-col items-center">
                                        <div className="text-slate-500 uppercase text-[9px] mb-1 text-center tracking-wider">Coverage</div>
                                        <div className={`font-bold ${response.verification_report?.coverage?.passed ? "text-emerald-400" : "text-rose-400"}`}>
                                            {response.verification_report?.coverage?.passed ? '✓' : '✗'}
                                        </div>
                                    </div>
                                    <div className="p-2 bg-slate-900 rounded border border-slate-800/50 flex flex-col items-center">
                                        <div className="text-slate-500 uppercase text-[9px] mb-1 text-center tracking-wider">Citations</div>
                                        <div className={`font-bold ${response.verification_report?.citations?.passed ? "text-emerald-400" : "text-rose-400"}`}>
                                            {response.verification_report?.citations?.passed ? '✓' : '✗'}
                                        </div>
                                    </div>
                                    <div className="p-2 bg-slate-900 rounded border border-slate-800/50 flex flex-col items-center">
                                        <div className="text-slate-500 uppercase text-[9px] mb-1 text-center tracking-wider">Completeness</div>
                                        <div className={`font-bold ${response.verification_report?.completeness?.passed ? "text-emerald-400" : "text-rose-400"}`}>
                                            {response.verification_report?.completeness?.passed ? '✓' : '✗'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-center text-slate-600">↓</div>

                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 shadow-sm relative mb-4">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2"><Server className="w-3 h-3" /> Final Response</h3>
                            <p className="font-mono text-[10px] text-slate-500">Sent to user.</p>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
