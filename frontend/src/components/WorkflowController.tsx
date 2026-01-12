'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';

// Types
type Draft = { id: number; title: string; summary: string; theme: string };
type Cut = {
    cutNumber: number;
    description: string;
    imagePrompt?: string;
    characterTag?: string;
    physicsDetail?: string;
    lightingCondition?: string;
    weatherAtmosphere?: string;
};
type TitleSuggestion = { title: string; style: string };

type WorkflowState = {
    step: number;
    mode: 'long' | 'short';
    style: 'photoreal' | 'animation';
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
    loadingMessage: string;
    loadingDetail: string;
    streamingText: string;
    referenceImage: string | null;
    referenceConfirmed: boolean;
    currentCutIndex: number;
    result: any;
    currentImage: string | null;
};


const CATEGORIES = [
    "사고·부상",
    "자연재해",
    "학대·방치·호딩",
    "보은 및 영웅적 행동",
    "도시형 고립",
    "유기 및 유실",
    "모성애",
    "장애 및 노령 동물의 생존",
    "종을 뛰어넘는 우정",
    "사회적 약자와의 동행"
];
const STEPS = ["모드 선택", "주제 입력", "스토리 확정", "이미지 생성", "제목 선택"];

export default function WorkflowController({ onNavigate }: { onNavigate?: (tab: 'generate' | 'history') => void }) {
    const [state, setState] = useState<WorkflowState>({
        step: 0,
        mode: 'long',
        style: 'photoreal',
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
        loadingMessage: '',
        loadingDetail: '',
        streamingText: '',
        referenceImage: null,
        referenceConfirmed: false,
        currentCutIndex: 0,
        result: null,
        currentImage: null
    });
    // 10개 초안의 개별 스트리밍 텍스트
    const [streamingTexts, setStreamingTexts] = useState<{ [key: number]: string }>({});
    // 이미지 참조 기능 사용 여부 (설정에서 불러옴)
    const [useReferenceImage, setUseReferenceImage] = useState(true);
    const logEndRef = useRef<HTMLDivElement>(null);

    const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'error'>('checking');

    // 설정에서 use_reference_image 값 불러오기
    useEffect(() => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);

        fetch('http://localhost:3501/api/settings', { signal: controller.signal })
            .then(res => res.json())
            .then(data => {
                clearTimeout(timeoutId);
                setUseReferenceImage(data.use_reference_image !== false);
                setBackendStatus('connected');
            })
            .catch(() => {
                setBackendStatus('error');
            });

        return () => clearTimeout(timeoutId);
    }, []);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [state.logs]);


    // Step Navigation
    const nextStep = () => setState(s => ({ ...s, step: Math.min(s.step + 1, 4) }));
    const prevStep = () => setState(s => ({ ...s, step: Math.max(s.step - 1, 0) }));

    // Step 0 -> Step 1: Mode selected
    const confirmMode = () => {
        if (state.style === 'animation') {
            // Skip Step 1 (Topic Selection) and jump to Step 2 (Direct Input)
            setState(s => ({ ...s, step: 2 }));
        } else {
            nextStep();
        }
    };

    // Modal states for save/load/delete
    const [showDraftsModal, setShowDraftsModal] = useState(false);
    const [modalMode, setModalMode] = useState<'save' | 'load' | 'delete'>('load');
    const [saveType, setSaveType] = useState<'draft' | 'story'>('draft'); // 'draft' or 'story'
    const [saveTitle, setSaveTitle] = useState('');

    // Split saved items for load mode
    const [savedDrafts, setSavedDrafts] = useState<any[]>([]);
    const [savedStories, setSavedStories] = useState<any[]>([]);
    // For delete/save mode, we still use a single active list or just reuse the above

    // Draft Detail & Stream states
    const [showDraftDetailModal, setShowDraftDetailModal] = useState(false);
    const [editingDraft, setEditingDraft] = useState<Draft | null>(null);
    const [isStoryStreaming, setIsStoryStreaming] = useState(false);
    const [storyStreamingText, setStoryStreamingText] = useState('');
    const [storyStreamingLogRef, setStoryStreamingLogRef] = useState<HTMLDivElement | null>(null);
    const eventSourceStreamRef = useRef<EventSource | null>(null);

    // Auto-scroll for story streaming
    useEffect(() => {
        if (storyStreamingLogRef) {
            storyStreamingLogRef.scrollTop = storyStreamingLogRef.scrollHeight;
        }
    }, [storyStreamingText, storyStreamingLogRef]);

    // Stop streaming
    const stopStreaming = () => {
        if (eventSourceStreamRef.current) {
            eventSourceStreamRef.current.close();
            eventSourceStreamRef.current = null;
        }
        setIsStoryStreaming(false);
    };

    // Load saved items list
    const refreshSavedItems = () => {
        // Load both lists
        const drafts = JSON.parse(localStorage.getItem('akitect_drafts_list') || '[]');
        const stories = JSON.parse(localStorage.getItem('akitect_stories_list') || '[]');
        setSavedDrafts(drafts);
        setSavedStories(stories);
    };

    // Open modal
    type ModalMode = 'save' | 'load' | 'delete';
    type SaveType = 'draft' | 'story';

    const openDraftsModal = (mode: ModalMode, type: SaveType = 'draft') => {
        setModalMode(mode);
        // saveType is mainly relevant for 'save' and 'delete' modes. 
        // For 'load', we show both, but we can default to one if needed for some UI state, though split view ignores it.
        setSaveType(type);
        setSaveTitle(`${type === 'draft' ? '초안' : '스토리'}_${new Date().toLocaleDateString()}`);

        refreshSavedItems();
        setShowDraftsModal(true);
    };

    // Save item
    const saveItem = () => {
        if (!saveTitle.trim()) return;

        let saveData: any;

        if (saveType === 'story') {
            saveData = {
                title: saveTitle,
                mode: state.mode,
                selectedDraft: state.selectedDraft,
                cuts: state.cuts,
                characterPrompt: state.characterPrompt,
                editedStory: state.editedStory,
                savedAt: new Date().toISOString()
            };
        } else {
            saveData = {
                title: saveTitle,
                category: state.category,
                inputMode: state.inputMode,
                customInput: state.customInput,
                drafts: state.drafts,
                savedAt: new Date().toISOString()
            };
        }

        const key = saveType === 'story' ? 'akitect_stories_list' : 'akitect_drafts_list';
        const existingSaves = JSON.parse(localStorage.getItem(key) || '[]');
        existingSaves.push(saveData);
        localStorage.setItem(key, JSON.stringify(existingSaves));
        setShowDraftsModal(false);
        refreshSavedItems();
    };

    // Load item and apply to state
    const loadItem = (item: any, type: 'draft' | 'story') => {
        if (!item) return;

        if (type === 'story') {
            setState(s => ({
                ...s,
                mode: item.mode || 'long',
                selectedDraft: item.selectedDraft,
                cuts: item.cuts || [],
                characterPrompt: item.characterPrompt || '',
                editedStory: item.editedStory || '',
                step: 2, // Jump to Step 2 (Story Confirmation)
                isProcessing: false
            }));
        } else {
            setState(s => ({
                ...s,
                category: item.category || '',
                inputMode: item.inputMode || 'category',
                customInput: item.customInput || '',
                drafts: item.drafts || [],
                step: 1, // Stay at Step 1 (Topic/Drafts)
                isProcessing: false,
                loadingMessage: '',
                loadingDetail: ''
            }));
        }
        setStreamingTexts({});
        setShowDraftsModal(false);
    };


    // Delete saved item
    const deleteItem = (index: number, type: 'draft' | 'story' = saveType) => {
        const key = type === 'story' ? 'akitect_stories_list' : 'akitect_drafts_list';

        const list = type === 'story' ? [...savedStories] : [...savedDrafts];
        list.splice(index, 1);

        localStorage.setItem(key, JSON.stringify(list));
        refreshSavedItems();
    };

    // Delete all saved items
    const deleteAllItems = () => {
        const key = saveType === 'story' ? 'akitect_stories_list' : 'akitect_drafts_list';
        localStorage.removeItem(key);
        refreshSavedItems();
    };


    // Step 1: Fetch drafts with parallel processing (10 concurrent API calls)
    const fetchDrafts = async () => {
        setState(s => ({ ...s, isProcessing: true, loadingMessage: 'AI 초안 생성 중 (병렬 스트리밍)', loadingDetail: 'GET /api/workflow/drafts/parallel', drafts: [] }));
        setStreamingTexts({}); // Reset streaming texts

        const categoryParam = state.inputMode === 'category' ? state.category : '';
        const customParam = state.inputMode === 'custom' ? state.customInput : '';
        const url = `http://localhost:3501/api/workflow/drafts/parallel?mode=${state.mode}&category=${encodeURIComponent(categoryParam)}&customInput=${encodeURIComponent(customParam)}`;

        const eventSource = new EventSource(url);

        // Handle streaming text delta for each draft
        eventSource.addEventListener('delta', (event: any) => {
            const data = JSON.parse(event.data);
            const { draft_id, text } = data;
            setStreamingTexts(prev => ({
                ...prev,
                [draft_id]: (prev[draft_id] || '') + text
            }));
        });

        eventSource.addEventListener('draft', (event: any) => {
            const draft = JSON.parse(event.data);
            setState(s => ({
                ...s,
                drafts: [...s.drafts, draft].sort((a, b) => a.id - b.id)
            }));
        });

        eventSource.addEventListener('complete', (event: any) => {
            setState(s => ({ ...s, isProcessing: false, loadingMessage: '', loadingDetail: '' }));
            setStreamingTexts({}); // Clear streaming texts when done
            eventSource.close();
        });

        eventSource.addEventListener('error', (event: any) => {
            console.error('SSE Error:', event);
            setState(s => ({ ...s, isProcessing: false, loadingMessage: '', loadingDetail: '' }));
            eventSource.close();
        });
        eventSource.onerror = () => {
            eventSource.close();
            setState(s => ({ ...s, isProcessing: false, loadingMessage: '', loadingDetail: '' }));
        };
    };

    // Regenerate a single failed draft
    const regenerateDraft = async (draftId: number) => {
        // Find existing draft to show loading state
        setState(s => ({
            ...s,
            drafts: s.drafts.map(d => d.id === draftId ? { ...d, summary: '재생성 중...', theme: 'loading' } : d)
        }));

        try {
            const categoryParam = state.inputMode === 'category' ? state.category : '';
            const customParam = state.inputMode === 'custom' ? state.customInput : '';

            const res = await fetch('http://localhost:3501/api/workflow/draft/regenerate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    draftId,
                    mode: state.mode,
                    category: categoryParam,
                    customInput: customParam
                })
            });

            const data = await res.json();
            if (data.success && data.draft) {
                setState(s => ({
                    ...s,
                    drafts: s.drafts.map(d => d.id === draftId ? data.draft : d)
                }));
            } else {
                throw new Error(data.error || 'Failed to regenerate');
            }
        } catch (e) {
            setState(s => ({
                ...s,
                drafts: s.drafts.map(d => d.id === draftId ? { ...d, title: 'Error', summary: '재생성 실패: ' + String(e), theme: 'error' } : d)
            }));
        }
    };


    // Step 1 -> Step 2: Open Draft Detail Modal
    const selectDraft = (draft: Draft) => {
        setEditingDraft({ ...draft });
        setShowDraftDetailModal(true);
    };

    // Step 2 Stream: Start Story Generation Stream
    const startStoryStream = async () => {
        if (!editingDraft) return;

        setShowDraftDetailModal(false);
        setIsStoryStreaming(true);
        setStoryStreamingText('');

        try {
            // 1. Prepare Request to avoid URL length limits
            const prepareRes = await fetch('http://localhost:3501/api/workflow/story/prepare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    draftId: editingDraft.id,
                    draftTitle: editingDraft.title,
                    draftSummary: editingDraft.summary,
                    mode: state.mode
                })
            });

            if (!prepareRes.ok) {
                throw new Error('Failed to prepare story generation');
            }

            const { requestId } = await prepareRes.json();

            // 2. Start Streaming with Request ID
            const eventSource = new EventSource(
                `http://localhost:3501/api/workflow/story/stream?requestId=${requestId}`
            );
            eventSourceStreamRef.current = eventSource;

            eventSource.addEventListener('delta', ((event: any) => {
                const data = JSON.parse(event.data);
                setStoryStreamingText(prev => prev + data.text);
            }) as EventListener);

            eventSource.addEventListener('complete', ((event: any) => {
                eventSource.close();
                const data = JSON.parse(event.data);

                setIsStoryStreaming(false);
                eventSourceStreamRef.current = null;

                setState(s => ({
                    ...s,
                    selectedDraft: editingDraft,
                    cuts: data.cuts,
                    characterPrompt: data.characterPrompt,
                    editedStory: data.fullText || '', // Use streaming result
                    step: 2
                }));
            }) as EventListener);

            eventSource.addEventListener('error', ((event: any) => {
                console.error('Story Streaming Error:', event);
                setIsStoryStreaming(false);
                eventSourceStreamRef.current = null;

                // Check if it's a specific error from backend
                try {
                    const data = JSON.parse(event.data);
                    if (data.error) {
                        alert(`오류 발생: ${data.error}`);
                    } else {
                        alert('스토리 생성 스트리밍 중 오류가 발생했습니다.');
                    }
                } catch (e) {
                    alert('연결 오류 또는 타임아웃이 발생했습니다. (백엔드 로그 확인)');
                }
                eventSource.close();
            }) as EventListener);

            eventSource.onerror = () => {
                console.error('SSE onerror');
                if (eventSource.readyState === 2) {
                    eventSource.close();
                    setIsStoryStreaming(false);
                    eventSourceStreamRef.current = null;
                    alert('스트리밍 연결이 끊어졌습니다.');
                }
            };
        } catch (e) {
            console.error(e);
            setIsStoryStreaming(false);
            alert('스토리 생성 요청 실패: URL 길이 제한 문제 해결 시도 중 오류.');
        }
    };




    // Animation: Parse Script
    const parseScript = async () => {
        if (!state.editedStory.trim()) {
            alert("스크립트를 입력해주세요.");
            return;
        }

        setState(s => ({ ...s, isProcessing: true, loadingMessage: '대본 분석 및 컷 나눈 중...', loadingDetail: 'AI가 대본을 분석하여 컷 리스트를 생성합니다.' }));
        try {
            const res = await fetch('http://localhost:3501/api/workflow/story/parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script: state.editedStory, mode: state.mode })
            });
            const data = await res.json();
            if (data.success) {
                // Determine cut instruction based on result
                setState(s => ({
                    ...s,
                    cuts: data.cuts,
                    characterPrompt: data.characterPrompt,
                    isProcessing: false,
                }));
                alert(`분석 완료: 총 ${data.totalCuts}컷이 생성되었습니다.`);
            } else {
                alert('파싱 실패: ' + (data.error || '알 수 없는 오류'));
                setState(s => ({ ...s, isProcessing: false }));
            }
        } catch (e) {
            console.error(e);
            alert('통신 오류가 발생했습니다.');
            setState(s => ({ ...s, isProcessing: false }));
        }
    };

    // [CONTROL] Stop or Finish Early
    const controlGeneration = async (action: 'stop' | 'finish_early') => {
        try {
            const response = await fetch('http://localhost:3501/api/workflow/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action })
            });
            const data = await response.json();
            console.log("Control response:", data);
        } catch (e) {
            console.error("Control failed:", e);
        }
    };

    // Step 2 -> Step 3: Generate first reference image (or skip if disabled)
    const startGeneration = async () => {
        if (state.cuts.length === 0) {
            alert(state.style === 'animation'
                ? "이미지를 생성하기 전에 먼저 'AI 컷 나누기' 버튼을 눌러 스토리를 컷별로 나누어야 합니다."
                : "생성할 스토리 정보가 없습니다. 이전 단계로 돌아가 스토리를 생성해 주세요."
            );
            return;
        }

        // 1. Ensure we have the latest settings
        let currentUseRef = useReferenceImage;
        try {
            const setRes = await fetch('http://localhost:3501/api/settings');
            const setData = await setRes.json();
            currentUseRef = setData.use_reference_image !== false;
            setUseReferenceImage(currentUseRef);
        } catch (e) {
            console.error("Settings sync failed", e);
        }

        // Helper: Setup SSE for generation stream
        const setupEventSource = (eventSource: EventSource) => {
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'log') {
                    setState(s => ({ ...s, logs: [...s.logs, data.message], currentCutIndex: data.cutIndex || s.currentCutIndex }));
                } else if (data.type === 'preview') {
                    setState(s => ({ ...s, currentImage: data.image, currentCutIndex: data.cutIndex || s.currentCutIndex }));
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

        // 2. Direct Generation (If Reference Mode is OFF)
        if (!currentUseRef) {
            setState(s => ({
                ...s,
                step: 3,
                logs: ['🎬 이미지 생성 시작 (참조 기능 비활성화)...'],
                isProcessing: true,
                referenceImage: null,
                referenceConfirmed: true, // Auto-confirm
                currentCutIndex: 1
            }));

            const cuts = state.mode === 'long' ? 100 : 20;
            const modeStr = state.mode === 'long' ? 'Long Form (16:9)' : 'Short Form (9:16)';

            // Queue Generation first to pass full story data
            fetch('http://localhost:3501/api/queue-generation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: modeStr,
                    style: state.style,
                    topic: state.selectedDraft?.title || 'Story',
                    cuts: state.cuts, // Pass full cuts data
                    concept: "기본 (Default)",
                    title: state.selectedTitle || state.selectedDraft?.title || '',
                    characterPrompt: state.characterPrompt
                })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.jobId) {
                        const eventSource = new EventSource(
                            `http://localhost:3501/api/stream?jobId=${data.jobId}`
                        );
                        setupEventSource(eventSource);
                    } else {
                        setState(s => ({ ...s, logs: [...s.logs, '❌ 작업 큐 실패'], isProcessing: false }));
                    }
                })
                .catch(e => {
                    setState(s => ({ ...s, logs: [...s.logs, `❌ 큐 요청 오류: ${String(e)}`], isProcessing: false }));
                });
            return;
        }

        // 3. User Uploaded Reference Logic (If already uploaded)
        if (state.referenceImage) {
            setState(s => ({
                ...s,
                step: 3,
                logs: ['🖼️ 사용자 업로드 이미지 사용...'],
                isProcessing: false,
                referenceConfirmed: false, // User must confirm
                currentCutIndex: 1
            }));
            return;
        }

        // 4. Generate Reference Image (First Cut Only)
        setState(s => ({
            ...s,
            step: 3,
            logs: ['🎬 첫 번째 이미지 생성 시작...'],
            isProcessing: true,
            referenceImage: null,
            referenceConfirmed: false,
            currentCutIndex: 1
        }));

        try {
            // Generate only the first image for confirmation
            const res = await fetch('http://localhost:3501/api/workflow/generate-reference', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: state.mode,
                    style: state.style,
                    cut: state.cuts[0],
                    characterPrompt: state.characterPrompt
                })
            });
            const data = await res.json();

            if (data.success && data.imageUrl) {
                setState(s => ({
                    ...s,
                    referenceImage: data.imageUrl,
                    logs: [...s.logs, '✅ 첫 번째 이미지 생성 완료! 확인해주세요.'],
                    isProcessing: false
                }));
            } else {
                // Error case: Stop and show error
                setState(s => ({
                    ...s,
                    logs: [...s.logs, `❌ 오류: ${data.error || '이미지 생성 실패'}`],
                    isProcessing: false
                }));
            }
        } catch (e) {
            // Network/Server Error: Stop and show error
            setState(s => ({
                ...s,
                logs: [...s.logs, `❌ 서버 연결 오류: ${String(e)}`],
                isProcessing: false
            }));
        }
    };

    // Regenerate reference image
    const regenerateReferenceImage = () => {
        setState(s => ({ ...s, referenceImage: null, isProcessing: true, logs: [...s.logs, '🔄 이미지 재생성 중...'] }));
        startGeneration();

    };

    // Confirm reference and continue with remaining images
    const confirmReferenceAndContinue = () => {
        setState(s => ({
            ...s,
            referenceConfirmed: true,
            isProcessing: true,
            logs: [...s.logs, '✅ 참조 이미지 확정! 나머지 이미지 생성 시작...']
        }));

        const cuts = state.mode === 'long' ? 100 : 20;
        const modeStr = state.mode === 'long' ? 'Long Form (16:9)' : 'Short Form (9:16)';

        // Start generating remaining images with reference
        const eventSource = new EventSource(
            `http://localhost:3501/api/stream?mode=${encodeURIComponent(modeStr)}&topic=${encodeURIComponent(state.selectedDraft?.title || 'Story')}&cuts=${cuts}&concept=기본 (Default)&title=${encodeURIComponent(state.selectedTitle || state.selectedDraft?.title || '')}&referenceImage=${encodeURIComponent(state.referenceImage || '')}`
        );

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'log') {
                setState(s => ({ ...s, logs: [...s.logs, data.message], currentCutIndex: data.cutIndex || s.currentCutIndex }));
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
            step: 0, mode: 'long', style: 'photoreal', inputMode: 'category', category: '', customInput: '',
            drafts: [], selectedDraft: null, cuts: [], characterPrompt: '', editedStory: '',
            titles: [], selectedTitle: '', logs: [], isProcessing: false, loadingMessage: '', loadingDetail: '', streamingText: '',
            referenceImage: null, referenceConfirmed: false, currentCutIndex: 0, result: null, currentImage: null
        });
    };

    return (
        <div className="space-y-6 relative">
            {/* Stepper */}

            <div className="flex items-center justify-between bg-slate-900/50 p-4 rounded-2xl border border-slate-800">
                <div className="flex items-center gap-4">
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

                {/* Backend Status Indicator */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800/50 border border-slate-700">
                    <div className={`w-2 h-2 rounded-full ${backendStatus === 'connected' ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' :
                        backendStatus === 'checking' ? 'bg-amber-500 animate-pulse' : 'bg-red-500 animate-pulse shadow-[0_0_8px_#ef4444]'
                        }`} />
                    <span className="text-[10px] font-bold text-slate-400">
                        {backendStatus === 'connected' ? 'BACKEND ONLINE' :
                            backendStatus === 'checking' ? 'SYNCING...' : 'BACKEND OFFLINE'}
                    </span>
                </div>
            </div>

            {backendStatus === 'error' && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-4 flex items-center gap-4 animate-in fade-in slide-in-from-top-2">
                    <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center text-red-500">
                        <Icon icon="solar:danger-bold" className="text-2xl" />
                    </div>
                    <div className="flex-1">
                        <h4 className="text-red-400 font-bold">백엔드 서버 연결 실패</h4>
                        <p className="text-red-400/70 text-sm">Port 3501 서버가 실행 중인지 확인하거나, 방화벽 설정을 검토하세요.</p>
                    </div>
                    <button
                        onClick={() => window.location.reload()}
                        className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-bold rounded-lg transition-all"
                    >
                        재시도
                    </button>
                </div>
            )}

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

                        <div className="text-center mb-4 pt-8 border-t border-slate-800">
                            <h2 className="text-2xl font-black text-white mb-2">스타일 선택</h2>
                            <p className="text-slate-400">영상의 톤앤매너를 선택하세요.</p>
                        </div>
                        <div className="grid grid-cols-2 gap-6 max-w-3xl mx-auto">
                            <button
                                onClick={() => setState(s => ({ ...s, style: 'photoreal' }))}
                                className={`p-6 rounded-3xl border-2 transition-all ${state.style === 'photoreal'
                                    ? 'border-emerald-500 bg-emerald-600/10 shadow-[0_0_30px_rgba(16,185,129,0.3)]'
                                    : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                                    }`}
                            >
                                <Icon icon="solar:camera-minimalistic-bold-duotone" className="text-4xl text-emerald-400 mb-3 mx-auto" />
                                <h3 className="text-lg font-black text-white mb-1">📸 실사 (Real)</h3>
                                <p className="text-slate-400 text-xs">AI 자동 스토리 생성 & 실사 렌더링</p>
                            </button>
                            <button
                                onClick={() => setState(s => ({ ...s, style: 'animation' }))}
                                className={`p-6 rounded-3xl border-2 transition-all ${state.style === 'animation'
                                    ? 'border-pink-500 bg-pink-600/10 shadow-[0_0_30px_rgba(236,72,153,0.3)]'
                                    : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                                    }`}
                            >
                                <Icon icon="solar:palette-bold-duotone" className="text-4xl text-pink-400 mb-3 mx-auto" />
                                <h3 className="text-lg font-black text-white mb-1">🎨 애니메이션 (Man-hwa)</h3>
                                <p className="text-slate-400 text-xs">직접 스토리 입력 & 전래동화풍 렌더링</p>
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

                        <div className="flex justify-center gap-3 pt-4">
                            {state.drafts.length === 0 && (
                                <button
                                    onClick={() => openDraftsModal('load', 'draft')}
                                    className="px-6 py-4 bg-amber-600/20 hover:bg-amber-600 text-amber-400 hover:text-white font-bold rounded-2xl transition-all flex items-center gap-2 border border-amber-600/50"
                                >
                                    <Icon icon="solar:folder-open-bold" className="text-xl" />
                                    불러오기
                                </button>
                            )}
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

                        {/* Inline Streaming Text Display - Only for Draft Generation */}
                        {state.isProcessing && state.loadingDetail === 'GET /api/workflow/drafts/parallel' && (
                            <motion.div
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="mt-6 bg-slate-900/80 border border-slate-700 rounded-2xl p-6 max-w-4xl mx-auto"
                            >
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
                                        <Icon icon="solar:cpu-bolt-bold" className="text-xl text-white" />
                                    </div>
                                    <div>
                                        <h4 className="text-white font-bold">병렬 스트리밍</h4>
                                        <div className="flex items-center gap-2 text-xs text-slate-500">
                                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                                            <span>10개 초안 동시 생성 중...</span>
                                        </div>
                                    </div>
                                    <div className="ml-auto text-sm font-bold text-blue-400">
                                        {state.drafts.length}/10 완료
                                    </div>
                                </div>

                                {/* 2 columns x 5 rows Grid with Streaming Text */}
                                <div className="grid grid-cols-2 gap-3">
                                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((id) => {
                                        const draft = state.drafts.find(d => d.id === id);
                                        const streamText = streamingTexts[id] || '';
                                        return (
                                            <div
                                                key={id}
                                                className={`p-3 rounded-xl border transition-all ${draft
                                                    ? 'bg-green-500/10 border-green-500/50'
                                                    : streamText
                                                        ? 'bg-blue-500/10 border-blue-500/50'
                                                        : 'bg-slate-800/50 border-slate-700'
                                                    }`}
                                            >
                                                <div className="flex justify-between items-start mb-1">
                                                    <span className={`text-xs font-bold ${draft ? 'text-green-400' : 'text-slate-500'}`}>#{id}</span>
                                                    {draft && <Icon icon="solar:check-circle-bold" className="text-green-500" />}
                                                </div>
                                                <p className="text-xs text-slate-400 line-clamp-3 font-mono">
                                                    {draft ? draft.title : streamText || '대기 중...'}
                                                </p>
                                            </div>
                                        );
                                    })}
                                </div>
                            </motion.div>
                        )}

                        {/* General Loading Overlay (for Story Generation, etc) */}
                        {state.isProcessing && state.loadingDetail !== 'GET /api/workflow/drafts/parallel' && (
                            <div className="mt-8 flex flex-col items-center justify-center p-8 bg-slate-900/50 rounded-2xl border border-slate-700/50 backdrop-blur-sm">
                                <div className="relative mb-4">
                                    <div className="w-16 h-16 border-4 border-blue-600/30 border-t-blue-500 rounded-full animate-spin" />
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <Icon icon="solar:magic-stick-3-bold" className="text-blue-500 text-2xl animate-pulse" />
                                    </div>
                                </div>
                                <h3 className="text-xl font-bold text-white mb-2 animate-pulse">{state.loadingMessage || '처리 중...'}</h3>
                                <p className="text-slate-400 text-sm font-mono">{state.loadingDetail}</p>
                            </div>
                        )}


                        {/* Drafts Grid */}
                        {
                            state.drafts.length > 0 && (
                                <>
                                    {/* Save/Load Buttons */}
                                    <div className="flex justify-center gap-3 mt-6">
                                        <button
                                            onClick={() => openDraftsModal('save', 'draft')}
                                            className="px-6 py-3 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-400 hover:text-white font-bold rounded-xl transition-all flex items-center gap-2 border border-emerald-600/50"
                                        >
                                            <Icon icon="solar:diskette-bold" className="text-lg" />
                                            저장
                                        </button>
                                        <button
                                            onClick={() => openDraftsModal('load', 'draft')}
                                            className="px-6 py-3 bg-amber-600/20 hover:bg-amber-600 text-amber-400 hover:text-white font-bold rounded-xl transition-all flex items-center gap-2 border border-amber-600/50"
                                        >
                                            <Icon icon="solar:folder-open-bold" className="text-lg" />
                                            불러오기
                                        </button>
                                        <button
                                            onClick={() => openDraftsModal('delete', 'draft')}
                                            className="px-6 py-3 bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white font-bold rounded-xl transition-all flex items-center gap-2 border border-red-600/50"
                                        >
                                            <Icon icon="solar:trash-bin-trash-bold" className="text-lg" />
                                            삭제
                                        </button>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 mt-4">

                                        {state.drafts.map((draft) => (
                                            <motion.div
                                                key={draft.id}
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className={`bg-slate-900/70 border rounded-2xl p-5 hover:border-blue-500/50 transition-all group cursor-pointer relative overflow-hidden ${draft.theme === 'error' ? 'border-red-500/50' : 'border-slate-700'
                                                    }`}
                                                onClick={() => { if (draft.theme !== 'error') selectDraft(draft); }}
                                            >
                                                <div className="flex items-start justify-between mb-2">
                                                    <h4 className="font-bold text-white group-hover:text-blue-400 transition-colors">{draft.title}</h4>
                                                    <span className={`text-[10px] px-2 py-0.5 rounded uppercase ${draft.theme === 'error' ? 'bg-red-500/20 text-red-400' : 'bg-slate-800 text-slate-400'
                                                        }`}>{draft.theme}</span>
                                                </div>
                                                <p className="text-slate-400 text-sm leading-relaxed line-clamp-4">{draft.summary}</p>

                                                {draft.theme === 'error' ? (
                                                    <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center pointer-events-auto" onClick={(e) => e.stopPropagation()}>
                                                        <button
                                                            onClick={() => regenerateDraft(draft.id)}
                                                            className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl flex items-center gap-2 shadow-lg hover:scale-105 transition-all"
                                                        >
                                                            <Icon icon="solar:restart-bold" /> 다시 시도
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); selectDraft(draft); }}
                                                        className="mt-3 w-full py-2 bg-blue-600/20 text-blue-400 rounded-xl text-xs font-bold hover:bg-blue-600 hover:text-white transition-all"
                                                    >
                                                        이 초안 선택 →
                                                    </button>
                                                )}
                                            </motion.div>

                                        ))}
                                    </div>
                                </>
                            )
                        }

                        <div className="flex justify-start pt-4">
                            <button onClick={prevStep} className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl">
                                ← 이전
                            </button>
                        </div>
                    </motion.div >
                )}

                {/* ===== STEP 2: Story Confirmation ===== */}
                {
                    state.step === 2 && (
                        <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">

                            <div className="flex items-center justify-between">
                                <div>
                                    <h2 className="text-2xl font-black text-white mb-1">
                                        {state.style === 'animation' ? '대본(스크립트) 입력' : '스토리 확정'}
                                    </h2>
                                    <p className="text-slate-400 text-sm">
                                        {state.style === 'animation'
                                            ? '영상으로 제작할 대본을 입력하세요. (번호를 붙이면 컷 분리가 정확해집니다)'
                                            : `생성된 ${state.mode === 'long' ? 100 : 20}컷 스토리를 검토하고 수정하세요.`}
                                    </p>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => openDraftsModal('load', 'story')}
                                        className="px-4 py-2 bg-amber-600/20 hover:bg-amber-600 text-amber-400 hover:text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 border border-amber-600/50"
                                    >
                                        <Icon icon="solar:folder-open-bold" /> 불러오기
                                    </button>
                                    <button
                                        onClick={() => openDraftsModal('save', 'story')}
                                        className="px-4 py-2 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-400 hover:text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 border border-emerald-600/50"
                                    >
                                        <Icon icon="solar:diskette-bold" /> 저장
                                    </button>
                                    <div className="bg-slate-800 px-4 py-2 rounded-xl border border-slate-700 flex items-center">
                                        <span className="text-xs text-slate-400 mr-2">선택 초안: </span>
                                        <span className="text-white font-bold">{state.selectedDraft?.title}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-6">
                                <div className="col-span-2 bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden relative">
                                    <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                                        <span className="text-xs font-bold text-slate-400 uppercase">📝 상세 스토리 ({state.mode === 'long' ? 100 : 20}컷)</span>
                                        <span className="text-[10px] text-slate-500">{state.editedStory.length} 자</span>
                                    </div>
                                    <textarea
                                        value={state.editedStory}
                                        onChange={(e) => setState(s => ({ ...s, editedStory: e.target.value }))}
                                        placeholder={state.style === 'animation' ? "1. 숲속을 걸어가는 주인공...\n2. 갑자기 나타난 사슴..." : ""}
                                        className="w-full h-[400px] bg-transparent p-4 text-slate-300 text-sm leading-relaxed focus:outline-none resize-none custom-scrollbar"
                                    />
                                    {state.style === 'animation' && (
                                        <div className="absolute bottom-4 right-4">
                                            <button
                                                onClick={parseScript}
                                                disabled={state.isProcessing}
                                                className={`px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg flex items-center gap-2 transition-all ${state.isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
                                            >
                                                {state.isProcessing ? (
                                                    <>
                                                        <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                        분석 중...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Icon icon="solar:magic-stick-3-bold-duotone" />
                                                        AI 컷 나누기
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    )}
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
                                <div className="flex flex-col items-end gap-2">
                                    <button
                                        onClick={startGeneration}
                                        disabled={state.cuts.length === 0}
                                        className={`px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-black rounded-2xl transition-all shadow-lg flex items-center gap-3 ${state.cuts.length === 0 ? 'opacity-50 grayscale cursor-not-allowed' : ''}`}
                                    >
                                        <Icon icon="solar:play-bold" className="text-xl" /> 이미지 생성 시작
                                    </button>
                                    {state.cuts.length === 0 && (
                                        <span className="text-[10px] text-amber-500 font-bold animate-pulse">
                                            {state.style === 'animation' ? '⚠️ "AI 컷 나누기"를 먼저 눌러주세요' : '⚠️ 스토리 데이터가 없습니다'}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </motion.div >
                    )
                }

                {/* ===== STEP 3: Generation ===== */}
                {
                    state.step === 3 && (
                        <motion.div key="step3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-6">

                            {/* Reference Image Confirmation */}
                            {state.referenceImage && !state.referenceConfirmed && (
                                <div className="bg-gradient-to-br from-purple-900/30 to-indigo-900/30 border border-purple-500/30 rounded-2xl p-6">
                                    <div className="text-center mb-4">
                                        <h2 className="text-2xl font-black text-white mb-2">🎭 주인공 이미지 확인</h2>
                                        <p className="text-slate-400">첫 번째 이미지가 생성되었습니다. 이 이미지를 참조하여 나머지 씬을 생성합니다.</p>
                                    </div>

                                    <div className="flex gap-6 items-start">
                                        {/* Reference Image Preview */}
                                        <div className="flex-shrink-0">
                                            <div className="w-64 h-64 bg-slate-800 rounded-xl overflow-hidden border-4 border-purple-500/50">
                                                <img
                                                    src={state.referenceImage}
                                                    alt="Reference"
                                                    className="w-full h-full object-cover"
                                                />
                                            </div>
                                            <p className="text-center text-xs text-purple-400 mt-2">컷 #1 - 주인공 참조 이미지</p>
                                        </div>

                                        {/* Controls */}
                                        <div className="flex-1 space-y-4">
                                            <div className="bg-slate-900/50 rounded-xl p-4">
                                                <h3 className="text-white font-bold mb-2">📌 이 이미지가 참조로 사용됩니다</h3>
                                                <ul className="text-sm text-slate-400 space-y-1">
                                                    <li>• 모든 씬에서 주인공의 얼굴/외형 일관성 유지</li>
                                                    <li>• IP-Adapter 기술로 동일 인물 재현</li>
                                                    <li>• 마음에 들지 않으면 재생성 가능</li>
                                                </ul>
                                            </div>

                                            <div className="flex gap-3">
                                                <button
                                                    onClick={regenerateReferenceImage}
                                                    disabled={state.isProcessing}
                                                    className="flex-1 px-6 py-4 bg-amber-600/20 hover:bg-amber-600 text-amber-400 hover:text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2 border border-amber-600/50 disabled:opacity-50"
                                                >
                                                    <Icon icon="solar:refresh-bold" className="text-xl" />
                                                    재생성
                                                </button>
                                                <button
                                                    onClick={confirmReferenceAndContinue}
                                                    disabled={state.isProcessing}
                                                    className="flex-1 px-6 py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                                                >
                                                    <Icon icon="solar:check-circle-bold" className="text-xl" />
                                                    이대로 진행
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Generating remaining images */}
                            {(state.referenceConfirmed || !state.referenceImage) && (
                                <>
                                    <div className="text-center mb-4">
                                        <h2 className="text-2xl font-black text-white mb-2">
                                            {state.referenceConfirmed ? '🎬 나머지 이미지 생성 중...' : '🎬 첫 번째 이미지 생성 중...'}
                                        </h2>
                                        <p className="text-slate-400">
                                            {state.referenceConfirmed
                                                ? `참조 이미지 기반으로 ${state.mode === 'long' ? 100 : 20}컷을 생성합니다.`
                                                : '주인공 참조 이미지를 생성하고 있습니다...'
                                            }
                                        </p>
                                    </div>

                                    {/* Progress Bar */}
                                    {state.referenceConfirmed && (
                                        <div className="bg-slate-900/50 rounded-xl p-4">
                                            <div className="flex justify-between text-xs text-slate-400 mb-2">
                                                <span>진행률</span>
                                                <span>{state.currentCutIndex} / {state.mode === 'long' ? 100 : 20} 컷</span>
                                            </div>
                                            <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
                                                <motion.div
                                                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${(state.currentCutIndex / (state.mode === 'long' ? 100 : 20)) * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}

                            {/* [CONTROL] Buttons: Only show during Image Generation (Step 3+) and Processing */}
                            {state.step >= 3 && state.isProcessing && (
                                <div className="flex justify-end gap-2 my-4">
                                    <button
                                        onClick={() => controlGeneration('stop')}
                                        className="btn btn-error btn-sm text-white shadow-lg shadow-red-500/20"
                                    >
                                        🛑 중단 (Stop)
                                    </button>
                                    <button
                                        onClick={() => controlGeneration('finish_early')}
                                        className="btn btn-warning btn-sm text-white shadow-lg shadow-orange-500/20"
                                    >
                                        🏁 이까지만 생성 (Finish Here)
                                    </button>
                                </div>
                            )}


                            {/* Logs */}
                            {/* Logs & Live Preview */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Logs */}
                                <div className="bg-slate-900 rounded-xl p-4 h-64 overflow-y-auto font-mono text-xs border border-slate-800 space-y-1">
                                    {state.logs.length === 0 ? (
                                        <div className="h-full flex items-center justify-center text-slate-600">
                                            <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                                        </div>
                                    ) : (
                                        <>
                                            {state.logs.map((log, i) => (
                                                <div key={i} className="text-slate-400">{log}</div>
                                            ))}
                                            <div ref={logEndRef} />
                                        </>
                                    )}
                                </div>

                                {/* Live Image Preview */}
                                {state.currentImage && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="space-y-2"
                                    >
                                        <h3 className="text-white font-bold flex items-center gap-2">
                                            <Icon icon="solar:camera-bold" className="text-blue-500" />
                                            실시간 미리보기 (Cut {state.currentCutIndex})
                                        </h3>
                                        <div className="rounded-xl overflow-hidden border border-slate-700 aspect-video bg-black relative">
                                            <img
                                                src={state.currentImage}
                                                alt="Live Preview"
                                                className="w-full h-full object-contain"
                                            />
                                        </div>
                                    </motion.div>
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

            {/* Save/Load/Delete Modal */}
            <AnimatePresence>
                {
                    showDraftsModal && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
                            onClick={() => setShowDraftsModal(false)}
                        >
                            <motion.div
                                initial={{ scale: 0.9, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                exit={{ scale: 0.9, opacity: 0 }}
                                className="bg-slate-900/95 border border-slate-700 rounded-3xl p-6 w-full max-w-lg mx-4 shadow-2xl"
                                onClick={(e) => e.stopPropagation()}
                            >
                                {/* Modal Header */}
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-xl font-black text-white flex items-center gap-3">
                                        {modalMode === 'save' && <><Icon icon="solar:diskette-bold" className="text-emerald-400" /> {saveType === 'draft' ? '초안' : '스토리'} 저장</>}
                                        {modalMode === 'load' && <><Icon icon="solar:folder-open-bold" className="text-amber-400" /> {saveType === 'draft' ? '초안' : '스토리'} 불러오기</>}
                                        {modalMode === 'delete' && <><Icon icon="solar:trash-bin-trash-bold" className="text-red-400" /> {saveType === 'draft' ? '초안' : '스토리'} 삭제</>}
                                    </h3>
                                    <button
                                        onClick={() => setShowDraftsModal(false)}
                                        className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all"
                                    >
                                        <Icon icon="solar:close-circle-bold" />
                                    </button>
                                </div>

                                {/* Save Mode */}
                                {modalMode === 'save' && (
                                    <div className="space-y-4">
                                        <input
                                            type="text"
                                            value={saveTitle}
                                            onChange={(e) => setSaveTitle(e.target.value)}
                                            placeholder="저장할 이름을 입력하세요"
                                            className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500"
                                        />
                                        <p className="text-xs text-slate-500">
                                            {saveType === 'draft'
                                                ? `현재 ${state.drafts.length}개의 초안이 저장됩니다.`
                                                : `현재 편집 중인 스토리와 캐릭터 설정이 저장됩니다.`}
                                        </p>
                                        <button
                                            onClick={saveItem}
                                            disabled={!saveTitle.trim() || (saveType === 'draft' && state.drafts.length === 0)}
                                            className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                        >
                                            <Icon icon="solar:diskette-bold" /> 저장하기
                                        </button>
                                    </div>
                                )}

                                {/* Load/Delete Mode */}
                                {(modalMode === 'load' || modalMode === 'delete') && (
                                    <div className="space-y-3">
                                        {modalMode === 'load' ? (
                                            /* Split View for Load */
                                            <div className="grid grid-cols-2 gap-4 h-96">
                                                {/* Left Column: Drafts */}
                                                <div className="flex flex-col bg-slate-950/50 rounded-2xl p-4 border border-slate-800">
                                                    <h4 className="text-amber-400 font-bold mb-3 flex items-center gap-2">
                                                        <Icon icon="solar:document-text-bold" /> 초안 목록 ({savedDrafts.length})
                                                    </h4>
                                                    <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                                        {savedDrafts.length === 0 ? (
                                                            <div className="text-slate-500 text-xs text-center py-10">저장된 초안이 없습니다.</div>
                                                        ) : (
                                                            savedDrafts.map((item, i) => (
                                                                <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-xl p-3 hover:border-slate-500 transition-all group">
                                                                    <div className="mb-2">
                                                                        <h5 className="text-white font-bold text-sm truncate">{item.title}</h5>
                                                                        <p className="text-xs text-slate-500">{new Date(item.savedAt).toLocaleDateString()} · {item.drafts?.length || 0}개</p>
                                                                    </div>
                                                                    <div className="flex gap-2">
                                                                        <button
                                                                            onClick={() => loadItem(item, 'draft')}
                                                                            className="flex-1 py-2 bg-amber-600/20 hover:bg-amber-600 text-amber-400 hover:text-white text-xs font-bold rounded-lg transition-all"
                                                                        >
                                                                            불러오기
                                                                        </button>
                                                                        <button
                                                                            onClick={(e) => { e.stopPropagation(); if (confirm('정말 삭제하시겠습니까?')) deleteItem(i, 'draft'); }}
                                                                            className="px-3 py-2 bg-slate-700 hover:bg-red-600 text-slate-400 hover:text-white rounded-lg transition-all"
                                                                        >
                                                                            <Icon icon="solar:trash-bin-trash-bold" />
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            ))
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Right Column: Stories */}
                                                <div className="flex flex-col bg-slate-950/50 rounded-2xl p-4 border border-slate-800">
                                                    <h4 className="text-emerald-400 font-bold mb-3 flex items-center gap-2">
                                                        <Icon icon="solar:clapperboard-play-bold" /> 스토리 목록 ({savedStories.length})
                                                    </h4>
                                                    <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                                        {savedStories.length === 0 ? (
                                                            <div className="text-slate-500 text-xs text-center py-10">저장된 스토리가 없습니다.</div>
                                                        ) : (
                                                            savedStories.map((item, i) => (
                                                                <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-xl p-3 hover:border-slate-500 transition-all group">
                                                                    <div className="mb-2">
                                                                        <h5 className="text-white font-bold text-sm truncate">{item.title}</h5>
                                                                        <p className="text-xs text-slate-500">
                                                                            {new Date(item.savedAt).toLocaleDateString()} · {item.mode === 'long' ? 'Long' : 'Short'}
                                                                        </p>
                                                                    </div>
                                                                    <div className="flex gap-2">
                                                                        <button
                                                                            onClick={() => loadItem(item, 'story')}
                                                                            className="flex-1 py-2 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-400 hover:text-white text-xs font-bold rounded-lg transition-all"
                                                                        >
                                                                            불러오기
                                                                        </button>
                                                                        <button
                                                                            onClick={(e) => { e.stopPropagation(); if (confirm('정말 삭제하시겠습니까?')) deleteItem(i, 'story'); }}
                                                                            className="px-3 py-2 bg-slate-700 hover:bg-red-600 text-slate-400 hover:text-white rounded-lg transition-all"
                                                                        >
                                                                            <Icon icon="solar:trash-bin-trash-bold" />
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            ))
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            /* Single List View for Delete (based on saveType) */
                                            <div className="space-y-4">
                                                {/* Tab Switcher for Delete Mode */}
                                                <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800">
                                                    <button
                                                        onClick={() => setSaveType('draft')}
                                                        className={`flex-1 py-2 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${saveType === 'draft' ? 'bg-slate-700 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}
                                                    >
                                                        <Icon icon="solar:document-text-bold" /> 초안 ({savedDrafts.length})
                                                    </button>
                                                    <button
                                                        onClick={() => setSaveType('story')}
                                                        className={`flex-1 py-2 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${saveType === 'story' ? 'bg-slate-700 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}
                                                    >
                                                        <Icon icon="solar:clapperboard-play-bold" /> 스토리 ({savedStories.length})
                                                    </button>
                                                </div>

                                                <div className="max-h-80 overflow-y-auto space-y-2">
                                                    {(saveType === 'draft' ? savedDrafts : savedStories).length === 0 ? (
                                                        <div className="text-center py-8 text-slate-500">
                                                            <p>저장된 {saveType === 'draft' ? '초안이' : '스토리가'} 없습니다.</p>
                                                        </div>
                                                    ) : (
                                                        (saveType === 'draft' ? savedDrafts : savedStories).map((item, i) => (
                                                            <div key={i} className="flex items-center justify-between bg-slate-800/50 border border-slate-700 rounded-xl p-3 hover:border-slate-500 transition-all">
                                                                <div className="flex-1 min-w-0">
                                                                    <h4 className="text-white font-bold text-sm truncate">{item.title}</h4>
                                                                    <p className="text-xs text-slate-500">
                                                                        {new Date(item.savedAt).toLocaleString()}
                                                                    </p>
                                                                </div>
                                                                <button
                                                                    onClick={() => { if (confirm('정말 삭제하시겠습니까?')) deleteItem(i, saveType); }}
                                                                    className="ml-3 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-bold rounded-lg transition-all"
                                                                >
                                                                    삭제
                                                                </button>
                                                            </div>
                                                        ))
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {modalMode === 'delete' && (saveType === 'draft' ? savedDrafts : savedStories).length > 0 && (
                                            <button
                                                onClick={deleteAllItems}
                                                className="w-full py-2 bg-red-900/50 hover:bg-red-600 text-red-400 hover:text-white font-bold rounded-xl transition-all border border-red-600/50 text-sm"
                                            >
                                                🗑️ 전체 삭제
                                            </button>
                                        )}
                                    </div>
                                )}
                            </motion.div>
                        </motion.div>
                    )
                }


                {/* Draft Detail & Edit Modal */}
                {showDraftDetailModal && editingDraft && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4"
                        onClick={() => setShowDraftDetailModal(false)}
                    >
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
                            onClick={e => e.stopPropagation()}
                        >
                            <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-900 sticky top-0 z-10">
                                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                    <Icon icon="solar:pen-new-square-bold" className="text-blue-500" />
                                    초안 수정 및 확정
                                </h3>
                                <button onClick={() => setShowDraftDetailModal(false)} className="text-slate-500 hover:text-white transition-colors">
                                    <Icon icon="solar:close-circle-bold" className="text-2xl" />
                                </button>
                            </div>

                            <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-4">
                                <div>
                                    <label className="block text-sm font-bold text-slate-400 mb-1">제목</label>
                                    <input
                                        type="text"
                                        value={editingDraft.title}
                                        onChange={(e) => setEditingDraft({ ...editingDraft, title: e.target.value })}
                                        className="w-full bg-slate-800 border-slate-700 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all font-bold text-lg"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-bold text-slate-400 mb-1">줄거리 요약</label>
                                    <textarea
                                        value={editingDraft.summary}
                                        onChange={(e) => setEditingDraft({ ...editingDraft, summary: e.target.value })}
                                        className="w-full bg-slate-800 border-slate-700 rounded-lg px-4 py-3 text-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all h-64 resize-none leading-relaxed"
                                    />
                                </div>
                            </div>

                            <div className="p-4 bg-slate-900 border-t border-slate-800 flex justify-end gap-3">
                                <button
                                    onClick={() => setShowDraftDetailModal(false)}
                                    className="px-6 py-3 rounded-xl font-bold text-slate-400 hover:bg-slate-800 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={startStoryStream}
                                    className="px-8 py-3 rounded-xl font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-500/20 flex items-center gap-2 transition-all transform hover:scale-[1.02]"
                                >
                                    <Icon icon="solar:magic-stick-3-bold-duotone" className="text-xl" />
                                    이 내용으로 생성하기
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}

                {/* Story Generation Streaming Overlay */}
                {isStoryStreaming && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/90 backdrop-blur-sm p-4"
                    >
                        <div className="w-full max-w-4xl h-[80vh] bg-black border border-slate-800 rounded-2xl overflow-hidden flex flex-col shadow-2xl relative">
                            {/* Header */}
                            <div className="p-4 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="relative">
                                        <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                                        <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75" />
                                    </div>
                                    <span className="font-mono text-green-500 font-bold text-sm">LIVE STREAMING GENERATION</span>
                                </div>
                                <div className="flex items-center gap-4">
                                    <div className="font-mono text-slate-500 text-xs">gpt-5-mini-2025-08-07</div>
                                    <button
                                        onClick={stopStreaming}
                                        className="text-slate-400 hover:text-white transition-colors p-1"
                                        title="스트리밍 중지 및 닫기"
                                    >
                                        <Icon icon="solar:close-circle-bold" className="text-2xl" />
                                    </button>
                                </div>
                            </div>

                            {/* Terminal Output */}
                            <div
                                ref={setStoryStreamingLogRef}
                                className="flex-1 p-6 overflow-y-auto font-mono text-sm leading-relaxed custom-scrollbar bg-black"
                            >
                                <div className="text-slate-500 mb-4">
                                    Reading draft...<br />
                                    Initializing story engine...<br />
                                    Generating cuts...
                                </div>
                                <div className="whitespace-pre-wrap text-emerald-400">
                                    {storyStreamingText}
                                    <span className="inline-block w-2 h-4 bg-emerald-500 ml-1 animate-pulse" />
                                </div>
                            </div>

                            {/* Footer */}
                            <div className="p-4 border-t border-slate-800 bg-slate-900/30 text-center">
                                <p className="text-slate-500 text-xs animate-pulse">스토리를 작성하는 중입니다. 잠시만 기다려주세요...</p>
                            </div>
                        </div>
                    </motion.div>
                )}

            </AnimatePresence >
        </div >
    );
}


