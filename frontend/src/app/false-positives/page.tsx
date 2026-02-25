'use client';

import { useState } from 'react';
import {
  useFalsePositives,
  useCreateFalsePositive,
  useUpdateFalsePositive,
  useDeleteFalsePositive,
} from '@/lib/hooks/use-false-positives';

const ShieldIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
  </svg>
);

function AddPatternForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ semgrepRuleId: '', filePattern: '', reason: '' });
  const createMutation = useCreateFalsePositive();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      { semgrepRuleId: form.semgrepRuleId, filePattern: form.filePattern || undefined, reason: form.reason },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <div className="card p-5 border-indigo-800/50 mb-6">
      <h3 className="text-sm font-semibold text-white mb-4">오탐 패턴 추가</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Semgrep Rule ID <span className="text-red-400">*</span></label>
          <input type="text" value={form.semgrepRuleId} onChange={(e) => setForm((f) => ({ ...f, semgrepRuleId: e.target.value }))} required
            placeholder="예: python.django.security.injection.tainted-sql-string"
            className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">파일 패턴 (glob, 선택)</label>
          <input type="text" value={form.filePattern} onChange={(e) => setForm((f) => ({ ...f, filePattern: e.target.value }))}
            placeholder="예: tests/**/*.py"
            className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">오탐 사유 <span className="text-red-400">*</span></label>
          <textarea value={form.reason} onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} required rows={2}
            placeholder="이 룰이 해당 파일에서 오탐인 이유를 간략히 입력하세요."
            className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none" />
        </div>
        {createMutation.isError && (
          <p className="text-red-400 text-xs">{createMutation.error instanceof Error ? createMutation.error.message : '등록에 실패했습니다.'}</p>
        )}
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={createMutation.isPending} className="btn-primary">{createMutation.isPending ? '등록 중...' : '추가'}</button>
          <button type="button" onClick={onClose} className="btn-secondary">취소</button>
        </div>
      </form>
    </div>
  );
}

export default function FalsePositivesPage() {
  const [showForm, setShowForm] = useState(false);
  const { data: patterns, isLoading, isError, refetch } = useFalsePositives();
  const updateMutation = useUpdateFalsePositive();
  const deleteMutation = useDeleteFalsePositive();

  const handleToggleActive = (id: string, current: boolean) => {
    updateMutation.mutate({ id, data: { isActive: !current } });
  };

  const handleDelete = (id: string) => {
    if (window.confirm('이 오탐 패턴을 삭제하시겠습니까?')) { deleteMutation.mutate(id); }
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5"><ShieldIcon />오탐 관리</h1>
          <p className="text-gray-400 mt-1 text-sm">특정 Semgrep 룰을 오탐으로 마킹하여 불필요한 경고를 제거하세요.</p>
        </div>
        {!showForm && (
          <button type="button" onClick={() => setShowForm(true)} className="btn-primary"><PlusIcon />패턴 추가</button>
        )}
      </div>

      {showForm && <AddPatternForm onClose={() => setShowForm(false)} />}

      {isError && (
        <div className="card border-red-900/50 p-4 mb-6 flex items-center justify-between">
          <p className="text-red-400 text-sm">데이터를 불러오지 못했습니다.</p>
          <button type="button" onClick={() => void refetch()} className="btn-secondary text-xs">재시도</button>
        </div>
      )}

      {isLoading && (
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-4"><div className="h-4 w-full bg-gray-700 rounded" /></div>
          ))}
        </div>
      )}

      {!isLoading && patterns?.length === 0 && (
        <div className="card p-12 text-center">
          <div className="flex justify-center mb-3 text-gray-600"><ShieldIcon /></div>
          <p className="text-gray-400 text-sm">등록된 오탐 패턴이 없습니다.</p>
          <button type="button" onClick={() => setShowForm(true)} className="btn-primary mt-4"><PlusIcon />첫 번째 패턴 추가</button>
        </div>
      )}

      {!isLoading && patterns && patterns.length > 0 && (
        <div className="space-y-3">
          {patterns.map((pattern) => (
            <div key={pattern.id} className="card p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <code className="text-sm font-mono text-indigo-300">{pattern.semgrepRuleId}</code>
                  {pattern.filePattern && (
                    <span className="ml-3 text-xs font-mono text-gray-500 bg-gray-800 px-2 py-0.5 rounded">{pattern.filePattern}</span>
                  )}
                  <p className="mt-1.5 text-xs text-gray-400">{pattern.reason}</p>
                  <p className="mt-1 text-xs text-gray-600">{pattern.createdBy} · {new Date(pattern.createdAt).toLocaleDateString('ko-KR')}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button type="button" onClick={() => handleToggleActive(pattern.id, pattern.isActive)}
                    disabled={updateMutation.isPending}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${pattern.isActive ? 'bg-indigo-600' : 'bg-gray-700'}`}
                    title={pattern.isActive ? '비활성화' : '활성화'}>
                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${pattern.isActive ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
                  </button>
                  <button type="button" onClick={() => handleDelete(pattern.id)} disabled={deleteMutation.isPending}
                    className="p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-900/20 transition-colors" title="삭제">
                    <TrashIcon />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
