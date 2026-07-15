'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

interface AuthUser {
    user_id: string;
    username: string;
    email: string;
}

interface AuthContextProps {
    user: AuthUser | null;
    token: string | null;
    isAuthenticated: boolean;
    login: (data: { token: string; user_id: string; username: string; email: string }) => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const router = useRouter();

    // On mount, restore auth state from localStorage
    useEffect(() => {
        try {
            const storedToken = localStorage.getItem('auth_token');
            const storedUser = localStorage.getItem('auth_user');
            if (storedToken && storedUser) {
                setToken(storedToken);
                setUser(JSON.parse(storedUser));
            }
        } catch {
            // Ignore parse errors
        }
    }, []);

    const login = useCallback((data: { token: string; user_id: string; username: string; email: string }) => {
        const userObj: AuthUser = {
            user_id: data.user_id,
            username: data.username,
            email: data.email,
        };
        // Persist to localStorage
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('auth_user', JSON.stringify(userObj));
        // Set a simple cookie so Next.js middleware can check it.
        // On HTTPS (ngrok/production): SameSite=None; Secure works.
        // On HTTP localhost: omit Secure flag so the cookie actually persists.
        const isSecure = window.location.protocol === 'https:';
        const cookieParts = ['edu_logged_in=1', 'path=/', 'max-age=86400', 'SameSite=Lax'];
        if (isSecure) {
            cookieParts.push('Secure');
        }
        document.cookie = cookieParts.join('; ');
        setToken(data.token);
        setUser(userObj);
    }, []);

    const logout = useCallback(() => {
        // Clear storage and cookie
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        const isSecure = window.location.protocol === 'https:';
        const cookieParts = ['edu_logged_in=', 'path=/', 'max-age=0', 'SameSite=Lax'];
        if (isSecure) {
            cookieParts.push('Secure');
        }
        document.cookie = cookieParts.join('; ');
        setToken(null);
        setUser(null);
        router.push('/auth');
    }, [router]);

    const isAuthenticated = !!(token && user);

    return (
        <AuthContext.Provider value={{ user, token, isAuthenticated, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
