'use client';

import React, { useState } from 'react';
import WorkflowController from '@/components/WorkflowController';
import HistoryView from '@/components/HistoryView';
import SettingsView from '@/components/SettingsView';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState<'generate' | 'history' | 'settings'>('generate');

  const navItems = [
    { id: 'generate', label: '워크플로우 생성', icon: 'solar:magic-stick-3-bold-duotone' },
    { id: 'history', label: '작업 내역 (Cloud)', icon: 'solar:folder-path-connect-bold-duotone' },
    { id: 'settings', label: '설정', icon: 'solar:settings-bold-duotone' },
  ];

  return (
    <main className="flex min-h-screen bg-slate-950 text-slate-200">

      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 flex flex-col shrink-0 bg-slate-900/50 backdrop-blur-xl">
        <nav className="flex-1 p-4 space-y-1 mt-4">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id as any)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${activeTab === item.id
                ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_rgba(37,99,235,0.1)]'
                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                }`}
            >
              <Icon
                icon={item.icon}
                className={`text-xl transition-transform group-hover:scale-110 ${activeTab === item.id ? 'text-blue-500' : 'text-slate-500'
                  }`}
              />
              <span className="font-bold text-sm tracking-tight">{item.label}</span>
              {activeTab === item.id && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(37,99,235,0.8)]" />
              )}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content Area */}
      <section className="flex-1 flex flex-col h-screen overflow-hidden">

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto w-full custom-scrollbar">
          <div className="max-w-7xl mx-auto w-full">
            <AnimatePresence mode="wait">
              {activeTab === 'generate' ? (
                <motion.div
                  key="gen"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="p-8"
                >
                  <WorkflowController onNavigate={(tab) => setActiveTab(tab as any)} />
                </motion.div>
              ) : activeTab === 'history' ? (
                <motion.div
                  key="hist"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  <HistoryView />
                </motion.div>
              ) : (
                <motion.div
                  key="settings"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  <SettingsView />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </section>
    </main>
  );
}
