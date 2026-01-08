'use client';

import React, { useState, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { motion } from 'framer-motion';

type Settings = {
    openai_api_key_masked: string;
    openai_api_key_set: boolean;
    comfyui_path: string;
    prompts: {
        draft_generation: string;
        story_confirmation: string;
        title_generation: string;
    };
};

export default function SettingsView() {
    const [settings, setSettings] = useState<Settings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');

    // Form state
    const [apiKey, setApiKey] = useState('');
    const [comfyuiPath, setComfyuiPath] = useState('');
    const [draftPrompt, setDraftPrompt] = useState('');
    const [storyPrompt, setStoryPrompt] = useState('');
    const [titlePrompt, setTitlePrompt] = useState('');

    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        setIsLoading(true);
        try {
            const res = await fetch('http://localhost:3501/api/settings');
            const data = await res.json();
            setSettings(data);
            setComfyuiPath(data.comfyui_path || '');
            setDraftPrompt(data.prompts?.draft_generation || '');
            setStoryPrompt(data.prompts?.story_confirmation || '');
            setTitlePrompt(data.prompts?.title_generation || '');
        } catch (e) {
            console.error("Failed to fetch settings:", e);
        } finally {
            setIsLoading(false);
        }
    };

    const saveSettings = async () => {
        setIsSaving(true);
        setSaveStatus('idle');
        try {
            const payload: any = {
                comfyui_path: comfyuiPath,
                prompts: {
                    draft_generation: draftPrompt,
                    story_confirmation: storyPrompt,
                    title_generation: titlePrompt
                }
            };

            // Only include API key if it was changed
            if (apiKey) {
                payload.openai_api_key = apiKey;
            }

            const res = await fetch('http://localhost:3501/api/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                setSaveStatus('success');
                setApiKey(''); // Clear the input after save
                fetchSettings(); // Refresh to get masked key
                setTimeout(() => setSaveStatus('idle'), 3000);
            } else {
                setSaveStatus('error');
            }
        } catch (e) {
            setSaveStatus('error');
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="p-8 flex items-center justify-center h-full">
                <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="p-8 space-y-8 max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-black text-white mb-1">설정 (Settings)</h2>
                    <p className="text-slate-400 text-sm">API 키, 경로, 프롬프트를 설정하세요.</p>
                </div>
                <button
                    onClick={saveSettings}
                    disabled={isSaving}
                    className={`px-6 py-3 rounded-xl font-black text-sm transition-all flex items-center gap-2 ${saveStatus === 'success' ? 'bg-green-600 text-white' :
                            saveStatus === 'error' ? 'bg-red-600 text-white' :
                                'bg-blue-600 hover:bg-blue-500 text-white'
                        }`}
                >
                    {isSaving ? (
                        <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> 저장 중...</>
                    ) : saveStatus === 'success' ? (
                        <><Icon icon="solar:check-circle-bold" /> 저장 완료</>
                    ) : saveStatus === 'error' ? (
                        <><Icon icon="solar:close-circle-bold" /> 저장 실패</>
                    ) : (
                        <><Icon icon="solar:diskette-bold" /> 설정 저장</>
                    )}
                </button>
            </div>

            {/* API & Path Section */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 space-y-6"
            >
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Icon icon="solar:key-minimalistic-bold" className="text-blue-500" />
                    연결 설정
                </h3>

                {/* OpenAI API Key */}
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Icon icon="simple-icons:openai" /> OpenAI API Key
                        {settings?.openai_api_key_set && (
                            <span className="text-green-500 text-[10px] bg-green-500/10 px-2 py-0.5 rounded">설정됨</span>
                        )}
                    </label>
                    <div className="flex gap-3">
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder={settings?.openai_api_key_set ? `현재: ${settings.openai_api_key_masked}` : "sk-..."}
                            className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <p className="text-[10px] text-slate-500">새 키를 입력하면 기존 키가 덮어씌워집니다. 빈칸으로 두면 기존 키가 유지됩니다.</p>
                </div>

                {/* ComfyUI Path */}
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Icon icon="solar:folder-bold" /> ComfyUI 설치 경로
                    </label>
                    <input
                        type="text"
                        value={comfyuiPath}
                        onChange={(e) => setComfyuiPath(e.target.value)}
                        placeholder="/Users/username/ComfyUI"
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono"
                    />
                    <p className="text-[10px] text-slate-500">ComfyUI가 설치된 폴더의 전체 경로를 입력하세요.</p>
                </div>
            </motion.div>

            {/* Prompts Section */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 space-y-6"
            >
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Icon icon="solar:document-text-bold" className="text-indigo-500" />
                    AI 프롬프트 설정
                </h3>

                {/* Draft Generation Prompt */}
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Icon icon="solar:magic-stick-3-bold" /> 초안 생성 프롬프트 (Step 1)
                    </label>
                    <textarea
                        value={draftPrompt}
                        onChange={(e) => setDraftPrompt(e.target.value)}
                        rows={6}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono resize-none"
                        placeholder="초안 생성용 시스템 프롬프트..."
                    />
                    <p className="text-[10px] text-slate-500">10개의 스토리 초안을 생성할 때 사용되는 시스템 프롬프트입니다.</p>
                </div>

                {/* Story Confirmation Prompt */}
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Icon icon="solar:notebook-bold" /> 스토리 확정 프롬프트 (Step 2)
                    </label>
                    <textarea
                        value={storyPrompt}
                        onChange={(e) => setStoryPrompt(e.target.value)}
                        rows={6}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono resize-none"
                        placeholder="스토리 확정용 시스템 프롬프트..."
                    />
                    <p className="text-[10px] text-slate-500">{'{cuts}'} 변수를 사용하면 컷 수(100 또는 20)로 자동 치환됩니다.</p>
                </div>

                {/* Title Generation Prompt */}
                <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Icon icon="solar:text-bold" /> 제목 생성 프롬프트 (Step 4)
                    </label>
                    <textarea
                        value={titlePrompt}
                        onChange={(e) => setTitlePrompt(e.target.value)}
                        rows={6}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono resize-none"
                        placeholder="제목 생성용 시스템 프롬프트..."
                    />
                    <p className="text-[10px] text-slate-500">영어 제목을 제안할 때 사용되는 시스템 프롬프트입니다.</p>
                </div>
            </motion.div>

            {/* Info Card */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="bg-blue-500/5 border border-blue-500/20 rounded-2xl p-4 flex items-start gap-3"
            >
                <Icon icon="solar:info-circle-bold" className="text-blue-500 text-xl shrink-0 mt-0.5" />
                <div>
                    <p className="text-blue-400 text-sm font-bold mb-1">실제 AI 연동 안내</p>
                    <p className="text-blue-300/70 text-xs leading-relaxed">
                        OpenAI API 키가 설정되면 Mock 데이터 대신 실제 GPT-4o-mini를 호출하여 스토리를 생성합니다.
                        키가 없으면 데모용 하드코딩 데이터가 사용됩니다.
                    </p>
                </div>
            </motion.div>
        </div>
    );
}
