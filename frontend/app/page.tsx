'use client'

import { MainLayout } from "@/components/layout/MainLayout";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/SessionContext";
import { useAuth } from "@/lib/AuthContext";
import { Brain, Zap, BookOpen, GitBranch, Search, Shield, ArrowRight, Sparkles, Target, CheckCircle, LogIn } from "lucide-react";
import Link from 'next/link';

export default function Home() {
  const router = useRouter();
  const { setEngineVersion } = useSession();
  const { isAuthenticated } = useAuth();

  const selectVersion = (version: 'v1' | 'v2') => {
    if (!isAuthenticated) {
      // Store intended version in sessionStorage so we can restore it after login
      sessionStorage.setItem('intended_engine', version);
      router.push('/auth');
      return;
    }
    setEngineVersion(version);
    router.push('/session');
  };

  return (
    <MainLayout>
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-12 space-y-16">

          {/* Hero Section */}
          <div className="text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800/80 rounded-full border border-slate-700/50 mb-4">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-slate-400">NCERT Class 12 • Mathematics • Physics • Chemistry</span>
            </div>

            <h1 className="text-6xl font-bold tracking-tight text-white leading-tight">
              Learn anything,<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400">
                deeply.
              </span>
            </h1>

            <p className="text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
              Your personal AI tutor for NCERT Class 12. Ask questions in natural language,
              get answers sourced directly from the textbook with page references.
            </p>

            {/* CTA for unauthenticated users */}
            {!isAuthenticated && (
              <div className="flex items-center justify-center gap-4 pt-2">
                <Link
                  href="/auth"
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-blue-500/20"
                >
                  <LogIn className="w-4 h-4" />
                  Sign In to Start
                </Link>
                <Link
                  href="/auth?tab=register"
                  className="flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-xl border border-slate-700 transition-all duration-200"
                >
                  Create Account
                </Link>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 max-w-xl mx-auto">
            <div className="text-center p-4 bg-slate-800/30 rounded-xl border border-slate-700/30">
              <div className="text-2xl font-bold text-white">465</div>
              <div className="text-xs text-slate-400">Concepts</div>
            </div>
            <div className="text-center p-4 bg-slate-800/30 rounded-xl border border-slate-700/30">
              <div className="text-2xl font-bold text-white">6</div>
              <div className="text-xs text-slate-400">Textbooks</div>
            </div>
            <div className="text-center p-4 bg-slate-800/30 rounded-xl border border-slate-700/30">
              <div className="text-2xl font-bold text-white">100%</div>
              <div className="text-xs text-slate-400">Textbook Grounded</div>
            </div>
          </div>

          {/* Version Selection */}
          <div className="space-y-6">
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-white mb-2">Choose Your Learning Engine</h2>
              <p className="text-sm text-slate-400">
                {isAuthenticated
                  ? 'Select the engine that best fits your learning style'
                  : 'Sign in to start learning'}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* v1 Card */}
              <button
                onClick={() => selectVersion('v1')}
                className="group relative text-left p-6 rounded-2xl border border-slate-700/50 bg-slate-800/30 hover:bg-slate-800/60 hover:border-blue-500/50 transition-all duration-200"
              >
                <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  {isAuthenticated
                    ? <ArrowRight className="w-5 h-5 text-blue-400" />
                    : <LogIn className="w-5 h-5 text-blue-400" />}
                </div>

                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2.5 rounded-xl bg-blue-500/10">
                    <Brain className="w-6 h-6 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-white">Engine v1</h3>
                    <span className="text-xs text-blue-400 font-medium">Deterministic Pipeline</span>
                  </div>
                </div>

                <p className="text-sm text-slate-400 mb-5 leading-relaxed">
                  A 9-stage deterministic pipeline. Every educational decision is made by rule-based code;
                  the LLM only renders natural language. Best for structured, verifiable responses.
                </p>

                <div className="space-y-2.5 text-xs text-slate-500">
                  <div className="flex items-center gap-2.5">
                    <Search className="w-3.5 h-3.5 text-blue-400/60" />
                    <span>BM25F lexical retrieval with educational ranking</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <GitBranch className="w-3.5 h-3.5 text-blue-400/60" />
                    <span>9-stage deterministic orchestration</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <Shield className="w-3.5 h-3.5 text-blue-400/60" />
                    <span>Response verification & grounding checks</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <BookOpen className="w-3.5 h-3.5 text-blue-400/60" />
                    <span>Student profiling & personalized teaching</span>
                  </div>
                </div>
              </button>

              {/* v2 Card */}
              <button
                onClick={() => selectVersion('v2')}
                className="group relative text-left p-6 rounded-2xl border border-emerald-500/30 bg-slate-800/30 hover:bg-slate-800/60 hover:border-emerald-500/50 transition-all duration-200"
              >
                <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  {isAuthenticated
                    ? <ArrowRight className="w-5 h-5 text-emerald-400" />
                    : <LogIn className="w-5 h-5 text-emerald-400" />}
                </div>

                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2.5 rounded-xl bg-emerald-500/10">
                    <Zap className="w-6 h-6 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-white">Engine v2</h3>
                    <span className="text-xs text-emerald-400 font-medium">RAG + Semantic Search</span>
                  </div>
                </div>

                <p className="text-sm text-slate-400 mb-5 leading-relaxed">
                  Hybrid retrieval combining lexical search with semantic vectors. Handles paraphrases,
                  follow-up questions, and complex queries. Best for natural conversation.
                </p>

                <div className="space-y-2.5 text-xs text-slate-500">
                  <div className="flex items-center gap-2.5">
                    <Search className="w-3.5 h-3.5 text-emerald-400/60" />
                    <span>BM25F + Qdrant vector search (RRF fusion)</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <Sparkles className="w-3.5 h-3.5 text-emerald-400/60" />
                    <span>LLM-powered intent resolution for follow-ups</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <Zap className="w-3.5 h-3.5 text-emerald-400/60" />
                    <span>Response caching (50%+ LLM cost reduction)</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <Shield className="w-3.5 h-3.5 text-emerald-400/60" />
                    <span>Rate limiting & session management</span>
                  </div>
                </div>

                <div className="mt-4 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <span className="text-xs text-emerald-400 font-medium">Recommended for new users</span>
                </div>
              </button>
            </div>
          </div>

          {/* Features */}
          <div className="space-y-6">
            <h2 className="text-2xl font-semibold text-white text-center">Why EduTutor?</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 bg-slate-800/30 rounded-xl border border-slate-700/30">
                <div className="p-2 rounded-lg bg-blue-500/10 w-fit mb-3">
                  <BookOpen className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="font-semibold text-white mb-2">Textbook Grounded</h3>
                <p className="text-sm text-slate-400">Every answer comes directly from NCERT textbooks with page references. No hallucinated content.</p>
              </div>

              <div className="p-5 bg-slate-800/30 rounded-xl border border-slate-700/30">
                <div className="p-2 rounded-lg bg-purple-500/10 w-fit mb-3">
                  <Target className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="font-semibold text-white mb-2">Natural Language</h3>
                <p className="text-sm text-slate-400">Ask questions in plain English. No need to learn special syntax or formatting.</p>
              </div>

              <div className="p-5 bg-slate-800/30 rounded-xl border border-slate-700/30">
                <div className="p-2 rounded-lg bg-emerald-500/10 w-fit mb-3">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="font-semibold text-white mb-2">Verified Responses</h3>
                <p className="text-sm text-slate-400">Every response is verified against the textbook before showing. Grounded answers only.</p>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="text-center text-xs text-slate-600 pt-8 border-t border-slate-800/50">
            <p>EduTutor — AI-Powered NCERT Class 12 Tutor</p>
            <p className="mt-1">Mathematics • Physics • Chemistry</p>
          </div>

        </div>
      </div>
    </MainLayout>
  );
}
