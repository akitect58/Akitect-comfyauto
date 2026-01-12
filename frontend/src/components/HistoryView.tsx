'use client';

import React, { useState, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';

type HistoryItem = {
    id: string;
    title: string;
    mode: string;
    timestamp: string;
    thumbnails: string[];
    folder_name: string;
    image_count: number;
};

type ProjectDetail = {
    title: string;
    folder_name: string;
    assets: string[];
    metadata: {
        mode: string;
        cuts_data?: Array<{
            cutNumber: number;
            description: string;
            imagePrompt: string;
            sfxGuide?: string;
            videoPrompt?: string; // New field for Veo 3.1
            filename?: string;
            emotionLevel?: number;
            characterTag?: string;
            physicsDetail?: string;
        }>;
    };
};

export default function HistoryView() {
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [isDeleting, setIsDeleting] = useState<string | null>(null);

    const fetchHistory = async () => {
        setIsLoading(true);
        try {
            const res = await fetch('http://localhost:3501/api/history');
            const data = await res.json();
            setHistory(data);
        } catch (error) {
            console.error("Failed to fetch history:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchProjectDetails = async (folderName: string) => {
        try {
            const res = await fetch(`http://localhost:3501/api/history/${folderName}`);
            const data = await res.json();
            setSelectedProject(data);
        } catch (error) {
            console.error("Failed to fetch project details:", error);
        }
    };

    const deleteProject = async (e: React.MouseEvent, folderName: string) => {
        e.stopPropagation();
        if (!confirm('정말로 이 프로젝트를 폴더째로 삭제하시겠습니까? 관련 모든 이미지가 삭제됩니다.')) return;

        setIsDeleting(folderName);
        try {
            const res = await fetch(`http://localhost:3501/api/history/${folderName}`, {
                method: 'DELETE'
            });
            const data = await res.json();
            if (data.success) {
                setHistory(prev => prev.filter(item => item.folder_name !== folderName));
            } else {
                alert("삭제 실패: " + (data.error || "알 수 없는 오류"));
            }
        } catch (error) {
            console.error("Delete failed:", error);
            alert("서버 연결 오류로 삭제에 실패했습니다.");
        } finally {
            setIsDeleting(null);
        }
    };

    const regenerateVeoData = async () => {
        if (!selectedProject) return;

        setIsLoading(true);
        try {
            const res = await fetch(`http://localhost:3501/api/workflow/history/${selectedProject.folder_name}/generate_veo_prompts`, {
                method: 'POST'
            });
            const data = await res.json();

            if (data.success) {
                // Update local state by re-fetching project details or manually merging
                // Ideally re-fetch or merge. Let's merge for speed.
                setSelectedProject(prev => {
                    if (!prev) return null;
                    return {
                        ...prev,
                        metadata: {
                            ...prev.metadata,
                            cuts_data: data.updated_cuts
                        }
                    };
                });
                alert("VEO 3.1 프롬프트가 생성되었습니다. ('VEO 3.1 Prompt' 항목을 확인하세요)");
            } else {
                alert("생성 실패: " + data.error);
            }
        } catch (e) {
            console.error(e);
            alert("서버 통신 오류");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, []);

    const formatTimestamp = (ts: string) => {
        if (!ts) return "N/A";
        const year = ts.substring(0, 4);
        const month = ts.substring(4, 6);
        const day = ts.substring(6, 8);
        const hour = ts.substring(9, 11);
        const minute = ts.substring(11, 13);
        return `${year}-${month}-${day} ${hour}:${minute}`;
    };

    return (
        <div className="p-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white mb-1">작업 내역 (History)</h2>
                </div>
                <div className="flex items-center gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-700/50">
                    <button
                        onClick={() => setViewMode('grid')}
                        className={`p-2 rounded-md transition-all ${viewMode === 'grid' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                    >
                        <Icon icon="solar:widget-2-bold" />
                    </button>
                    <button
                        onClick={() => setViewMode('list')}
                        className={`p-2 rounded-md transition-all ${viewMode === 'list' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                    >
                        <Icon icon="solar:list-bold" />
                    </button>
                    <div className="w-px h-4 bg-slate-700 mx-1" />
                    <button
                        onClick={fetchHistory}
                        className="p-2 text-slate-400 hover:text-white transition-colors"
                    >
                        <Icon icon="solar:refresh-linear" />
                    </button>
                </div>
            </div>

            {isLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-12 py-8">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="bg-slate-800/50 rounded-2xl h-64 animate-pulse border border-slate-700/30" />
                    ))}
                </div>
            ) : history.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-32 text-slate-500 gap-4 border-2 border-dashed border-slate-700 rounded-2xl bg-slate-900/10">
                    <Icon icon="solar:folder-error-linear" className="text-6xl opacity-20" />
                    <p className="font-medium">저장된 내역이 없습니다. 첫 번째 프로젝트를 만들어보세요.</p>
                </div>
            ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-8 gap-y-12 pt-8 pb-16">
                    <AnimatePresence mode="popLayout">
                        {history.map((item) => (
                            <motion.div
                                key={item.id}
                                layout
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.8 }}
                                whileHover={{ y: -5 }}
                                onClick={() => fetchProjectDetails(item.folder_name)}
                                className="group relative cursor-pointer"
                            >
                                {/* THE STACK EFFECT */}
                                <div className="relative aspect-[4/3] w-full mb-4">
                                    <div className="absolute inset-0 bg-slate-800 rounded-2xl border border-white/5 shadow-2xl origin-bottom-right rotate-[6deg] scale-[0.98] -translate-x-2 -translate-y-2 group-hover:rotate-[8deg] transition-transform duration-500" />
                                    <div className="absolute inset-0 bg-slate-700 rounded-2xl border border-white/10 shadow-xl origin-bottom-right rotate-[3deg] scale-[0.99] -translate-x-1 -translate-y-1 group-hover:rotate-[4deg] transition-transform duration-500" />
                                    <div className="absolute inset-0 bg-black rounded-2xl border border-slate-600/50 shadow-2xl overflow-hidden z-10">
                                        {item.thumbnails && item.thumbnails.length > 0 ? (
                                            <img
                                                src={`http://localhost:3501${item.thumbnails[0]}`}
                                                alt={item.title}
                                                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-slate-700">
                                                <Icon icon="solar:folder-2-bold-duotone" className="text-6xl" />
                                            </div>
                                        )}
                                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

                                        {/* Action Overlay */}
                                        <div className="absolute top-3 right-3 z-30 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button
                                                onClick={(e) => deleteProject(e, item.folder_name)}
                                                disabled={isDeleting === item.folder_name}
                                                className="p-2 bg-red-600/90 hover:bg-red-500 text-white rounded-xl shadow-lg transition-all active:scale-90"
                                            >
                                                {isDeleting === item.folder_name ? (
                                                    <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                                ) : (
                                                    <Icon icon="solar:trash-bin-trash-bold" />
                                                )}
                                            </button>
                                        </div>

                                        <div className="absolute bottom-3 left-3 flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0 text-white z-20">
                                            <div className="bg-white/20 backdrop-blur-md px-2 py-1 rounded text-[10px] font-bold border border-white/10">
                                                {item.image_count} CUTS
                                            </div>
                                        </div>
                                    </div>
                                    <div className="absolute -top-3 left-6 w-16 h-8 bg-slate-700 rounded-t-xl -z-1 border-t border-x border-slate-600 scale-x-90" />
                                </div>
                                <div className="px-1">
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                        <h3 className="text-white font-bold group-hover:text-blue-400 transition-colors truncate text-sm">
                                            {item.title}
                                        </h3>
                                        <span className={`shrink-0 text-[8px] font-black px-1.5 py-0.5 rounded tracking-tighter ${item.mode === 'LONG_FORM' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20' : 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/20'}`}>
                                            {item.mode === 'LONG_FORM' ? '16:9' : '9:16'}
                                        </span>
                                    </div>
                                    <p className="text-slate-500 text-[10px] font-medium flex items-center gap-1">
                                        <Icon icon="solar:clock-circle-linear" className="text-xs" />
                                        {formatTimestamp(item.timestamp)}
                                    </p>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            ) : (
                <div className="bg-slate-900/50 rounded-2xl overflow-hidden border border-slate-800">
                    <table className="w-full text-left text-sm border-collapse">
                        <thead className="bg-slate-800/50 text-slate-400 font-bold text-xs uppercase tracking-wider border-b border-slate-800">
                            <tr>
                                <th className="px-6 py-4">프로젝트명</th>
                                <th className="px-6 py-4">모드</th>
                                <th className="px-6 py-4 text-center">에셋 수</th>
                                <th className="px-6 py-4">생성일</th>
                                <th className="px-6 py-4 text-right">관리</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            <AnimatePresence mode="popLayout">
                                {history.map((item) => (
                                    <motion.tr
                                        key={item.id}
                                        layout
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        exit={{ opacity: 0 }}
                                        onClick={() => fetchProjectDetails(item.folder_name)}
                                        className="hover:bg-slate-800/30 transition-colors group cursor-pointer"
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-4">
                                                <div className="w-12 h-10 rounded-lg bg-black overflow-hidden flex-shrink-0 border border-slate-700 shadow-lg relative">
                                                    <div className="absolute top-0 left-0 w-full h-full bg-slate-700 -z-1 rotate-3 scale-90 translate-x-1" />
                                                    <img src={`http://localhost:3501${item.thumbnails[0]}`} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
                                                </div>
                                                <div>
                                                    <span className="text-white font-bold group-hover:text-blue-400 transition-colors">{item.title}</span>
                                                    <p className="text-[10px] text-slate-500 font-mono">{item.folder_name}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="text-[10px] font-bold px-2 py-1 rounded bg-slate-800 text-slate-400 border border-slate-700 group-hover:text-white transition-colors">
                                                {item.mode}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <span className="text-white font-mono">{item.image_count}</span>
                                        </td>
                                        <td className="px-6 py-4 text-slate-400 font-mono text-xs">
                                            {formatTimestamp(item.timestamp)}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button
                                                onClick={(e) => deleteProject(e, item.folder_name)}
                                                disabled={isDeleting === item.folder_name}
                                                className="p-2 text-slate-600 hover:text-red-500 transition-colors active:scale-90"
                                            >
                                                {isDeleting === item.folder_name ? (
                                                    <div className="w-4 h-4 border-2 border-slate-600 border-t-white rounded-full animate-spin" />
                                                ) : (
                                                    <Icon icon="solar:trash-bin-trash-bold" className="text-xl" />
                                                )}
                                            </button>
                                        </td>
                                    </motion.tr>
                                ))}
                            </AnimatePresence>
                        </tbody>
                    </table>
                </div>
            )}

            {/* FOLDER EXPLORER MODAL */}
            <AnimatePresence>
                {selectedProject && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 md:p-12 overflow-hidden">
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-black/90 backdrop-blur-sm"
                            onClick={() => setSelectedProject(null)}
                        />

                        <motion.div
                            initial={{ scale: 0.95, y: 20, opacity: 0 }}
                            animate={{ scale: 1, y: 0, opacity: 1 }}
                            exit={{ scale: 0.95, y: 20, opacity: 0 }}
                            className="relative bg-slate-900 border border-slate-700 rounded-3xl shadow-3xl max-w-7xl w-full h-full overflow-hidden flex flex-col"
                        >
                            <div className="px-8 py-6 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-900/50 backdrop-blur-md sticky top-0 z-20">
                                <div className="flex items-center gap-4">
                                    <button
                                        onClick={() => setSelectedProject(null)}
                                        className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all"
                                    >
                                        <Icon icon="solar:alt-arrow-left-linear" className="text-2xl" />
                                    </button>
                                    <div>
                                        <h3 className="text-2xl font-black text-white">{selectedProject.title}</h3>
                                        <div className="flex items-center gap-3 mt-1">
                                            <span className="text-xs font-mono text-slate-500">
                                                {`/outputs/${selectedProject.metadata.mode}/...`}
                                            </span>
                                            <div className="w-1 h-1 rounded-full bg-slate-700" />
                                            <span className="text-xs font-bold text-blue-500 uppercase tracking-widest">{selectedProject.assets.length} ASSETS GENERATED</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-bold text-sm transition-all flex items-center gap-2 border border-slate-700">
                                        <Icon icon="solar:download-minimalistic-bold" />
                                        Bulk Download
                                    </button>

                                    {/* Veo Regen Button - Show if any cut is missing videoPrompt but has description */}
                                    {selectedProject.metadata.cuts_data?.some(c => !c.videoPrompt && c.description) && (
                                        <button
                                            onClick={regenerateVeoData}
                                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold text-sm transition-all flex items-center gap-2 shadow-lg shadow-indigo-500/20"
                                        >
                                            <Icon icon="solar:magic-stick-3-bold-duotone" />
                                            VEO 3.1 데이터 생성
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setSelectedProject(null)}
                                        className="p-2 text-slate-400 hover:text-white"
                                    >
                                        <Icon icon="solar:close-circle-linear" className="text-3xl" />
                                    </button>
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto w-full p-8 custom-scrollbar bg-slate-950/50">
                                <div className="space-y-12">
                                    {selectedProject.assets.map((asset, idx) => {
                                        // Find matching cut data
                                        // Asset path format: /outputs/EncodedFolder/001.png
                                        const filename = asset.split('/').pop();
                                        const cutData = selectedProject.metadata.cuts_data?.find(c => c.filename === filename || (c.cutNumber === idx + 1));

                                        return (
                                            <motion.div
                                                key={idx}
                                                initial={{ opacity: 0, y: 20 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="flex flex-col md:flex-row gap-6 bg-slate-900/50 p-6 rounded-3xl border border-slate-800"
                                            >
                                                {/* Image */}
                                                <div className="w-full md:w-1/3 max-w-sm shrink-0">
                                                    <div className="aspect-video bg-black rounded-2xl overflow-hidden shadow-lg border border-slate-700">
                                                        <img
                                                            src={`http://localhost:3501${asset}`}
                                                            alt={`Cut ${idx + 1}`}
                                                            className="w-full h-full object-contain"
                                                        />
                                                    </div>
                                                </div>

                                                {/* Prompts & Data */}
                                                <div className="flex-1 space-y-4">
                                                    <div className="flex items-center gap-3 mb-2">
                                                        <span className="text-xl font-black text-white">#{String(idx + 1).padStart(3, '0')}</span>
                                                        <span className="px-2 py-1 bg-slate-800 text-slate-300 text-xs rounded-lg border border-slate-700 font-bold">
                                                            {cutData?.emotionLevel ? `Emotion: ${cutData.emotionLevel}` : 'Scene'}
                                                        </span>
                                                    </div>

                                                    {/* Korean Description */}
                                                    <div>
                                                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">SCENE DESCRIPTION (KR)</h4>
                                                        <p className="text-white font-medium">{cutData?.description || "No description available"}</p>
                                                    </div>

                                                    {/* English Image Prompt */}
                                                    <div className="bg-black/30 p-4 rounded-xl border border-slate-800/50">
                                                        <h4 className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-2 flex items-center gap-2">
                                                            <Icon icon="solar:gallery-wide-bold" />
                                                            SDXL Image Prompt
                                                        </h4>
                                                        <p className="text-slate-400 text-xs font-mono leading-relaxed select-all">
                                                            {cutData?.imagePrompt || "No prompt data"}
                                                        </p>
                                                    </div>

                                                    {/* VEO 3.1 Prompt */}
                                                    <div className="bg-gradient-to-br from-indigo-900/20 to-purple-900/20 p-4 rounded-xl border border-indigo-500/20">
                                                        <div className="flex items-center justify-between mb-2">
                                                            <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2">
                                                                <Icon icon="solar:videocamera-record-bold" />
                                                                VEO 3.1 Video Prompt
                                                            </h4>
                                                            {!cutData?.videoPrompt && (
                                                                <span className="text-[10px] text-indigo-400/50 italic">Not generated</span>
                                                            )}
                                                        </div>
                                                        {cutData?.videoPrompt ? (
                                                            <p className="text-indigo-200/80 text-xs font-mono leading-relaxed select-all">
                                                                {cutData.videoPrompt}
                                                            </p>
                                                        ) : (
                                                            <div className="flex flex-col items-center justify-center py-4 gap-2">
                                                                <p className="text-indigo-300/50 text-xs mb-1">프롬프트가 없습니다.</p>
                                                                <button
                                                                    onClick={regenerateVeoData}
                                                                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition-all shadow-lg flex items-center gap-2"
                                                                >
                                                                    <Icon icon="solar:magic-stick-3-bold-duotone" />
                                                                    지금 생성하기 (Generate)
                                                                </button>
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Meta Info */}
                                                    <div className="grid grid-cols-2 gap-4">
                                                        <div className="bg-slate-800/30 p-3 rounded-lg border border-slate-800/50">
                                                            <h5 className="text-[10px] font-bold text-slate-500 mb-1">CHARACTER TAG</h5>
                                                            <p className="text-slate-300 text-xs">{cutData?.characterTag || "-"}</p>
                                                        </div>
                                                        <div className="bg-slate-800/30 p-3 rounded-lg border border-slate-800/50">
                                                            <h5 className="text-[10px] font-bold text-slate-500 mb-1">PHYSICS / SFX</h5>
                                                            <p className="text-slate-300 text-xs">
                                                                {cutData?.physicsDetail || "-"}<br />
                                                                <span className="text-slate-500 text-[10px] pt-1 block">{cutData?.sfxGuide}</span>
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>
                                            </motion.div>
                                        );
                                    })}
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
}
