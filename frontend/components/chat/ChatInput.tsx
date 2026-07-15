'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sigma, Eye, EyeOff, Trash2, Copy, Clipboard } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface ChatInputProps {
    onSend: (query: string) => void;
    disabled?: boolean;
}

// LaTeX templates for common PCM patterns
const LATEX_TEMPLATES = [
    { label: 'Matrix 2×2', latex: '\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}' },
    { label: 'Matrix 3×3', latex: '\\begin{bmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{bmatrix}' },
    { label: 'Fraction', latex: '\\frac{a}{b}' },
    { label: 'Square root', latex: '\\sqrt{x}' },
    { label: 'Integral', latex: '\\int_{a}^{b} f(x) \\, dx' },
    { label: 'Sum', latex: '\\sum_{i=1}^{n} a_i' },
    { label: 'Product', latex: '\\prod_{i=1}^{n} a_i' },
    { label: 'Limit', latex: '\\lim_{x \\to \\infty} f(x)' },
    { label: 'Derivative', latex: '\\frac{d}{dx} f(x)' },
    { label: 'Partial', latex: '\\frac{\\partial f}{\\partial x}' },
    { label: 'Chemical', latex: '\\ce{H2O -> H+ + OH-}' },
];

// Quick symbols organized by category
const QUICK_SYMBOLS = [
    { label: 'Math', symbols: ['²', '³', 'ⁿ', '₁', '₂', '₃', 'ᵢ', 'ⱼ', '∑', '∏', '∫', '∂', '∇', '√', '∞', '±', '×', '÷', '°'] },
    { label: 'Greek', symbols: ['α', 'β', 'γ', 'δ', 'ε', 'θ', 'λ', 'μ', 'π', 'σ', 'φ', 'ω', 'Δ', 'Σ', 'Ω', 'η', 'τ', 'ρ'] },
    { label: 'Arrow', symbols: ['→', '↔', '⇒', '⇔', '←', '↑', '↓', '↦', '⟶'] },
    { label: 'Compare', symbols: ['≤', '≥', '≠', '≈', '≡', '∈', '∉', '⊂', '⊃', '∪', '∩', '⊂=', '⊃='] },
    { label: 'Logic', symbols: ['∀', '∃', '¬', '∧', '∨', '⊕', '⊥', '∥', '∠', '∝'] },
    { label: 'Chem', symbols: ['→', '⇌', '↑', '↓', 'Δ', '°', '±', '₂', '₃', '⁺', '⁻'] },
];

// Matrix template helpers (short labels, full LaTeX on click)
const MATRIX_TEMPLATES = [
    { label: '[ ]', latex: '\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}', title: '2×2 Matrix' },
    { label: '( )', latex: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}', title: '2×2 Parentheses' },
    { label: '| |', latex: '\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}', title: '2×2 Determinant' },
    { label: '3×3', latex: '\\begin{bmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{bmatrix}', title: '3×3 Matrix' },
];

export function ChatInput({ onSend, disabled }: ChatInputProps) {
    const [query, setQuery] = useState("");
    const [showToolbar, setShowToolbar] = useState(false);
    const [showPreview, setShowPreview] = useState(true);
    const [showTemplates, setShowTemplates] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [query]);

    const handleSend = () => {
        if (query.trim() && !disabled) {
            onSend(query.trim());
            setQuery("");
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
        // Tab to insert spaces instead of changing focus
        if (e.key === 'Tab') {
            e.preventDefault();
            insertAtCursor('  ');
        }
    };

    const insertAtCursor = (text: string) => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const newText = query.substring(0, start) + text + query.substring(end);
        setQuery(newText);

        setTimeout(() => {
            textarea.focus();
            const newPos = start + text.length;
            textarea.selectionStart = textarea.selectionEnd = newPos;
        }, 0);
    };

    const insertTemplate = (latex: string) => {
        insertAtCursor(latex);
        setShowTemplates(false);
    };

    const handlePaste = useCallback((e: React.ClipboardEvent) => {
        // Get pasted text
        const pastedText = e.clipboardData.getData('text');

        // Check if it looks like it has mathematical structure
        // (multiple numbers separated by spaces/tabs in a grid pattern)
        const lines = pastedText.split('\n').filter(l => l.trim());
        const hasGridPattern = lines.length > 1 && lines.some(l => l.includes('\t') || l.includes('  '));

        if (hasGridPattern) {
            // Try to convert tab/space-separated values to LaTeX matrix
            e.preventDefault();
            const matrixRows = lines.map(l => {
                const cells = l.split(/\t+|\s{2,}/).filter(c => c.trim());
                return cells.join(' & ');
            }).join(' \\\\ ');

            const latexMatrix = `\\begin{bmatrix} ${matrixRows} \\end{bmatrix}`;
            insertAtCursor(latexMatrix);
            return;
        }

        // For single-line pastes with numbers and operators, try to preserve structure
        if (pastedText.match(/^[\d\s\+\-\*\/\=\(\)\[\]\.]+$/)) {
            // Pure math expression - keep as-is but wrap in math mode if needed
            // Don't prevent default - let normal paste happen
        }
    }, [query]);

    // Build preview markdown
    const previewContent = query
        ? query.replace(/\n/g, '  \n')
        : '';

    return (
        <div className="relative max-w-3xl mx-auto w-full px-4">
            {/* Templates Panel */}
            <AnimatePresence>
                {showTemplates && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden mb-2"
                    >
                        <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-3">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400 font-medium">LaTeX Templates</span>
                                <button onClick={() => setShowTemplates(false)} className="text-slate-500 hover:text-slate-300 text-xs">Close</button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {LATEX_TEMPLATES.map((t) => (
                                    <button
                                        key={t.label}
                                        onClick={() => insertTemplate(t.latex)}
                                        className="px-3 py-1.5 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white rounded-lg transition-colors"
                                        title={t.latex}
                                    >
                                        {t.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Quick Symbols Toolbar */}
            <AnimatePresence>
                {showToolbar && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden mb-2"
                    >
                        <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-3 space-y-2">
                            {QUICK_SYMBOLS.map((group) => (
                                <div key={group.label} className="flex items-start gap-2">
                                    <span className="text-[10px] text-slate-500 w-14 shrink-0 uppercase tracking-wider pt-1">
                                        {group.label}
                                    </span>
                                    <div className="flex flex-wrap gap-1">
                                        {group.symbols.map((symbol, i) => (
                                            <button
                                                key={`${group.label}-${i}`}
                                                onClick={() => insertAtCursor(symbol)}
                                                className="px-2 py-1 text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white rounded transition-colors font-mono min-w-[32px]"
                                                title={`Insert ${symbol}`}
                                            >
                                                {symbol}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {/* Matrix templates row */}
                            <div className="flex items-start gap-2">
                                <span className="text-[10px] text-slate-500 w-14 shrink-0 uppercase tracking-wider pt-1">
                                    Matrix
                                </span>
                                <div className="flex flex-wrap gap-1">
                                    {MATRIX_TEMPLATES.map((t) => (
                                        <button
                                            key={t.label}
                                            onClick={() => insertAtCursor(t.latex)}
                                            className="px-2 py-1 text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white rounded transition-colors font-mono min-w-[32px]"
                                            title={t.title}
                                        >
                                            {t.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                                <p className="text-[10px] text-slate-600">
                                    Paste from PDF? Numbers will be auto-converted to matrix format.
                                </p>
                                <button
                                    onClick={() => setShowTemplates(true)}
                                    className="text-[10px] text-blue-400 hover:text-blue-300"
                                >
                                    More templates →
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Live Preview */}
            {showPreview && query && query.includes('\\') && (
                <div className="mb-2 bg-slate-900/80 border border-slate-700/30 rounded-xl p-3 max-h-40 overflow-y-auto">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider">Preview</span>
                    </div>
                    <div className="text-sm text-slate-200 prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown
                            remarkPlugins={[remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                        >
                            {`$${query}$`}
                        </ReactMarkdown>
                    </div>
                </div>
            )}

            {/* Input Area */}
            <motion.div
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-xl flex items-end p-2 focus-within:border-blue-500/50 transition-colors duration-300"
            >
                {/* Toolbar toggle */}
                <button
                    onClick={() => setShowToolbar(!showToolbar)}
                    className={`p-2 rounded-lg transition-colors mb-1 shrink-0 ${
                        showToolbar
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                    }`}
                    title="Math symbols & templates"
                >
                    <Sigma className="w-5 h-5" />
                </button>

                {/* Preview toggle */}
                <button
                    onClick={() => setShowPreview(!showPreview)}
                    className={`p-2 rounded-lg transition-colors mb-1 shrink-0 ${
                        showPreview
                            ? 'text-slate-400 hover:text-slate-200'
                            : 'text-slate-600 hover:text-slate-400'
                    }`}
                    title={showPreview ? "Hide preview" : "Show preview"}
                >
                    {showPreview ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                </button>

                {/* Clear button */}
                {query && (
                    <button
                        onClick={() => setQuery("")}
                        className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors mb-1 shrink-0"
                        title="Clear"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                )}

                <textarea
                    ref={textareaRef}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    disabled={disabled}
                    placeholder="Type your question... (supports LaTeX: \frac, \sqrt, \begin{bmatrix} etc.)"
                    className="w-full max-h-[200px] bg-transparent text-slate-100 placeholder-slate-500 px-4 py-3 outline-none resize-none disabled:opacity-50 font-mono text-sm"
                    rows={1}
                />
                <button
                    onClick={handleSend}
                    disabled={disabled || !query.trim()}
                    className="p-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl transition-colors mb-1 mr-1 shrink-0"
                >
                    <Send className="w-5 h-5" />
                </button>
            </motion.div>
        </div>
    );
}
