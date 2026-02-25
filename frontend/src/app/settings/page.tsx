'use client';

import { useState } from 'react';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/lib/hooks/use-api-keys';
import type { ApiKeyCreated } from '@/lib/api-keys-api';

// ─── 아이콘 ────────────────────────────────────────────────────────────────────

const KeyIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 0 1 21.75 8.25Z" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

const CopyIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const GearIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
  </svg>
);

// ─── 날짜 포맷 ────────────────────────────────────────────────────────────────

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatRelativeTime(iso: string | null) {
  if (!iso) return '사용 없음';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return '오늘';
  if (days < 7) return `${days}일 전`;
  if (days < 30) return `${Math.floor(days / 7)}주 전`;
  return formatDate(iso);
}

// ─── 신규 발급 모달 ───────────────────────────────────────────────────────────

interface NewKeyModalProps {
  onClose: () => void;
  onCreated: (key: ApiKeyCreated) => void;
}

function NewKeyModal({ onClose, onCreated }: NewKeyModalProps) {
  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<string>('90');
  const createMutation = useCreateApiKey();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      {
        name,
        expiresInDays: expiresInDays ? Number(expiresInDays) : undefined,
      },
      {
        onSuccess: (key) => onCreated(key),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md p-6 mx-4">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <KeyIcon />
          새 API Key 발급
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              Key 이름 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="예: VSCode Extension"
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              유효 기간
            </label>
            <select
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="30">30일</option>
              <option value="90">90일</option>
              <option value="180">180일</option>
              <option value="365">1년</option>
              <option value="">만료 없음</option>
            </select>
          </div>

          {createMutation.isError && (
            <p className="text-red-400 text-xs">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : '발급에 실패했습니다.'}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="btn-primary"
            >
              {createMutation.isPending ? '발급 중...' : '발급'}
            </button>
            <button type="button" onClick={onClose} className="btn-secondary">
              취소
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── 발급된 Key 표시 모달 ─────────────────────────────────────────────────────

function CreatedKeyModal({
  apiKey,
  onClose,
}: {
  apiKey: ApiKeyCreated;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard.writeText(apiKey.fullKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-lg p-6 mx-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-emerald-400">
            <CheckIcon />
          </span>
          <h3 className="text-base font-semibold text-white">API Key 발급 완료</h3>
        </div>
        <p className="text-xs text-amber-400 mb-4">
          이 키는 지금 한 번만 표시됩니다. 안전한 곳에 보관하세요.
        </p>

        <div className="bg-gray-800 rounded-md p-3 flex items-center gap-2 mb-4">
          <code className="flex-1 text-xs text-emerald-300 font-mono break-all">
            {apiKey.fullKey}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className={`shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
              copied
                ? 'bg-emerald-700/40 text-emerald-300'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? '복사됨!' : '복사'}
          </button>
        </div>

        <button type="button" onClick={onClose} className="btn-secondary w-full">
          확인
        </button>
      </div>
    </div>
  );
}

// ─── API Key 탭 ───────────────────────────────────────────────────────────────

function ApiKeysTab() {
  const [showNewModal, setShowNewModal] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);

  const { data: apiKeys, isLoading, isError, refetch } = useApiKeys();
  const revokeMutation = useRevokeApiKey();

  const handleRevoke = (id: string, name: string) => {
    if (window.confirm(`"${name}" Key를 비활성화하시겠습니까?`)) {
      revokeMutation.mutate(id);
    }
  };

  const handleCreated = (key: ApiKeyCreated) => {
    setShowNewModal(false);
    setCreatedKey(key);
  };

  return (
    <div>
      {/* 모달 */}
      {showNewModal && (
        <NewKeyModal
          onClose={() => setShowNewModal(false)}
          onCreated={handleCreated}
        />
      )}
      {createdKey && (
        <CreatedKeyModal
          apiKey={createdKey}
          onClose={() => setCreatedKey(null)}
        />
      )}

      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-400">
          IDE 확장, CI/CD 파이프라인 등에서 Vulnix API에 접근할 때 사용합니다.
        </p>
        <button
          type="button"
          onClick={() => setShowNewModal(true)}
          className="btn-primary shrink-0"
        >
          <PlusIcon />
          새 Key 발급
        </button>
      </div>

      {/* 에러 */}
      {isError && (
        <div className="card border-red-900/50 p-4 mb-4 flex items-center justify-between">
          <p className="text-red-400 text-sm">데이터를 불러오지 못했습니다.</p>
          <button type="button" onClick={() => void refetch()} className="btn-secondary text-xs">
            재시도
          </button>
        </div>
      )}

      {/* 로딩 */}
      {isLoading && (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="card p-4">
              <div className="flex items-center gap-3">
                <div className="h-4 w-32 bg-gray-700 rounded" />
                <div className="h-4 w-24 bg-gray-700 rounded" />
                <div className="ml-auto h-6 w-16 bg-gray-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && apiKeys?.length === 0 && (
        <div className="card p-10 text-center">
          <div className="flex justify-center mb-3 text-gray-600">
            <KeyIcon />
          </div>
          <p className="text-gray-400 text-sm">발급된 API Key가 없습니다.</p>
        </div>
      )}

      {/* Key 목록 */}
      {!isLoading && apiKeys && apiKeys.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">이름</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">접두사</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">만료일</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">마지막 사용</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">상태</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3 font-medium text-white">{key.name}</td>
                  <td className="px-4 py-3">
                    <code className="text-xs font-mono text-gray-300 bg-gray-800 px-2 py-0.5 rounded">
                      {key.keyPrefix}...
                    </code>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{formatDate(key.expiresAt)}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{formatRelativeTime(key.lastUsedAt)}</td>
                  <td className="px-4 py-3">
                    {key.isActive ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-900/40 text-emerald-400">
                        활성
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-800 text-gray-500">
                        비활성
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {key.isActive && (
                      <button
                        type="button"
                        onClick={() => handleRevoke(key.id, key.name)}
                        disabled={revokeMutation.isPending}
                        className="text-xs text-red-400 hover:text-red-300 hover:bg-red-900/20 px-2.5 py-1.5 rounded transition-colors"
                      >
                        비활성화
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── 팀 설정 탭 ───────────────────────────────────────────────────────────────

type Locale = 'ko' | 'en';

function TeamSettingsTab() {
  const [locale, setLocale] = useState<Locale>('ko');

  return (
    <div className="max-w-md space-y-6">
      {/* 팀 이름 (읽기 전용) */}
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1.5">팀 이름</label>
        <div className="px-3 py-2 rounded-md bg-gray-800/50 border border-gray-700/50 text-gray-300 text-sm">
          My Team
        </div>
      </div>

      {/* 언어 설정 */}
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-2">인터페이스 언어</label>
        <div className="flex flex-col gap-2">
          {([['ko', '한국어'], ['en', 'English']] as [Locale, string][]).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="locale"
                value={value}
                checked={locale === value}
                onChange={() => setLocale(value)}
                className="w-4 h-4 text-indigo-600 bg-gray-800 border-gray-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-300">{label}</span>
            </label>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">언어 설정은 페이지 새로고침 후 적용됩니다.</p>
      </div>

      <button type="button" className="btn-primary">
        저장
      </button>
    </div>
  );
}

// ─── 페이지 ───────────────────────────────────────────────────────────────────

type Tab = 'apiKeys' | 'team';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('apiKeys');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'apiKeys', label: 'API Key 관리' },
    { key: 'team', label: '팀 설정' },
  ];

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
          <GearIcon />
          설정
        </h1>
        <p className="text-gray-400 mt-1 text-sm">
          API Key 관리와 팀 환경을 설정합니다.
        </p>
      </div>

      {/* 탭 내비게이션 */}
      <div className="border-b border-gray-800 mb-6">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.key
                  ? 'border-indigo-500 text-white'
                  : 'border-transparent text-gray-400 hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === 'apiKeys' && <ApiKeysTab />}
      {activeTab === 'team' && <TeamSettingsTab />}
    </div>
  );
}
