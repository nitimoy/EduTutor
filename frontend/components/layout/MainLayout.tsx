'use client'

import React, { useState } from 'react';
import { StudentSidebar } from '../sidebar/StudentSidebar';
import { DeveloperPanel } from '../developer/DeveloperPanel';
import { Settings, Menu, Zap, Brain, LogOut, User, GraduationCap } from 'lucide-react';
import { useSession } from '@/lib/SessionContext';
import { useAuth } from '@/lib/AuthContext';
import Link from 'next/link';

export function MainLayout({ children }: { children: React.ReactNode }) {
    const { isDeveloperMode, setIsDeveloperMode, engineVersion, setEngineVersion, clearSession } = useSession();
    const { user, isAuthenticated, logout } = useAuth();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const handleLogout = () => {
        clearSession();
        logout();
    };

    // For unauthenticated users: render a clean minimal layout (no sidebar, no dev tools)
    if (!isAuthenticated) {
        return (
            <div className="flex flex-col h-[100dvh] bg-slate-950 font-sans text-slate-200">
                {/* Minimal public top bar */}
                <div className="h-14 border-b border-slate-800 bg-slate-900/50 backdrop-blur flex items-center justify-between px-6 sticky top-0 z-10">
                    <Link href="/" className="flex items-center gap-2 text-white hover:text-blue-400 transition-colors">
                        <GraduationCap className="w-6 h-6 text-blue-400" />
                        <span className="font-bold text-lg">EduTutor</span>
                    </Link>
                    <Link
                        href="/auth"
                        className="text-sm text-slate-400 hover:text-white transition-colors px-4 py-2 rounded-lg hover:bg-slate-800"
                    >
                        Sign In
                    </Link>
                </div>
                <main className="flex-1 overflow-y-auto">
                    {children}
                </main>
            </div>
        );
    }

    // Authenticated layout: full sidebar + dev panel
    return (
        <div className="flex h-[100dvh] bg-slate-950 overflow-hidden font-sans text-slate-200">
            {/* Mobile Sidebar Overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-20 md:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar — only shown when authenticated */}
            <div className={`fixed md:static inset-y-0 left-0 transform ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0 transition duration-200 ease-in-out z-30 flex`}>
                <StudentSidebar onClose={() => setSidebarOpen(false)} />
            </div>

            <div className="flex-1 flex flex-col min-w-0 relative">
                {/* Topbar */}
                <div className="h-14 border-b border-slate-800 bg-slate-900/50 backdrop-blur flex items-center justify-between px-4 sticky top-0 z-10">
                    {/* Mobile menu toggle */}
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="md:hidden p-2 text-slate-400 hover:text-slate-200"
                    >
                        <Menu className="w-5 h-5" />
                    </button>

                    <div className="ml-auto flex items-center gap-3">
                        {/* Engine Version Switcher */}
                        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
                            <button
                                onClick={() => setEngineVersion('v1')}
                                className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                                    engineVersion === 'v1'
                                        ? 'bg-blue-500/20 text-blue-400'
                                        : 'text-slate-400 hover:text-slate-200'
                                }`}
                                title="Traditional pipeline"
                            >
                                <Brain className="w-3.5 h-3.5" />
                                v1
                            </button>
                            <button
                                onClick={() => setEngineVersion('v2')}
                                className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                                    engineVersion === 'v2'
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'text-slate-400 hover:text-slate-200'
                                }`}
                                title="RAG-based pipeline"
                            >
                                <Zap className="w-3.5 h-3.5" />
                                v2
                            </button>
                        </div>

                        <button
                            onClick={() => setIsDeveloperMode(!isDeveloperMode)}
                            className={`p-2 rounded-md transition-colors ${isDeveloperMode ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
                            title="Toggle Developer Mode"
                        >
                            <Settings className="w-5 h-5" />
                        </button>

                        {/* User info + logout */}
                        {user && (
                            <div className="flex items-center gap-2 pl-2 border-l border-slate-700">
                                <div className="flex items-center gap-1.5 text-slate-400 text-xs">
                                    <User className="w-4 h-4" />
                                    <span className="hidden sm:inline font-medium text-slate-300">{user.username}</span>
                                </div>
                                <button
                                    onClick={handleLogout}
                                    className="p-2 rounded-md text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                    title="Logout"
                                >
                                    <LogOut className="w-4 h-4" />
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Main Content Area */}
                <main className="flex-1 overflow-y-auto">
                    {children}
                </main>
            </div>

            {/* Developer panel — only shown to authenticated users on large screens */}
            <div className="hidden lg:block">
                <DeveloperPanel />
            </div>
        </div>
    );
}
