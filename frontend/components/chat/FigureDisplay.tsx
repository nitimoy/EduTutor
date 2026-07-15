'use client'

import React, { useState, useEffect } from 'react';
import { Image, Loader2, AlertCircle } from 'lucide-react';

interface FigureDisplayProps {
    figureIds: string[];
    subject: string;
    book: string;
}

export function FigureDisplay({ figureIds, subject, book }: FigureDisplayProps) {
    const [loadedCount, setLoadedCount] = useState(0);
    const [failedCount, setFailedCount] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Reset counts when figureIds change
        setLoadedCount(0);
        setFailedCount(0);
        setLoading(true);
    }, [figureIds]);

    useEffect(() => {
        // Check if all figures have loaded or failed
        if (loadedCount + failedCount >= figureIds.length && figureIds.length > 0) {
            setLoading(false);
        }
    }, [loadedCount, failedCount, figureIds.length]);

    if (!figureIds || figureIds.length === 0) return null;

    const allFailed = failedCount === figureIds.length;
    const someLoaded = loadedCount > 0;

    return (
        <div className="mt-4 pt-4 border-t border-slate-800/60">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1">
                <Image className="w-3 h-3" /> Textbook Figures
            </h4>

            {/* Work in progress message */}
            {allFailed && (
                <div className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/30 mb-3">
                    <div className="flex items-center gap-2 text-amber-400/80">
                        <AlertCircle className="w-4 h-4" />
                        <span className="text-xs">
                            Figure extraction is still in progress. The textbook contains diagrams that will be available in a future update.
                        </span>
                    </div>
                </div>
            )}

            {/* Loading indicator */}
            {loading && !allFailed && (
                <div className="flex items-center gap-2 text-slate-500 mb-3">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span className="text-xs">Loading figures...</span>
                </div>
            )}

            {/* Figure grid */}
            <div className="flex flex-wrap gap-3">
                {figureIds.map((figId: string) => (
                    <FigureItem
                        key={figId}
                        figId={figId}
                        subject={subject}
                        book={book}
                        onLoad={() => setLoadedCount(prev => prev + 1)}
                        onError={() => setFailedCount(prev => prev + 1)}
                    />
                ))}
            </div>

            {/* Partial success message */}
            {someLoaded && !allFailed && failedCount > 0 && (
                <p className="text-[10px] text-slate-600 mt-2">
                    {loadedCount} of {figureIds.length} figures loaded. Some figures may not be available yet.
                </p>
            )}
        </div>
    );
}

function FigureItem({
    figId,
    subject,
    book,
    onLoad,
    onError,
}: {
    figId: string;
    subject: string;
    book: string;
    onLoad: () => void;
    onError: () => void;
}) {
    const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
    const [retryCount, setRetryCount] = useState(0);

    const src = `/api/v1/figures/${subject}/${book}/${figId}`;

    const handleLoad = () => {
        setStatus('loaded');
        onLoad();
    };

    const handleError = () => {
        if (retryCount < 2) {
            // Retry once
            setRetryCount(prev => prev + 1);
        } else {
            setStatus('error');
            onError();
        }
    };

    if (status === 'error') {
        return null; // Don't show failed images
    }

    return (
        <div className="bg-slate-800/50 rounded-lg p-2 border border-slate-700/50">
            <img
                src={`${src}${retryCount > 0 ? '?retry=' + retryCount : ''}`}
                alt="Textbook figure"
                className="max-w-[300px] max-h-[200px] rounded"
                loading="lazy"
                onLoad={handleLoad}
                onError={handleError}
            />
        </div>
    );
}
