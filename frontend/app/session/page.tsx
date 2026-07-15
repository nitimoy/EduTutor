'use client'

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MainLayout } from '@/components/layout/MainLayout';
import { useSession } from '@/lib/SessionContext';
import { useAuth } from '@/lib/AuthContext';

export default function SessionSetup() {
    const router = useRouter();
    const { engineVersion } = useSession();
    const { user } = useAuth();

    useEffect(() => {
        let mounted = true;

        async function init() {
            try {
                const { startV2Session, startSession } = await import('@/services/api');
                // Use the logged-in user's ID so sessions are user-specific.
                // Falls back to 'anonymous' if not authenticated (shouldn't happen — middleware guards this route).
                const studentId = user?.user_id || user?.username || 'anonymous';

                let session;
                if (engineVersion === 'v2') {
                    session = await startV2Session(studentId);
                } else {
                    session = await startSession(studentId);
                }

                if (mounted && session?.session_id) {
                    router.replace(`/session/${session.session_id}`);
                }
            } catch (err) {
                console.error("Failed to create session", err);
                if (mounted) {
                    router.push('/');
                }
            }
        }

        init();
        return () => { mounted = false; };
    }, [router, engineVersion, user]);

    return (
        <MainLayout>
            <div className="flex h-full items-center justify-center">
                <div className="text-slate-400 animate-pulse flex flex-col items-center">
                    <div className="w-8 h-8 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mb-4"></div>
                    <p>Creating session...</p>
                </div>
            </div>
        </MainLayout>
    );
}
