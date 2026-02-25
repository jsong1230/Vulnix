'use client';

import { useState } from 'react';
import {
  useNotifications,
  useCreateNotification,
  useUpdateNotification,
  useDeleteNotification,
  useTestNotification,
} from '@/lib/hooks/use-notifications';
import type {
  NotificationPlatform,
  SeverityThreshold,
} from '@/lib/notifications-api';

// ─── 아이콘 ────────────────────────────────────────────────────────────────────

const BellIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

// ─── 플랫폼 배지 ───────────────────────────────────────────────────────────────

function PlatformBadge({ platform }: { platform: NotificationPlatform }) {
  if (platform === 'slack') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-900/40 text-emerald-400 border border-emerald-800/50">
        <span className="w-2 h-2 rounded-full bg-emerald-400" />
        Slack
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-900/40 text-purple-400 border border-purple-800/50">
      <span className="w-2 h-2 rounded-full bg-purple-400" />
      Teams
    </span>
  );
}

// ─── 심각도 라벨 ──────────────────────────────────────────────────────────────

const SEVERITY_LABELS: Record<SeverityThreshold, string> = {
  all: '전체',
  high: 'High 이상',
  critical: 'Critical만',
};

// ─── 추가 폼 ──────────────────────────────────────────────────────────────────

interface AddFormState {
  platform: NotificationPlatform;
  webhookUrl: string;
  severityThreshold: SeverityThreshold;
  weeklyReportEnabled: boolean;
}

function AddNotificationForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState<AddFormState>({
    platform: 'slack',
    webhookUrl: '',
    severityThreshold: 'high',
    weeklyReportEnabled: false,
  });

  const createMutation = useCreateNotification();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(form, {
      onSuccess: () => onClose(),
    });
  };

  return (
    <div className="card p-5 border-indigo-800/50">
      <h3 className="text-sm font-semibold text-white mb-4">새 알림 채널 추가</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* 플랫폼 선택 */}
        <div className="flex gap-3">
          {(['slack', 'teams'] as NotificationPlatform[]).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setForm((f) => ({ ...f, platform: p }))}
              className={`flex-1 py-2 px-3 rounded-md border text-sm font-medium transition-colors ${
                form.platform === p
                  ? 'border-indigo-500 bg-indigo-600/20 text-indigo-300'
                  : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600'
              }`}
            >
              {p === 'slack' ? 'Slack' : 'Microsoft Teams'}
            </button>
          ))}
        </div>

        {/* Webhook URL */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">
            Webhook URL <span className="text-red-400">*</span>
          </label>
          <input
            type="url"
            value={form.webhookUrl}
            onChange={(e) => setForm((f) => ({ ...f, webhookUrl: e.target.value }))}
            required
            placeholder={
              form.platform === 'slack'
                ? 'https://hooks.slack.com/services/...'
                : 'https://outlook.office.com/webhook/...'
            }
            className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        {/* 심각도 임계값 */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">
            알림 심각도
          </label>
          <select
            value={form.severityThreshold}
            onChange={(e) =>
              setForm((f) => ({ ...f, severityThreshold: e.target.value as SeverityThreshold }))
            }
            className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="all">전체 (Low 이상)</option>
            <option value="high">High 이상</option>
            <option value="critical">Critical만</option>
          </select>
        </div>

        {/* 주간 리포트 */}
        <label className="flex items-center gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={form.weeklyReportEnabled}
            onChange={(e) =>
              setForm((f) => ({ ...f, weeklyReportEnabled: e.target.checked }))
            }
            className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-indigo-600 focus:ring-indigo-500"
          />
          <span className="text-sm text-gray-300">주간 보안 리포트 발송</span>
        </label>

        {/* 에러 표시 */}
        {createMutation.isError && (
          <p className="text-red-400 text-xs">
            {createMutation.error instanceof Error
              ? createMutation.error.message
              : '등록에 실패했습니다.'}
          </p>
        )}

        {/* 버튼 */}
        <div className="flex gap-2 pt-1">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="btn-primary"
          >
            {createMutation.isPending ? '등록 중...' : '추가'}
          </button>
          <button type="button" onClick={onClose} className="btn-secondary">
            취소
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── 페이지 ───────────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const [showForm, setShowForm] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const { data: configs, isLoading, isError, refetch } = useNotifications();
  const updateMutation = useUpdateNotification();
  const deleteMutation = useDeleteNotification();
  const testMutation = useTestNotification();

  const handleToggleActive = (id: string, current: boolean) => {
    updateMutation.mutate({ id, data: { isActive: !current } });
  };

  const handleDelete = (id: string) => {
    if (window.confirm('이 알림 설정을 삭제하시겠습니까?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleTest = (id: string) => {
    setTestingId(id);
    testMutation.mutate(id, {
      onSettled: () => setTestingId(null),
    });
  };

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <BellIcon />
            알림 설정
          </h1>
          <p className="text-gray-400 mt-1 text-sm">
            Slack, Teams Webhook을 연결하여 취약점 발생 시 즉시 알림을 받으세요.
          </p>
        </div>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="btn-primary"
          >
            <PlusIcon />
            알림 채널 추가
          </button>
        )}
      </div>

      {/* 추가 폼 */}
      {showForm && (
        <div className="mb-6">
          <AddNotificationForm onClose={() => setShowForm(false)} />
        </div>
      )}

      {/* 에러 */}
      {isError && (
        <div className="card border-red-900/50 p-4 mb-6 flex items-center justify-between">
          <p className="text-red-400 text-sm">데이터를 불러오지 못했습니다.</p>
          <button type="button" onClick={() => void refetch()} className="btn-secondary text-xs">
            재시도
          </button>
        </div>
      )}

      {/* 로딩 스켈레톤 */}
      {isLoading && (
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-6 w-16 bg-gray-700 rounded-full" />
                  <div className="h-4 w-56 bg-gray-700 rounded" />
                </div>
                <div className="h-6 w-20 bg-gray-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && configs?.length === 0 && (
        <div className="card p-12 text-center">
          <BellIcon />
          <p className="mt-3 text-gray-400 text-sm">등록된 알림 설정이 없습니다.</p>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="btn-primary mt-4"
          >
            <PlusIcon />
            첫 번째 채널 추가
          </button>
        </div>
      )}

      {/* 알림 설정 목록 */}
      {!isLoading && configs && configs.length > 0 && (
        <div className="space-y-3">
          {configs.map((config) => (
            <div key={config.id} className="card p-5">
              <div className="flex items-start justify-between gap-4">
                {/* 왼쪽: 플랫폼 정보 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <PlatformBadge platform={config.platform} />
                    <span className="text-xs text-gray-500">
                      심각도: <span className="text-gray-300">{SEVERITY_LABELS[config.severityThreshold]}</span>
                    </span>
                    {config.weeklyReportEnabled && (
                      <span className="text-xs text-indigo-400">주간 리포트 ON</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-400 font-mono truncate" title={config.webhookUrl}>
                    {config.webhookUrl}
                  </p>
                </div>

                {/* 오른쪽: 액션 버튼들 */}
                <div className="flex items-center gap-2 shrink-0">
                  {/* 활성화 토글 */}
                  <button
                    type="button"
                    onClick={() => handleToggleActive(config.id, config.isActive)}
                    disabled={updateMutation.isPending}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
                      config.isActive ? 'bg-indigo-600' : 'bg-gray-700'
                    }`}
                    title={config.isActive ? '비활성화' : '활성화'}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                        config.isActive ? 'translate-x-4.5' : 'translate-x-0.5'
                      }`}
                    />
                  </button>

                  {/* 테스트 발송 */}
                  <button
                    type="button"
                    onClick={() => handleTest(config.id)}
                    disabled={testingId === config.id}
                    className="btn-secondary text-xs px-3 py-1.5"
                  >
                    {testingId === config.id ? '발송 중...' : '테스트 발송'}
                  </button>

                  {/* 삭제 */}
                  <button
                    type="button"
                    onClick={() => handleDelete(config.id)}
                    disabled={deleteMutation.isPending}
                    className="p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                    title="삭제"
                  >
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
