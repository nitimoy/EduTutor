'use client'

import React, { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { GraduationCap, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/lib/AuthContext';

function AuthForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { login } = useAuth();
    const [isLogin, setIsLogin] = useState(searchParams.get('tab') !== 'register');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const [form, setForm] = useState({
        username: '',
        email: '',
        phone: '',
        password: '',
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const endpoint = isLogin ? '/api/v2/auth/login' : '/api/v2/auth/register';
            const body = isLogin
                ? { username: form.username, password: form.password }
                : form;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                body: JSON.stringify(body),
            });

            const data = await response.json();

            if (!response.ok) {
                setError(data.detail || 'Authentication failed');
                return;
            }

            // Use AuthContext.login() — this sets localStorage + the auth cookie
            login({
                token: data.token,
                user_id: data.user_id,
                username: data.username,
                email: data.email,
            });

            // Redirect to originally-requested page or app dashboard
            const intendedEngine = sessionStorage.getItem('intended_engine');
            if (intendedEngine) {
                sessionStorage.removeItem('intended_engine');
                router.push('/session');
            } else {
                let from = searchParams.get('from') || '/session';
                if (from === '/') from = '/session';
                router.push(from);
            }
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-500/10 mb-4">
                        <GraduationCap className="w-8 h-8 text-blue-400" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">EduTutor</h1>
                    <p className="text-sm text-slate-400 mt-1">NCERT Class 12 AI Tutor</p>
                </div>

                {/* Tabs */}
                <div className="flex bg-slate-800/50 rounded-xl p-1 mb-6">
                    <button
                        onClick={() => { setIsLogin(true); setError(''); }}
                        className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                            isLogin ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        Sign In
                    </button>
                    <button
                        onClick={() => { setIsLogin(false); setError(''); }}
                        className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                            !isLogin ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        Sign Up
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Username */}
                    <div>
                        <label className="block text-sm text-slate-400 mb-1.5">Username</label>
                        <input
                            type="text"
                            value={form.username}
                            onChange={(e) => setForm({ ...form, username: e.target.value })}
                            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                            placeholder="Enter username"
                            required
                        />
                    </div>

                    {/* Email (register only) */}
                    {!isLogin && (
                        <div>
                            <label className="block text-sm text-slate-400 mb-1.5">Email</label>
                            <input
                                type="email"
                                value={form.email}
                                onChange={(e) => setForm({ ...form, email: e.target.value })}
                                className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                                placeholder="Enter email"
                                required
                            />
                        </div>
                    )}

                    {/* Phone (register only) */}
                    {!isLogin && (
                        <div>
                            <label className="block text-sm text-slate-400 mb-1.5">Phone</label>
                            <input
                                type="tel"
                                value={form.phone}
                                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                                className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                                placeholder="Enter phone number"
                                required
                            />
                        </div>
                    )}

                    {/* Password */}
                    <div>
                        <label className="block text-sm text-slate-400 mb-1.5">Password</label>
                        <div className="relative">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                value={form.password}
                                onChange={(e) => setForm({ ...form, password: e.target.value })}
                                className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors pr-10"
                                placeholder="Enter password"
                                required
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                            >
                                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors"
                    >
                        {loading ? 'Please wait...' : (isLogin ? 'Sign In' : 'Create Account')}
                    </button>
                </form>
            </div>
        </div>
    );
}

export default function AuthPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-slate-400 animate-pulse">Loading...</div>
            </div>
        }>
            <AuthForm />
        </Suspense>
    );
}
