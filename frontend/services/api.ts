import { LearningSession, TutorResponse } from '../types';

// All API calls go through the Next.js proxy at /api/*
// The proxy target is configured in next.config.ts via NEXT_PUBLIC_API_URL
const API_BASE = '/api';

// =============================================================================
// v1 API — Deterministic pipeline (BM25F retrieval, 9-stage orchestration)
// =============================================================================

export async function startSession(studentId: string = "anonymous"): Promise<LearningSession> {
    const response = await fetch(`${API_BASE}/v1/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ student_id: studentId })
    });
    if (!response.ok) throw new Error("Failed to start session");
    return response.json();
}

export async function askQuestion(sessionId: string, query: string): Promise<TutorResponse> {
    const response = await fetch(`${API_BASE}/v1/session/${sessionId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ query })
    });
    if (!response.ok) throw new Error("Failed to ask question");
    return response.json();
}

export async function getSession(sessionId: string): Promise<LearningSession> {
    const response = await fetch(`${API_BASE}/v1/session/${sessionId}`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) throw new Error("Failed to get session");
    return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/v1/session/${sessionId}`, {
        method: 'DELETE',
        headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    if (!response.ok) throw new Error("Failed to delete session");
}

export async function deleteV2Session(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/v1/version/session/${sessionId}`, {
        method: 'DELETE',
        headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    if (!response.ok) throw new Error("Failed to delete v2 session");
}

export async function listSessions(): Promise<Array<{session_id: string, title: string, updated_at: string}>> {
    const response = await fetch(`${API_BASE}/v1/session`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) throw new Error("Failed to list sessions");
    return response.json();
}

export async function listV2Sessions(studentId: string = 'anonymous'): Promise<Array<{session_id: string, title: string, updated_at: string, turn_count?: number}>> {
    const params = new URLSearchParams({ student_id: studentId });
    const response = await fetch(`${API_BASE}/v1/version/sessions?${params}`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) return [];
    return response.json();
}

export async function listAllSessions(engineVersion: 'v1' | 'v2' = 'v2', studentId: string = 'anonymous'): Promise<Array<{session_id: string, title: string, updated_at: string, turn_count?: number}>> {
    if (engineVersion === 'v2') {
        return listV2Sessions(studentId);
    }
    return listSessions();
}



export async function askQuestionStream(
    sessionId: string,
    query: string,
    onEvent: (event: string, data: any) => void
): Promise<void> {
    const response = await fetch(`${API_BASE}/v1/session/${sessionId}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ query })
    });

    if (!response.ok) throw new Error("Failed to start stream");
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split('\n');
            let eventType = 'message';
            let eventData = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.substring(7).trim();
                } else if (line.startsWith('data: ')) {
                    eventData = line.substring(6).trim();
                }
            }

            if (eventData) {
                try {
                    const parsedData = JSON.parse(eventData);
                    onEvent(eventType, parsedData);
                } catch (e) {
                    console.error('Failed to parse SSE data', eventData);
                }
            }
        }
    }
}

// =============================================================================
// v2 API — RAG engine (hybrid BM25F + Qdrant semantic search)
// =============================================================================

export interface V2Response {
    answer: string;
    sources: Array<{concept_name: string; concept_id: string; score: number; subject: string; chapter: string}>;
    citations: Array<{concept_id: string; concept_name: string; source_field: string; subject: string; chapter: string}>;
    query: string;
    resolved_query?: string;
    session_id: string;
    grounded: boolean;
    verification: {passed: boolean; reason: string};
    cached?: boolean;
    rate_limited?: boolean;
    cache_stats?: any;
}

export async function startV2Session(studentId: string = "anonymous"): Promise<{session_id: string; student_id: string}> {
    const response = await fetch(`${API_BASE}/v1/version/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ student_id: studentId })
    });
    if (!response.ok) throw new Error("Failed to start v2 session");
    return response.json();
}

export async function queryV2(query: string, sessionId?: string, subject?: string): Promise<V2Response> {
    const response = await fetch(`${API_BASE}/v1/version/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ query, session_id: sessionId, subject })
    });
    if (!response.ok) throw new Error("Failed to query v2");
    return response.json();
}

export async function queryV2Stream(
    query: string,
    sessionId: string | null,
    onEvent: (event: string, data: any) => void
): Promise<void> {
    const response = await fetch(`${API_BASE}/v1/version/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ query, session_id: sessionId })
    });

    if (!response.ok) throw new Error("Failed to start v2 stream");
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split('\n');
            let eventType = 'message';
            let eventData = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.substring(7).trim();
                } else if (line.startsWith('data: ')) {
                    eventData = line.substring(6).trim();
                }
            }

            if (eventData) {
                try {
                    const parsedData = JSON.parse(eventData);
                    onEvent(eventType, parsedData);
                } catch (e) {
                    console.error('Failed to parse SSE data', eventData);
                }
            }
        }
    }
}

export async function getV2Session(sessionId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/v1/version/session/${sessionId}`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) throw new Error("Failed to get v2 session");
    return response.json();
}

export async function getV2History(sessionId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/v1/version/session/${sessionId}/history`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) throw new Error("Failed to get v2 history");
    return response.json();
}

export async function getVersion(): Promise<{version: string; available: string[]}> {
    const response = await fetch(`${API_BASE}/v1/version`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
    if (!response.ok) throw new Error("Failed to get version");
    return response.json();
}

export async function setVersion(version: string): Promise<{version: string; message: string}> {
    const response = await fetch(`${API_BASE}/v1/version`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ version })
    });
    if (!response.ok) throw new Error("Failed to set version");
    return response.json();
}
