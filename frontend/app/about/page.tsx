import { MainLayout } from "@/components/layout/MainLayout";
import { Brain, Zap, Search, GitBranch, Shield, BookOpen, Sparkles, Database } from "lucide-react";

export default function AboutPage() {
    return (
        <MainLayout>
            <div className="p-8 max-w-4xl mx-auto space-y-8">
                <h1 className="text-3xl font-bold text-slate-100">Architecture</h1>

                {/* Overview */}
                <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 space-y-4 text-slate-300 leading-relaxed">
                    <p>
                        EduTutor is an AI-powered NCERT Class 12 tutor for Mathematics, Physics, and Chemistry.
                        The system ingests NCERT textbook PDFs, compiles them into structured knowledge graphs,
                        and serves a multi-stage educational pipeline that retrieves relevant concepts, plans
                        pedagogical strategy, personalizes for the student, and generates verified responses.
                    </p>
                    <p>
                        Two engine versions are available — choose the one that fits your needs:
                    </p>
                </div>

                {/* v1 Architecture */}
                <div className="bg-slate-900/50 p-6 rounded-2xl border border-blue-500/20 space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <Brain className="w-6 h-6 text-blue-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-white">Engine v1 — Deterministic Pipeline</h2>
                            <span className="text-xs text-blue-400 font-medium">Original engine, frozen interface</span>
                        </div>
                    </div>

                    <p className="text-sm text-slate-400 leading-relaxed">
                        v1 runs a 9-stage deterministic pipeline where every educational decision is made
                        by rule-based code. The LLM is used only as a final text renderer, receiving
                        highly constrained structured prompts. This ensures consistency and verifiability.
                    </p>

                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-500">
                        <div className="flex items-center gap-2">
                            <Search className="w-3 h-3 text-blue-400" />
                            <span>BM25F lexical retrieval</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <GitBranch className="w-3 h-3 text-blue-400" />
                            <span>9-stage orchestration</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Shield className="w-3 h-3 text-blue-400" />
                            <span>Response verification</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <BookOpen className="w-3 h-3 text-blue-400" />
                            <span>Student profiling</span>
                        </div>
                    </div>

                    <div className="text-xs text-slate-500 bg-slate-800/50 p-3 rounded-lg">
                        <strong className="text-slate-400">Pipeline stages:</strong> Profiling → Retrieval (BM25F) → Ranking →
                        Evidence Assessment → Planning → Personalization → Composition → Generation → Verification
                    </div>
                </div>

                {/* v2 Architecture */}
                <div className="bg-slate-900/50 p-6 rounded-2xl border border-emerald-500/20 space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/10">
                            <Zap className="w-6 h-6 text-emerald-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-white">Engine v2 — RAG + Semantic Search</h2>
                            <span className="text-xs text-emerald-400 font-medium">Enhanced engine, recommended</span>
                        </div>
                    </div>

                    <p className="text-sm text-slate-400 leading-relaxed">
                        v2 was built to fix v1&apos;s biggest limitation: <strong className="text-slate-300">lexical search fails on paraphrases</strong>.
                        When a student asks &quot;rectangular array of numbers&quot;, v1 can&apos;t find &quot;Matrix&quot; because
                        the keywords don&apos;t match. v2 adds semantic vector search (BGE-M3 embeddings via Qdrant)
                        that understands meaning, not just keywords.
                    </p>

                    <p className="text-sm text-slate-400 leading-relaxed">
                        v2 also adds LLM-powered intent resolution so follow-up questions like &quot;another example&quot;
                        or &quot;the transpose thing&quot; actually work — the LLM understands context from conversation
                        history and resolves ambiguous queries to proper search terms.
                    </p>

                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-500">
                        <div className="flex items-center gap-2">
                            <Search className="w-3 h-3 text-emerald-400" />
                            <span>BM25F + Qdrant vector search</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-3 h-3 text-emerald-400" />
                            <span>LLM intent resolution</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Database className="w-3 h-3 text-emerald-400" />
                            <span>Response & intent caching</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Shield className="w-3 h-3 text-emerald-400" />
                            <span>Rate limiting & session TTL</span>
                        </div>
                    </div>

                    <div className="text-xs text-slate-500 bg-slate-800/50 p-3 rounded-lg">
                        <strong className="text-slate-400">Key improvements over v1:</strong>
                        <ul className="mt-1 space-y-1 list-disc list-inside">
                            <li>Semantic search handles paraphrases and conceptual queries</li>
                            <li>Reciprocal Rank Fusion merges lexical + vector results</li>
                            <li>Follow-up questions resolved via LLM + conversation history</li>
                            <li>Response caching reduces LLM costs 50%+</li>
                            <li>Rate limiting prevents abuse</li>
                        </ul>
                    </div>
                </div>

                {/* Shared Infrastructure */}
                <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 space-y-4">
                    <h2 className="text-xl font-semibold text-white">Shared Infrastructure</h2>
                    <div className="grid grid-cols-2 gap-4 text-sm text-slate-400">
                        <div className="space-y-2">
                            <p className="font-medium text-slate-300">Frontend</p>
                            <ul className="space-y-1 text-xs">
                                <li>Next.js 16 (App Router, Tailwind CSS 4)</li>
                                <li>Streaming SSE responses</li>
                                <li>Markdown + LaTeX rendering (KaTeX)</li>
                                <li>Developer mode (pipeline trace)</li>
                                <li>Session persistence</li>
                            </ul>
                        </div>
                        <div className="space-y-2">
                            <p className="font-medium text-slate-300">Backend</p>
                            <ul className="space-y-1 text-xs">
                                <li>FastAPI (Python, uvicorn)</li>
                                <li>SQLite (sessions, knowledge index)</li>
                                <li>Qdrant (v2 vector store, local mode)</li>
                                <li>Cerebras LLM (gpt-oss-120b)</li>
                                <li>NCERT compiler (PDF → knowledge graph)</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </MainLayout>
    );
}
