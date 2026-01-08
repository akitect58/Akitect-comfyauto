'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';

// Types
type Draft = { id: number; title: string; summary: string; theme: string };
type Cut = { cutNumber: number; description: string };
type TitleSuggestion = { title: string; style: string };

type WorkflowState = {
    step: number;
    mode: 'long' | 'short';
    inputMode: 'category' | 'custom';
    category: string;
    customInput: string;
    drafts: Draft[];
    selectedDraft: Draft | null;
    cuts: Cut[];
    characterPrompt: string;
    editedStory: string;
    titles: TitleSuggestion[];
    selectedTitle: string;
    logs: string[];
    isProcessing: boolean;
    result: any;
};

const CATEGORIES = ["사고", "자연재해", "보은", "미스터리", "서바이벌", "로맨스", "우정", "복수", "성장", "모험"];
const STEPS = ["모드 선택", "주제 입력", "스토리 확정", "이미지 생성", "제목 선택"];

export default function WorkflowController({ onNavigate }: { onNavigate?: (tab: 'generate' | 'history') => void }) {
    const [state, setState] = useState<WorkflowState>({
        step: 0,
        mode: 'long',
        inputMode: 'category',
        category: '',
        customInput: '',
        drafts: [],
        selectedDraft: null,
        cuts: [],
        characterPrompt: '',
        editedStory: '',
        titles: [],
        selectedTitle: '',
        logs: [],
        isProcessing: false,
        result: null
    });
    const logEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [state.logs]);

    // Step Navigation
    const nextStep = () => setState(s => ({ ...s, step: Math.min(s.step + 1, 4) }));
    const prevStep = () => setState(s => ({ ...s, step: Math.max(s.step - 1, 0) }));

    // Step 0 -> Step 1: Mode selected
    const confirmMode = () => nextStep();

    // Step 1: Fetch drafts
    const fetchDrafts = async () => {
        setState(s => ({ ...s, isProcessing: true }));
        try {
            const res = await fetch('http://localhost:3501/api/workflow/drafts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: state.mode,
                    category: state.inputMode === 'category' ? state.category : null,
                    customInput: state.inputMode === 'custom' ? state.customInput : null
                })
            });
            const data = await res.json();
            setState(s => ({ ...s, drafts: data.drafts, isProcessing: false }));
        } catch (e) {
            setState(s => ({ ...s, isProcessing: false }));
        }
    };

    // Step 1 -> Step 2: Select draft and fetch story
    const selectDraft = async (draft: Draft) => {
        setState(s => ({ ...s, selectedDraft: draft, isProcessing: true }));
        try {
            const res = await fetch('http://localhost:3501/api/workflow/story', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: state.mode,
                    draftId: draft.id,
                    draftTitle: draft.title,
                    draftSummary: draft.summary
                })
            });
            const data = await res.json();
            const storyText = data.cuts.map((c: Cut) => `[컷 ${c.cutNumber}] ${c.description}`).join('\n');
            setState(s => ({
                ...s,
                cuts: data.cuts,
                characterPrompt: data.characterPrompt,
                editedStory: storyText,
                isProcessing: false,
                step: 2
            }));
        } catch (e) {
            setState(s => ({ ...s, isProcessing: false }));
        }
    };

    // Step 2 -> Step 3: Start generation
    const startGeneration = () => {
        setState(s => ({ ...s, step: 3, logs: [], isProcessing: true }));

        const cuts = state.mode === 'long' ? 100 : 20;
        const modeStr = state.mode === 'long' ? 'Long Form (16:9)' : 'Short Form (9:16)';

        const eventSource = new EventSource(
            `http://localhost:3501/api/stream?mode=${encodeURIComponent(modeStr)}&topic=${encodeURIComponent(state.selectedDraft?.title || 'Story')}&cuts=${cuts}&concept=기본 (Default)&title=${encodeURIComponent(state.selectedTitle || state.selectedDraft?.title || '')}`
        );

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'log') {
                setState(s => ({ ...s, logs: [...s.logs, data.message] }));
            } else if (data.type === 'result') {
                setState(s => ({ ...s, result: data.data }));
            } else if (data.type === 'done') {
                eventSource.close();
                fetchTitles();
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            setState(s => ({ ...s, isProcessing: false }));
        };
    };

    // Step 3 -> Step 4: Fetch titles
    const fetchTitles = async () => {
        try {
            const res = await fetch('http://localhost:3501/api/workflow/titles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ storyPreview: state.editedStory.substring(0, 500) })
            });
            const data = await res.json();
            setState(s => ({ ...s, titles: data.titles, isProcessing: false, step: 4 }));
        } catch (e) {
            setState(s => ({ ...s, isProcessing: false, step: 4 }));
        }
    };

    // Step 4: Final complete
    const completeWorkflow = () => {
        onNavigate?.('history');
    };

    // Reset
    const resetWorkflow = () => {
        setState({
            step: 0, mode: 'long', inputMode: 'category', category: '', customInput: '',
            drafts: [], selectedDraft: null, cuts: [], characterPrompt: '', editedStory: '',
            titles: [], selectedTitle: '', logs: [], isProcessing: false, result: null
        });
    };

    return (
        <div className="space-y-6">
            {/* Stepper */}
            <div className="flex items-center justify-between bg-slate-900/50 p-4 rounded-2xl border border-slate-800">
                {STEPS.map((label, idx) => (
                    <div key={idx} className="flex items-center">
                        <div className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all ${state.step === idx ? 'bg-blue-600 text-white' :
                            state.step > idx ? 'bg-green-600/20 text-green-400' : 'bg-slate-800 text-slate-500'
                            }`}>
                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${state.step > idx ? 'bg-green-500 text-white' : 'bg-slate-700 text-slate-400'
                                }`}>
                                {state.step > idx ? <Icon icon="solar:check-circle-bold" /> : idx}
                            </div>
                            <span className="text-xs font-bold hidden md:inline">{label}</span>
                        </div>
                        {idx < 4 && <div className={`w-8 h-0.5 mx-2 ${state.step > idx ? 'bg-green-500' : 'bg-slate-700'}`} />}
                    </div>
                ))}
            </div>

            <AnimatePresence mode="wait">
                {/* ===== STEP 0: Mode Selection ===== */}
                {state.step === 0 && (
                    <motion.div key="step0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                        <div className="text-center mb-8">
                            <h2 className="text-3xl font-black text-white mb-2">포맷 선택</h2>
                            <p className="text-slate-400">콘텐츠의 형태를 선택하세요. 모든 설정이 자동으로 최적화됩니다.</p>
                        </div>
                        <div className="grid grid-cols-2 gap-6 max-w-3xl mx-auto">
                            <button
                                onClick={() => setState(s => ({ ...s, mode: 'long' }))}
                                className={`p-8 rounded-3xl border-2 transition-all ${state.mode === 'long'
                                    ? 'border-blue-500 bg-blue-600/10 shadow-[0_0_30px_rgba(37,99,235,0.3)]'
                                    : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                                    }`}
                            >
                                <Icon icon="solar:clapperboard-play-bold-duotone" className="text-5xl text-blue-400 mb-4 mx-auto" />
                                <h3 className="text-xl font-black text-white mb-2">🎬 Long Form</h3>
                                <p className="text-slate-400 text-sm mb-4">유튜브 본 영상, 다큐멘터리</p>
                                <div className="flex justify-center gap-4 text-xs">
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">16:9</span>
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">100컷</span>
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">1920x1080</span>
                                </div>
                            </button>
                            <button
                                onClick={() => setState(s => ({ ...s, mode: 'short' }))}
                                className={`p-8 rounded-3xl border-2 transition-all ${state.mode === 'short'
                                    ? 'border-indigo-500 bg-indigo-600/10 shadow-[0_0_30px_rgba(99,102,241,0.3)]'
                                    : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                                    }`}
                            >
                                <Icon icon="solar:smartphone-bold-duotone" className="text-5xl text-indigo-400 mb-4 mx-auto" />
                                <h3 className="text-xl font-black text-white mb-2">📱 Short Form</h3>
                                <p className="text-slate-400 text-sm mb-4">쇼츠, 릴스, 틱톡</p>
                                <div className="flex justify-center gap-4 text-xs">
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">9:16</span>
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">20컷</span>
                                    <span className="bg-slate-800 px-2 py-1 rounded text-slate-300">1080x1920</span>
                                </div>
                            </button>
                        </div>
                        <div className="flex justify-center pt-8">
                            <button onClick={confirmMode} className="px-12 py-4 bg-blue-600 hover:bg-blue-500 text-white font-black rounded-2xl transition-all shadow-lg">
                                다음 단계 →
                            </button>
                        </div>
                    </motion.div>
                )}

                {/* ===== STEP 1: Topic Selection ===== */}
                {state.step === 1 && (
                    <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                        <div className="text-center mb-6">
                            <h2 className="text-2xl font-black text-white mb-2">주제 선택</h2>
                            <p className="text-slate-400">카테고리를 고르거나 직접 아이디어를 입력하세요.</p>
                        </div>

                        {/* Toggle */}
                        <div className="flex justify-center gap-2 bg-slate-900 p-1 rounded-xl w-fit mx-auto border border-slate-800">
                            <button onClick={() => setState(s => ({ ...s, inputMode: 'category' }))} className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${state.inputMode === 'category' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                                📂 카테고리
                            </button>
                            <button onClick={() => setState(s => ({ ...s, inputMode: 'custom' }))} className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${state.inputMode === 'custom' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                                ✏️ 직접 입력
                            </button>
                        </div>

                        {state.inputMode === 'category' ? (
                            <div className="grid grid-cols-5 gap-3 max-w-4xl mx-auto">
                                {CATEGORIES.map((cat) => (
                                    <button
                                        key={cat}
                                        onClick={() => setState(s => ({ ...s, category: cat }))}
                                        className={`py-4 px-3 rounded-xl text-sm font-bold transition-all ${state.category === cat
                                            ? 'bg-blue-600 text-white border-2 border-blue-400'
                                            : 'bg-slate-800 text-slate-300 border-2 border-transparent hover:border-slate-600'
                                            }`}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <div className="max-w-2xl mx-auto">
                                <textarea
                                    value={state.customInput}
                                    onChange={(e) => setState(s => ({ ...s, customInput: e.target.value }))}
                                    placeholder="당신의 스토리 아이디어를 입력하세요... (예: 우주에서 고립된 고양이의 생존기)"
                                    className="w-full h-32 bg-slate-900 border border-slate-700 rounded-2xl p-4 text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                                />
                            </div>
                        )}

                        <div className="flex justify-center pt-4">
                            <button
                                onClick={fetchDrafts}
                                disabled={state.isProcessing || (state.inputMode === 'category' && !state.category) || (state.inputMode === 'custom' && !state.customInput)}
                                className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-black rounded-2xl transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3"
                            >
                                {state.isProcessing ? (
                                    <><div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> AI 분석 중...</>
                                ) : (
                                    <><Icon icon="solar:magic-stick-3-bold" className="text-xl" /> 10개 초안 생성</>
                                )}
                            </button>
                        </div>

                        {/* Drafts Grid */}
                        {state.drafts.length > 0 && (
                            <div className="grid grid-cols-2 gap-4 mt-8">
                                {state.drafts.map((draft) => (
                                    <motion.div
                                        key={draft.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="bg-slate-900/70 border border-slate-700 rounded-2xl p-5 hover:border-blue-500/50 transition-all group cursor-pointer"
                                        onClick={() => selectDraft(draft)}
                                    >
                                        <div className="flex items-start justify-between mb-2">
                                            <h4 className="font-bold text-white group-hover:text-blue-400 transition-colors">{draft.title}</h4>
                                            <span className="text-[10px] px-2 py-0.5 bg-slate-800 rounded text-slate-400 uppercase">{draft.theme}</span>
                                        </div>
                                        <p className="text-slate-400 text-sm leading-relaxed line-clamp-4">{draft.summary}</p>
                                        <button className="mt-3 w-full py-2 bg-blue-600/20 text-blue-400 rounded-xl text-xs font-bold hover:bg-blue-600 hover:text-white transition-all">
                                            이 초안 선택 →
                                        </button>
                                    </motion.div>
                                ))}
                            </div>
                        )}

                        <div className="flex justify-start pt-4">
                            <button onClick={prevStep} className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl">
                                ← 이전
                            </button>
                        </div>
                    </motion.div>
                )}

                {/* ===== STEP 2: Story Confirmation ===== */}
                {state.step === 2 && (
                    <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-2xl font-black text-white mb-1">스토리 확정</h2>
                                <p className="text-slate-400 text-sm">생성된 {state.mode === 'long' ? 100 : 20}컷 스토리를 검토하고 수정하세요.</p>
                            </div>
                            <div className="bg-slate-800 px-4 py-2 rounded-xl border border-slate-700">
                                <span className="text-xs text-slate-400">선택 초안: </span>
                                <span className="text-white font-bold">{state.selectedDraft?.title}</span>
                            </div>
                        </div>

                        <div className="grid grid-cols-3 gap-6">
                            <div className="col-span-2 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
                                <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                                    <span className="text-xs font-bold text-slate-400 uppercase">📝 상세 스토리 ({state.mode === 'long' ? 100 : 20}컷)</span>
                                    <span className="text-[10px] text-slate-500">{state.editedStory.length} 자</span>
                                </div>
                                <textarea
                                    value={state.editedStory}
                                    onChange={(e) => setState(s => ({ ...s, editedStory: e.target.value }))}
                                    className="w-full h-[400px] bg-transparent p-4 text-slate-300 text-sm leading-relaxed focus:outline-none resize-none custom-scrollbar"
                                />
                            </div>


                            <div className="flex gap-4">
                                {/* Character Prompt */}
                                <div className="flex-1 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden flex flex-col">
                                    <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700">
                                        <span className="text-xs font-bold text-slate-400 uppercase">🎭 캐릭터 프롬프트</span>
                                    </div>
                                    <textarea
                                        value={state.characterPrompt}
                                        onChange={(e) => setState(s => ({ ...s, characterPrompt: e.target.value }))}
                                        className="flex-1 p-4 bg-transparent text-slate-400 text-xs leading-relaxed font-mono resize-none focus:outline-none custom-scrollbar"
                                    />
                                </div>

                                {/* Reference Image Upload */}
                                <div className="w-1/3 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden flex flex-col">
                                    <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700">
                                        <span className="text-xs font-bold text-slate-400 uppercase">🖼️ 주인공 참조 이미지 (IP-Adapter)</span>
                                    </div>
                                    <div className="flex-1 p-4 flex flex-col items-center justify-center relative group cursor-pointer" onClick={() => document.getElementById('ref-image-upload')?.click()}>
                                        <input
                                            type="file"
                                            id="ref-image-upload"
                                            className="hidden"
                                            accept="image/*"
                                            onChange={async (e) => {
                                                const file = e.target.files?.[0];
                                                if (file) {
                                                    const reader = new FileReader();
                                                    reader.onloadend = async () => {
                                                        const base64 = reader.result as string;
                                                        // Upload to server
                                                        try {
                                                            const res = await fetch('http://localhost:3501/api/workflow/upload_reference', {
                                                                method: 'POST',
                                                                headers: { 'Content-Type': 'application/json' },
                                                                body: JSON.stringify({ image: base64, filename: file.name })
                                                            });
                                                            const data = await res.json();
                                                            if (data.success) {
                                                                // Use path returned from server
                                                                setState(s => ({ ...s, referenceImage: data.path, referencePreview: base64 }));
                                                                console.log("Uploaded:", data.path);
                                                            }
                                                        } catch (err) {
                                                            console.error("Upload failed", err);
                                                        }
                                                    };
                                                    reader.readAsDataURL(file);
                                                }
                                            }}
                                        />

                                        {(state as any).referencePreview ? (
                                            <div className="relative w-full h-full">
                                                <img src={(state as any).referencePreview} alt="Reference" className="w-full h-full object-cover rounded-lg" />
                                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-lg">
                                                    <span className="text-white text-xs font-bold">이미지 변경</span>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-center p-4 border-2 border-dashed border-slate-700 rounded-xl group-hover:border-blue-500 transition-colors w-full h-full flex flex-col items-center justify-center">
                                                <Icon icon="solar:camera-add-bold" className="text-3xl text-slate-600 group-hover:text-blue-500 mb-2 transition-colors" />
                                                <span className="text-xs text-slate-500 group-hover:text-blue-400 transition-colors">이미지 업로드</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-between pt-4">
                            <button onClick={prevStep} className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl">
                                ← 이전
                            </button>
                            <button onClick={startGeneration} className="px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-black rounded-2xl transition-all shadow-lg flex items-center gap-3">
                                <Icon icon="solar:play-bold" className="text-xl" /> 이미지 생성 시작
                            </button>
                        </div>
                    </motion.div >
                )
                }

                {/* ===== STEP 3: Generation ===== */}
                {
                    state.step === 3 && (
                        <motion.div key="step3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                            <div className="text-center mb-4">
                                <h2 className="text-2xl font-black text-white mb-2">이미지 생성 중...</h2>
                                <p className="text-slate-400">AI가 {state.mode === 'long' ? 100 : 20}컷의 실사 이미지를 생성하고 있습니다.</p>
                            </div>

                            <div className="bg-black/50 border border-slate-800 rounded-2xl h-[400px] overflow-y-auto p-6 font-mono text-xs custom-scrollbar">
                                {state.logs.length === 0 ? (
                                    <div className="h-full flex items-center justify-center text-slate-600">
                                        <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        {state.logs.map((log, i) => (
                                            <div key={i} className="text-slate-400">{log}</div>
                                        ))}
                                        <div ref={logEndRef} />
                                    </div>
                                )}
                            </div>

                            {state.isProcessing && (
                                <div className="flex justify-center">
                                    <div className="flex items-center gap-3 text-blue-400">
                                        <div className="w-5 h-5 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                                        <span className="text-sm font-medium">처리 중...</span>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    )
                }

                {/* ===== STEP 4: Title Selection ===== */}
                {
                    state.step === 4 && (
                        <motion.div key="step4" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">
                            <div className="text-center mb-6">
                                <h2 className="text-2xl font-black text-white mb-2">🏆 제목 선택</h2>
                                <p className="text-slate-400">AI가 제안하는 영어 제목 중 하나를 선택하세요. 폴더명에 자동 적용됩니다.</p>
                            </div>

                            {state.result && (
                                <div className="flex justify-center mb-6">
                                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-4 flex items-center gap-4">
                                        <img src={state.result.image_url} alt="Preview" className="w-24 h-16 rounded-lg object-cover" />
                                        <div>
                                            <p className="text-white font-bold">{state.result.title}</p>
                                            <p className="text-slate-400 text-xs">{state.result.cuts}컷 · {state.result.resolution}</p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
                                {state.titles.map((t, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setState(s => ({ ...s, selectedTitle: t.title }))}
                                        className={`p-4 rounded-2xl border-2 transition-all text-left ${state.selectedTitle === t.title
                                            ? 'border-blue-500 bg-blue-600/10'
                                            : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                                            }`}
                                    >
                                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded mb-2 inline-block ${t.style === 'emotional' ? 'bg-pink-500/20 text-pink-400' :
                                            t.style === 'impact' ? 'bg-orange-500/20 text-orange-400' :
                                                'bg-blue-500/20 text-blue-400'
                                            }`}>{t.style}</span>
                                        <p className="text-white font-bold text-sm leading-snug">{t.title}</p>
                                    </button>
                                ))}
                            </div>

                            <div className="flex justify-center pt-8 gap-4">
                                <button onClick={resetWorkflow} className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl">
                                    🔄 처음부터
                                </button>
                                <button
                                    onClick={completeWorkflow}
                                    disabled={!state.selectedTitle}
                                    className="px-10 py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-black rounded-2xl transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3"
                                >
                                    <Icon icon="solar:check-circle-bold" className="text-xl" /> 워크플로우 완료
                                </button>
                            </div>
                        </motion.div>
                    )
                }
            </AnimatePresence >
        </div >
    );
}
