'use client'

import React, { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, RotateCcw, BookOpen } from 'lucide-react';

interface Flashcard {
    question: string;
    answer: string;
    concept_name: string;
    concept_id: string;
    chapter: string;
    subject: string;
    card_type: string;
}

interface FlashcardDeck {
    subject: string;
    chapter: string;
    total_cards: number;
    cards: Flashcard[];
}

interface FlashcardDeckProps {
    subject: string;
    chapter: string;
    onClose?: () => void;
}

export function FlashcardDeck({ subject, chapter, onClose }: FlashcardDeckProps) {
    const [deck, setDeck] = useState<FlashcardDeck | null>(null);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isFlipped, setIsFlipped] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchFlashcards();
    }, [subject, chapter]);

    const fetchFlashcards = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`/api/v1/flashcards/${subject}/${encodeURIComponent(chapter)}`);
            if (!response.ok) {
                throw new Error('Failed to load flashcards');
            }
            const data = await response.json();
            setDeck(data);
            setCurrentIndex(0);
            setIsFlipped(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load flashcards');
        } finally {
            setLoading(false);
        }
    };

    const handleNext = () => {
        if (deck && currentIndex < deck.total_cards - 1) {
            setCurrentIndex(currentIndex + 1);
            setIsFlipped(false);
        }
    };

    const handlePrevious = () => {
        if (currentIndex > 0) {
            setCurrentIndex(currentIndex - 1);
            setIsFlipped(false);
        }
    };

    const handleFlip = () => {
        setIsFlipped(!isFlipped);
    };

    const handleShuffle = () => {
        if (deck) {
            const shuffled = [...deck.cards].sort(() => Math.random() - 0.5);
            setDeck({ ...deck, cards: shuffled });
            setCurrentIndex(0);
            setIsFlipped(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="text-slate-400 flex items-center gap-2">
                    <div className="w-6 h-6 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
                    Loading flashcards...
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6 bg-slate-800 rounded-lg">
                <div className="text-red-400 mb-4">{error}</div>
                <button
                    onClick={fetchFlashcards}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                    Retry
                </button>
            </div>
        );
    }

    if (!deck || deck.total_cards === 0) {
        return (
            <div className="p-6 bg-slate-800 rounded-lg text-center">
                <BookOpen className="w-12 h-12 text-slate-500 mx-auto mb-4" />
                <p className="text-slate-400">No flashcards available for this chapter</p>
            </div>
        );
    }

    const currentCard = deck.cards[currentIndex];

    return (
        <div className="bg-slate-800 rounded-lg p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-lg font-semibold text-white">
                        {subject.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} - {chapter}
                    </h3>
                    <p className="text-sm text-slate-400">
                        Card {currentIndex + 1} of {deck.total_cards}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleShuffle}
                        className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded"
                        title="Shuffle cards"
                    >
                        <RotateCcw className="w-5 h-5" />
                    </button>
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="px-3 py-1 text-sm text-slate-400 hover:text-white hover:bg-slate-700 rounded"
                        >
                            Close
                        </button>
                    )}
                </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-slate-700 rounded-full h-2 mb-6">
                <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${((currentIndex + 1) / deck.total_cards) * 100}%` }}
                />
            </div>

            {/* Flashcard */}
            <div
                onClick={handleFlip}
                className={`relative w-full min-h-[300px] cursor-pointer perspective-1000 mb-6 ${
                    isFlipped ? 'rotate-y-180' : ''
                }`}
                style={{ transformStyle: 'preserve-3d' }}
            >
                <div className={`absolute inset-0 backface-hidden ${isFlipped ? 'opacity-0' : 'opacity-100'}`}>
                    <div className="w-full h-full min-h-[300px] bg-gradient-to-br from-slate-700 to-slate-800 rounded-xl p-6 flex flex-col items-center justify-center border border-slate-600">
                        <span className="text-xs text-slate-400 mb-2 uppercase tracking-wider">Question</span>
                        <p className="text-xl text-white text-center leading-relaxed">{currentCard.question}</p>
                        <span className="text-xs text-slate-500 mt-4">Click to reveal answer</span>
                    </div>
                </div>

                <div className={`absolute inset-0 backface-hidden rotate-y-180 ${isFlipped ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="w-full h-full min-h-[300px] bg-gradient-to-br from-blue-900/50 to-slate-800 rounded-xl p-6 flex flex-col items-center justify-center border border-blue-500/30">
                        <span className="text-xs text-blue-300 mb-2 uppercase tracking-wider">Answer</span>
                        <p className="text-lg text-white text-center leading-relaxed">{currentCard.answer}</p>
                        <div className="mt-4 flex items-center gap-2">
                            <span className={`px-2 py-1 rounded text-xs ${
                                currentCard.card_type === 'definition' ? 'bg-green-900/50 text-green-300' :
                                currentCard.card_type === 'formula' ? 'bg-purple-900/50 text-purple-300' :
                                'bg-orange-900/50 text-orange-300'
                            }`}>
                                {currentCard.card_type}
                            </span>
                            <span className="text-xs text-slate-400">{currentCard.concept_name}</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between">
                <button
                    onClick={handlePrevious}
                    disabled={currentIndex === 0}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <ChevronLeft className="w-5 h-5" />
                    Previous
                </button>

                <button
                    onClick={handleFlip}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                    {isFlipped ? 'Show Question' : 'Show Answer'}
                </button>

                <button
                    onClick={handleNext}
                    disabled={currentIndex === deck.total_cards - 1}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Next
                    <ChevronRight className="w-5 h-5" />
                </button>
            </div>

            {/* Keyboard hints */}
            <div className="mt-4 text-center text-xs text-slate-500">
                Press ← → to navigate, Space to flip
            </div>
        </div>
    );
}
