'use client'

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { LearningSession } from '../types';

interface SessionContextProps {
    session: LearningSession | null;
    setSession: (session: LearningSession | null) => void;
    clearSession: () => void;
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;
    isDeveloperMode: boolean;
    setIsDeveloperMode: (dev: boolean) => void;
    engineVersion: 'v1' | 'v2';
    setEngineVersion: (version: 'v1' | 'v2') => void;
}

const SessionContext = createContext<SessionContextProps | undefined>(undefined);

const ENGINE_STORAGE_KEY = 'edu_engine_version';

export function SessionProvider({ children }: { children: ReactNode }) {
    const [session, setSession] = useState<LearningSession | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isDeveloperMode, setIsDeveloperMode] = useState(false);

    // Restore engineVersion from localStorage on first load, default to 'v2'
    const [engineVersion, setEngineVersionState] = useState<'v1' | 'v2'>(() => {
        if (typeof window !== 'undefined') {
            const stored = localStorage.getItem(ENGINE_STORAGE_KEY);
            if (stored === 'v1' || stored === 'v2') return stored;
        }
        return 'v2'; // Default to v2 (recommended)
    });

    // Wrap setEngineVersion so every change is persisted to localStorage
    const setEngineVersion = (version: 'v1' | 'v2') => {
        localStorage.setItem(ENGINE_STORAGE_KEY, version);
        setEngineVersionState(version);
    };

    // clearSession resets active session state (called on logout)
    const clearSession = () => {
        setSession(null);
        setIsLoading(false);
    };

    return (
        <SessionContext.Provider value={{
            session, setSession, clearSession,
            isLoading, setIsLoading,
            isDeveloperMode, setIsDeveloperMode,
            engineVersion, setEngineVersion,
        }}>
            {children}
        </SessionContext.Provider>
    );
}

export function useSession() {
    const context = useContext(SessionContext);
    if (context === undefined) {
        throw new Error('useSession must be used within a SessionProvider');
    }
    return context;
}
