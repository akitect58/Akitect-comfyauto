'use client';

import React, { useState, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { motion } from 'framer-motion';

type Settings = {
    openai_api_key_masked: string;
    openai_api_key_set: boolean;
    comfyui_path: string;
    use_reference_image: boolean;
    prompts: {
        protagonist_prompt: string;
        draft_generation: string;
        story_confirmation: string;
        single_cut_regeneration: string;
        master_character: string;
        scene_image: string;
        veo_video: string;
        title_generation: string;
        negative_prompt: string;
        style_animation: string;
        negative_prompt_animation: string;
    };
};

export default function SettingsView() {
    const [settings, setSettings] = useState<Settings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [activeTab, setActiveTab] = useState<'connection' | 'prompts'>('connection');

    // Form state
    const [apiKey, setApiKey] = useState('');
    const [comfyuiPath, setComfyuiPath] = useState('');
    const [protagonistPrompt, setProtagonistPrompt] = useState('');
    const [draftPrompt, setDraftPrompt] = useState('');
    const [storyPrompt, setStoryPrompt] = useState('');
    const [singleCutPrompt, setSingleCutPrompt] = useState('');
    const [masterCharPrompt, setMasterCharPrompt] = useState('');
    const [sceneImagePrompt, setSceneImagePrompt] = useState('');
    const [veoVideoPrompt, setVeoVideoPrompt] = useState('');
    const [titlePrompt, setTitlePrompt] = useState('');
    const [negativePrompt, setNegativePrompt] = useState('');
    const [animationPrompt, setAnimationPrompt] = useState('');
    const [animationNegativePrompt, setAnimationNegativePrompt] = useState('');
    const [useReferenceImage, setUseReferenceImage] = useState(true);
    const [selectedModel, setSelectedModel] = useState('');
    const [availableModels, setAvailableModels] = useState<string[]>([]);

    useEffect(() => {
        fetchSettings();
        fetchModels();
    }, []);

    const fetchModels = async () => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8s timeout for models

        try {
            const res = await fetch('http://localhost:3501/api/settings/models', { signal: controller.signal });
            clearTimeout(timeoutId);

            if (!res.ok) throw new Error(`Server returned ${res.status}`);

            const data = await res.json();
            if (data.models) {
                setAvailableModels(data.models);
            }
        } catch (e) {
            console.error("Failed to fetch models:", e);
            // No specific error state for models, just log
        }
    };

    const fetchSettings = async () => {
        setIsLoading(true);
        setError(null); // Clear previous errors

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout

        try {
            const res = await fetch('http://localhost:3501/api/settings', { signal: controller.signal });
            clearTimeout(timeoutId);

            if (!res.ok) throw new Error(`Server returned ${res.status}`);

            const data = await res.json();
            setSettings(data);
            setComfyuiPath(data.comfyui_path || '');
            setProtagonistPrompt(data.prompts?.protagonist_prompt || '');
            setDraftPrompt(data.prompts?.draft_generation || '');
            setStoryPrompt(data.prompts?.story_confirmation || '');
            setSingleCutPrompt(data.prompts?.single_cut_regeneration || '');
            setMasterCharPrompt(data.prompts?.master_character || '');
            setSceneImagePrompt(data.prompts?.scene_image || '');
            setVeoVideoPrompt(data.prompts?.veo_video || '');
            setTitlePrompt(data.prompts?.title_generation || '');
            setNegativePrompt(data.prompts?.negative_prompt || '');
            setAnimationPrompt(data.prompts?.style_animation || '');
            setAnimationNegativePrompt(data.prompts?.negative_prompt_animation || '');
            setUseReferenceImage(data.use_reference_image !== false);
            setSelectedModel(data.selected_model || '');
        } catch (e: any) {
            console.error("Failed to fetch settings:", e);
            setError(e.message || "백엔드 서버에 연결할 수 없습니다.");
            // Even on error, stop loading so user is not stuck
            setSettings({
                openai_api_key_masked: '',
                openai_api_key_set: false,
                comfyui_path: '',
                use_reference_image: true,
                prompts: {} as any
            });
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
                    protagonist_prompt: protagonistPrompt,
                    draft_generation: draftPrompt,
                    story_confirmation: storyPrompt,
                    single_cut_regeneration: singleCutPrompt,
                    master_character: masterCharPrompt,
                    scene_image: sceneImagePrompt,
                    veo_video: veoVideoPrompt,
                    title_generation: titlePrompt,
                    negative_prompt: negativePrompt,
                    style_animation: animationPrompt,
                    negative_prompt_animation: animationNegativePrompt
                }
            };

            payload.use_reference_image = useReferenceImage;
            payload.selected_model = selectedModel;

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
                setApiKey('');
                fetchSettings();
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
        <div className="p-8 max-w-4xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-black text-white mb-2">설정 및 환경 정의</h2>
                    <p className="text-slate-400">API 키 및 ComfyUI 경로를 설정합니다.</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-700">
                    <div className={`w-2 h-2 rounded-full ${error ? 'bg-red-500 animate-pulse' : isLoading ? 'bg-amber-500 animate-pulse' : 'bg-green-500 shadow-[0_0_8px_#22c55e]'}`} />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        {error ? 'CONNECTION ERROR' : isLoading ? 'SYNCING...' : 'BACKEND ONLINE'}
                    </span>
                </div>
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 flex items-start gap-4 animate-in fade-in slide-in-from-top-4">
                    <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center text-red-500 shrink-0">
                        <Icon icon="solar:danger-bold-duotone" className="text-3xl" />
                    </div>
                    <div className="flex-1">
                        <h4 className="text-red-400 text-lg font-black mb-1">백엔드 서버에 연결할 수 없습니다</h4>
                        <p className="text-red-400/70 text-sm leading-relaxed mb-4">
                            {error}. <br />
                            백엔드 실행 창(파워쉘)에 에러 메시지가 있는지 확인하거나, 방화벽에서 3501 포트 허용 여부를 체크해 주세요.
                        </p>
                        <button
                            onClick={fetchSettings}
                            className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl transition-all shadow-lg active:scale-95"
                        >
                            연결 재시도
                        </button>
                    </div>
                </div>
            )}
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

            {/* Tab Buttons */}
            <div className="flex gap-2">
                <button
                    onClick={() => setActiveTab('connection')}
                    className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${activeTab === 'connection' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
                >
                    <Icon icon="solar:plug-circle-bold" className="inline mr-2" />연결 설정
                </button>
                <button
                    onClick={() => setActiveTab('prompts')}
                    className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${activeTab === 'prompts' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
                >
                    <Icon icon="solar:document-text-bold" className="inline mr-2" />AI 프롬프트
                </button>
            </div>

            {/* Connection Tab */}
            {activeTab === 'connection' && (
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
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder={settings?.openai_api_key_set ? `현재: ${settings.openai_api_key_masked}` : "sk-..."}
                            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                        />
                        <p className="text-[10px] text-slate-500">새 키를 입력하면 기존 키가 덮어씌워집니다.</p>
                    </div>

                    {/* ComfyUI Path & Model Selection */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <Icon icon="solar:folder-bold" /> ComfyUI 설치 경로
                            </label>
                            <input
                                type="text"
                                value={comfyuiPath}
                                onChange={(e) => setComfyuiPath(e.target.value)}
                                placeholder="C:\ComfyUI_windows_portable\ComfyUI"
                                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono"
                            />
                        </div>

                        {/* Model Selection */}
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <Icon icon="solar:box-minimalistic-bold" /> 기본 모델 (Checkpoint)
                            </label>
                            <div className="relative">
                                <select
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 appearance-none"
                                >
                                    <option value="" disabled>모델 선택...</option>
                                    {availableModels.length > 0 ? (
                                        availableModels.map((model) => (
                                            <option key={model} value={model}>{model}</option>
                                        ))
                                    ) : (
                                        <option value={selectedModel || "RealVisXL_V5.0.safetensors"}>
                                            {selectedModel || "RealVisXL_V5.0.safetensors"} (목록 로딩 실패)
                                        </option>
                                    )}
                                </select>
                                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">
                                    <Icon icon="solar:alt-arrow-down-bold" />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Use Reference Image Toggle */}
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <Icon icon="solar:gallery-bold" /> 이미지 참조 기능 (IP-Adapter)
                        </label>
                        <div className="flex items-center justify-between bg-slate-950 border border-slate-700 rounded-xl px-4 py-3">
                            <div className="flex-1">
                                <p className="text-sm text-white">첫 번째 이미지를 참조로 사용</p>
                                <p className="text-[10px] text-slate-500">img2img를 지원하지 않는 모델을 사용할 경우 끄세요.</p>
                            </div>
                            <button
                                onClick={() => setUseReferenceImage(!useReferenceImage)}
                                className={`w-14 h-7 rounded-full transition-all relative ${useReferenceImage ? 'bg-blue-600' : 'bg-slate-700'}`}
                            >
                                <div
                                    className={`absolute w-5 h-5 bg-white rounded-full top-1 transition-all ${useReferenceImage ? 'left-8' : 'left-1'}`}
                                />
                            </button>
                        </div>
                    </div>
                </motion.div>
            )}


            {/* Prompts Tab */}
            {activeTab === 'prompts' && (
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-4"
                >
                    {/* Protagonist Prompt - 주인공 설정 */}
                    <div className="bg-purple-500/5 border border-purple-500/20 rounded-2xl p-4">
                        <label className="text-xs font-bold text-purple-400 uppercase tracking-widest flex items-center gap-2 mb-2">
                            <Icon icon="solar:user-bold" /> 주인공 프롬프트 (모든 스토리에 적용)
                        </label>
                        <p className="text-xs text-slate-500 mb-3">
                            예: A majestic wild animal (wolf/fox/deer), detailed fur, expressive eyes
                        </p>
                        <textarea
                            value={protagonistPrompt}
                            onChange={(e) => setProtagonistPrompt(e.target.value)}
                            rows={2}
                            className="w-full bg-slate-950 border border-purple-500/30 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-purple-500 font-mono resize-none"
                            placeholder="A majestic golden eagle, hyperrealistic feathers, sharp gaze, national geographic style, 8k uhd"
                        />
                    </div>

                    {/* Negative Prompt - 항상 상단에 */}
                    <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-4">
                        <label className="text-xs font-bold text-red-400 uppercase tracking-widest flex items-center gap-2 mb-2">
                            <Icon icon="solar:forbidden-bold" /> 네거티브 프롬프트 (실사)
                        </label>
                        <textarea
                            value={negativePrompt}
                            onChange={(e) => setNegativePrompt(e.target.value)}
                            rows={3}
                            className="w-full bg-slate-950 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-red-500 font-mono resize-none"
                            placeholder="cgi, 3d render, anime, ..."
                        />
                    </div>

                    {/* Animation Style Prompts */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-pink-500/5 border border-pink-500/20 rounded-2xl p-4">
                            <label className="text-xs font-bold text-pink-400 uppercase tracking-widest flex items-center gap-2 mb-2">
                                <Icon icon="solar:palette-bold" /> 만화 스타일 프롬프트
                            </label>
                            <textarea
                                value={animationPrompt}
                                onChange={(e) => setAnimationPrompt(e.target.value)}
                                rows={3}
                                className="w-full bg-slate-950 border border-pink-500/30 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-pink-500 font-mono resize-none"
                                placeholder="A vertical 16:9 semi-realistic digital portrait..."
                            />
                        </div>
                        <div className="bg-pink-500/5 border border-pink-500/20 rounded-2xl p-4">
                            <label className="text-xs font-bold text-pink-400 uppercase tracking-widest flex items-center gap-2 mb-2">
                                <Icon icon="solar:forbidden-circle-bold" /> 만화 네거티브
                            </label>
                            <textarea
                                value={animationNegativePrompt}
                                onChange={(e) => setAnimationNegativePrompt(e.target.value)}
                                rows={3}
                                className="w-full bg-slate-950 border border-pink-500/30 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-pink-500 font-mono resize-none"
                                placeholder="photorealistic, 3d render..."
                            />
                        </div>
                    </div>

                    {/* Draft Generation */}
                    <PromptSection
                        icon="solar:magic-stick-3-bold"
                        iconColor="text-amber-500"
                        title="초안 생성 (Step 1)"
                        description="10개의 스토리 초안을 생성할 때 사용되는 시스템 프롬프트"
                        value={draftPrompt}
                        onChange={setDraftPrompt}
                    />

                    {/* Story Confirmation */}
                    <PromptSection
                        icon="solar:notebook-bold"
                        iconColor="text-blue-500"
                        title="100컷 스토리 확정 (Step 2)"
                        description="{{cut_count}}, {{story_title}}, {{character_tag}} 등 템플릿 변수 지원"
                        value={storyPrompt}
                        onChange={setStoryPrompt}
                    />

                    {/* Single Cut Regeneration */}
                    <PromptSection
                        icon="solar:refresh-circle-bold"
                        iconColor="text-rose-500"
                        title="단일 컷 재생성"
                        description="{{cut_number}}, {{previous_cut}}, {{next_cut}}, {{emotion_range}} 템플릿 변수 지원"
                        value={singleCutPrompt}
                        onChange={setSingleCutPrompt}
                    />

                    {/* Master Character */}
                    <PromptSection
                        icon="solar:user-circle-bold"
                        iconColor="text-purple-500"
                        title="마스터 캐릭터 프롬프트"
                        description="캐릭터 외형/털/피부 질감에만 집중. 배경·행동 묘사 금지."
                        value={masterCharPrompt}
                        onChange={setMasterCharPrompt}
                    />

                    {/* Scene Image */}
                    <PromptSection
                        icon="solar:gallery-bold"
                        iconColor="text-cyan-500"
                        title="씬별 이미지 프롬프트"
                        description="Pre-action 스냅샷. 조명/앵글/환경 디테일 집중."
                        value={sceneImagePrompt}
                        onChange={setSceneImagePrompt}
                    />

                    {/* VEO Video */}
                    <PromptSection
                        icon="solar:videocamera-record-bold"
                        iconColor="text-green-500"
                        title="VEO 3.1 영상 프롬프트"
                        description="5요소 공식: Cinematography/Subject/Action/Context/Style"
                        value={veoVideoPrompt}
                        onChange={setVeoVideoPrompt}
                    />

                    {/* Title Generation */}
                    <PromptSection
                        icon="solar:text-bold"
                        iconColor="text-orange-500"
                        title="제목 생성 (Step 4)"
                        description="영미권 콘텐츠 마케팅 스타일의 영어 제목 제안."
                        value={titlePrompt}
                        onChange={setTitlePrompt}
                    />
                </motion.div>
            )}
        </div>
    );
}

// 프롬프트 섹션 컴포넌트
function PromptSection({ icon, iconColor, title, description, value, onChange }: {
    icon: string;
    iconColor: string;
    title: string;
    description: string;
    value: string;
    onChange: (v: string) => void;
}) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full p-4 flex items-center justify-between hover:bg-slate-800/50 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <Icon icon={icon} className={`text-xl ${iconColor}`} />
                    <div className="text-left">
                        <div className="text-sm font-bold text-white">{title}</div>
                        <div className="text-[10px] text-slate-500">{description}</div>
                    </div>
                </div>
                <Icon icon={isExpanded ? "solar:alt-arrow-up-bold" : "solar:alt-arrow-down-bold"} className="text-slate-500" />
            </button>
            {isExpanded && (
                <div className="p-4 pt-0">
                    <textarea
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        rows={10}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono resize-none"
                        placeholder="시스템 프롬프트..."
                    />
                </div>
            )}
        </div>
    );
}
