'use client';

import { useState } from 'react';
import Link from 'next/link';
import { SeverityBadge } from '@/components/vulnerability/severity-badge';
import { useVulnerabilityList } from '@/lib/hooks/use-vulnerabilities';
import type { Severity, VulnerabilityStatus } from '@/lib/scan-api';

// ─── 상수 정의 ─────────────────────────────────────────────────────────────────

/** 심각도 필터 옵션 */
const SEVERITY_OPTIONS: { label: string; value: Severity | '' }[] = [
  { label: '전체', value: '' },
  { label: 'Critical', value: 'critical' },
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
];

/** 상태 필터 옵션 */
const STATUS_OPTIONS: { label: string; value: VulnerabilityStatus | '' }[] = [
  { label: '전체', value: '' },
  { label: 'Open', value: 'open' },
  { label: 'Patched', value: 'patched' },
  { label: 'Ignored', value: 'ignored' },
  { label: 'False Positive', value: 'false_positive' },
];

/** 취약점 처리 상태 배지 스타일 */
const statusStyleMap: Record<VulnerabilityStatus, string> = {
  open: 'text-red-400 bg-red-400/10',
  patched: 'text-green-400 bg-green-400/10',
  ignored: 'text-gray-400 bg-gray-400/10',
  false_positive: 'text-yellow-400 bg-yellow-400/10',
};

/** 취약점 처리 상태 한국어 레이블 */
const statusLabelMap: Record<VulnerabilityStatus, string> = {
  open: 'Open',
  patched: 'Patched',
  ignored: 'Ignored',
  false_positive: 'False Positive',
};

// ─── 컴포넌트 ──────────────────────────────────────────────────────────────────

/**
 * 취약점 목록 페이지
 * 심각도/상태 필터 및 페이지네이션 지원
 * React Query를 통해 /api/v1/vulnerabilities 연동
 */
export default function VulnerabilitiesPage() {
  // 필터 상태
  const [severity, setSeverity] = useState<Severity | ''>('');
  const [status, setStatus] = useState<VulnerabilityStatus | ''>('');
  const [page, setPage] = useState(1);

  // 취약점 목록 조회
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useVulnerabilityList({
    ...(severity ? { severity } : {}),
    ...(status ? { status } : {}),
    page,
    perPage: 20,
  });

  const vulnerabilities = data?.items ?? [];
  const meta = data?.meta;
  const totalPages = meta?.total_pages ?? 1;

  // 필터 변경 시 페이지를 1로 리셋
  const handleSeverityChange = (value: Severity | '') => {
    setSeverity(value);
    setPage(1);
  };

  const handleStatusChange = (value: VulnerabilityStatus | '') => {
    setStatus(value);
    setPage(1);
  };

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">취약점 목록</h1>
        <p className="text-gray-400 mt-1 text-sm">
          탐지된 모든 보안 취약점을 조회하고 관리합니다
        </p>
      </div>

      {/* 필터 바 */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {/* 심각도 필터 */}
        <div className="flex items-center gap-1.5">
          <span className="text-gray-500 text-xs">심각도</span>
          <div className="flex gap-1">
            {SEVERITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSeverityChange(opt.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  severity === opt.value
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-4 w-px bg-gray-700 hidden sm:block" />

        {/* 상태 필터 */}
        <div className="flex items-center gap-1.5">
          <span className="text-gray-500 text-xs">상태</span>
          <div className="flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleStatusChange(opt.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  status === opt.value
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* 전체 건수 */}
        {!isLoading && meta && (
          <span className="ml-auto text-gray-500 text-xs">
            총 {meta.total}건
          </span>
        )}
      </div>

      {/* 에러 상태 */}
      {isError && !isLoading && (
        <div className="card border-red-900/50 p-4 mb-6 flex items-center justify-between">
          <p className="text-red-400 text-sm">
            {error instanceof Error
              ? error.message
              : '취약점 목록을 불러오지 못했습니다.'}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="btn-secondary text-xs shrink-0"
          >
            재시도
          </button>
        </div>
      )}

      {/* 테이블 */}
      <div className="card overflow-hidden">
        {/* 테이블 헤더 */}
        <div className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-4 py-3 border-b border-gray-800 text-xs text-gray-500 font-medium">
          <span>심각도</span>
          <span>취약점 / 파일</span>
          <span className="hidden sm:block">상태</span>
          <span className="hidden md:block">탐지 일시</span>
          <span className="sr-only">상세</span>
        </div>

        {/* 로딩 스켈레톤 */}
        {isLoading && (
          <div className="divide-y divide-gray-800 animate-pulse">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-4 py-3.5 items-center"
              >
                <div className="h-5 w-14 bg-gray-800 rounded" />
                <div>
                  <div className="h-3.5 bg-gray-800 rounded w-48 mb-1.5" />
                  <div className="h-3 bg-gray-800/60 rounded w-64" />
                </div>
                <div className="h-5 w-16 bg-gray-800 rounded-full hidden sm:block" />
                <div className="h-3 w-20 bg-gray-800 rounded hidden md:block" />
                <div className="h-4 w-4 bg-gray-800 rounded" />
              </div>
            ))}
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && !isError && vulnerabilities.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-600">
            <svg
              className="w-12 h-12 mb-3 text-gray-800"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
              />
            </svg>
            <p className="text-sm font-medium text-gray-400 mb-1">
              취약점이 없습니다
            </p>
            <p className="text-xs">
              {severity || status
                ? '선택한 필터에 해당하는 취약점이 없습니다'
                : '아직 탐지된 취약점이 없습니다'}
            </p>
          </div>
        )}

        {/* 취약점 행 목록 */}
        {!isLoading && !isError && vulnerabilities.length > 0 && (
          <div className="divide-y divide-gray-800/60">
            {vulnerabilities.map((vuln) => (
              <Link
                key={vuln.id}
                href={`/vulnerabilities/${vuln.id}`}
                className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-4 py-3.5 items-center hover:bg-gray-800/50 transition-colors"
              >
                {/* 심각도 배지 */}
                <SeverityBadge severity={vuln.severity} />

                {/* 취약점 타입 + 파일 경로 */}
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium truncate">
                    {vuln.vulnerabilityType}
                  </p>
                  <p className="text-gray-500 text-xs truncate mt-0.5">
                    {vuln.filePath}
                    <span className="text-gray-600 ml-1">:{vuln.startLine}</span>
                  </p>
                </div>

                {/* 처리 상태 배지 */}
                <span
                  className={`hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${statusStyleMap[vuln.status]}`}
                >
                  {statusLabelMap[vuln.status]}
                </span>

                {/* 탐지 일시 */}
                <time
                  dateTime={vuln.detectedAt}
                  className="hidden md:block text-gray-500 text-xs shrink-0"
                >
                  {new Date(vuln.detectedAt).toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </time>

                {/* 화살표 아이콘 */}
                <svg
                  className="w-4 h-4 text-gray-600 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.25 4.5l7.5 7.5-7.5 7.5"
                  />
                </svg>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* 페이지네이션 */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn-secondary text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            이전
          </button>
          <span className="text-gray-500 text-sm">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn-secondary text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
