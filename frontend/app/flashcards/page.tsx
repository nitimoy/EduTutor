'use client'

import React, { useState, useEffect } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { FlashcardDeck } from '@/components/flashcards/FlashcardDeck';
import { BookOpen, ChevronDown } from 'lucide-react';

interface ChapterInfo {
    subject: string;
    chapter: string;
    book: string;
    concept_count: number;
    topics: string[];
}

export default function FlashcardsPage() {
    const [selectedSubject, setSelectedSubject] = useState<string>('');
    const [selectedChapter, setSelectedChapter] = useState<string>('');
    const [chapters, setChapters] = useState<ChapterInfo[]>([]);
    const [loading, setLoading] = useState(false);
    const [showDeck, setShowDeck] = useState(false);

    const subjects = ['mathematics', 'physics', 'chemistry'];

    useEffect(() => {
        if (selectedSubject) {
            fetchChapters(selectedSubject);
        }
    }, [selectedSubject]);

    const fetchChapters = async (subject: string) => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/chapters?subject=${subject}`);
            if (response.ok) {
                const data = await response.json();
                // API returns an object with subject keys
                const chapterList = data[subject] || data || [];
                setChapters(Array.isArray(chapterList) ? chapterList : []);
            }
        } catch (err) {
            console.error('Failed to fetch chapters:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleStart = () => {
        if (selectedSubject && selectedChapter) {
            setShowDeck(true);
        }
    };

    return (
        <MainLayout>
            <div className="max-w-4xl mx-auto p-6">
                <div className="flex items-center gap-3 mb-8">
                    <BookOpen className="w-8 h-8 text-blue-400" />
                    <h1 className="text-2xl font-bold text-white">Flashcards</h1>
                </div>

                {!showDeck ? (
                    <div className="bg-slate-800 rounded-lg p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Select Chapter</h2>

                        {/* Subject selector */}
                        <div className="mb-4">
                            <label className="block text-sm text-slate-400 mb-2">Subject</label>
                            <div className="relative">
                                <select
                                    value={selectedSubject}
                                    onChange={(e) => {
                                        setSelectedSubject(e.target.value);
                                        setSelectedChapter('');
                                        setShowDeck(false);
                                    }}
                                    className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 appearance-none cursor-pointer hover:bg-slate-600 transition-colors"
                                >
                                    <option value="">Select a subject...</option>
                                    {subjects.map((subject) => (
                                        <option key={subject} value={subject}>
                                            {subject.charAt(0).toUpperCase() + subject.slice(1)}
                                        </option>
                                    ))}
                                </select>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
                            </div>
                        </div>

                        {/* Chapter selector */}
                        {selectedSubject && (
                            <div className="mb-6">
                                <label className="block text-sm text-slate-400 mb-2">Chapter</label>
                                <div className="relative">
                                    <select
                                        value={selectedChapter}
                                        onChange={(e) => setSelectedChapter(e.target.value)}
                                        className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 appearance-none cursor-pointer hover:bg-slate-600 transition-colors"
                                        disabled={loading}
                                    >
                                        <option value="">
                                            {loading ? 'Loading chapters...' : 'Select a chapter...'}
                                        </option>
                                        {chapters.map((chapter) => (
                                            <option key={chapter.chapter} value={chapter.chapter}>
                                                {chapter.chapter} ({chapter.concept_count} topics)
                                            </option>
                                        ))}
                                    </select>
                                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
                                </div>
                            </div>
                        )}

                        {/* Start button */}
                        <button
                            onClick={handleStart}
                            disabled={!selectedSubject || !selectedChapter}
                            className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            Start Studying
                        </button>

                        {/* Chapter topics preview */}
                        {selectedChapter && chapters.length > 0 && (
                            <div className="mt-6 p-4 bg-slate-700/50 rounded-lg">
                                <h3 className="text-sm font-medium text-slate-300 mb-2">Topics in this chapter:</h3>
                                <div className="flex flex-wrap gap-2">
                                    {chapters
                                        .find(c => c.chapter === selectedChapter)
                                        ?.topics.map((topic, i) => (
                                            <span key={i} className="px-2 py-1 bg-slate-600 text-slate-300 text-xs rounded">
                                                {topic}
                                            </span>
                                        ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <FlashcardDeck
                        subject={selectedSubject}
                        chapter={selectedChapter}
                        onClose={() => setShowDeck(false)}
                    />
                )}
            </div>
        </MainLayout>
    );
}
