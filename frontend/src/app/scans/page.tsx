'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useScans } from '@/lib/hooks/use-scans';
import type { ScanStatus } from '@/lib/scan-api';

// ─── 상수 정의 ─────────────────────────────────────────────────────────────────

/** 스캔 상태 배지 스타일 */
const statusStyleMap: Record<
  ScanStatus,
  { label: string; textColor: string; bgColor: string; pulse?: boolean }
> = {
  queued: {
    label: '대기 중',
    textColor: 'text-yellow-400',
    bgColor: 'bg-yellow-400/10',
  },
  running: {
    label: '스캔 중',
    textColor: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
    pulse: true,
  },
  completed: {
    label: '완료',
    textColor: 'text-green-400',
    bgColor: 'bg-green-400/10',
  },
  failed: {
    label: '실패',
    textColor: 'text-red-400',
    bgColor: 'bg-red-400/10',
  },
};

/** 트리거 타입 한국어 레이블 */
const triggerLabelMap: Record<'manual' | 'webhook' | 'schedule', string> = {
  manual: '수동',
  webhook: 'Webhook',
  schedule: '예약',
};

// ─── 컴포넌트 ──────────────────────────────────────────────────────────────────

/**
 * 스캔 목록 페이지
 * 전체 스캔 이력을 테이블 형식으로 표시
 * React Query를 통해 /api/v1/scans 연동
 */
export default function ScansPage() {
  const [page, setPage] = useState(1);

  // 스캔 목록 조회
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useScans({ page, perPage: 20 });

  const scans = data?.items ?? [];
  const meta = data?.meta;
  const totalPages = meta?.total_pages ?? 1;

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">스캔 이력</h1>
        <p className="text-gray-400 mt-1 text-sm">
          저장소별 보안 스캔 실행 이력을 조회합니다
        </p>
      </div>

      {/* 에러 상태 */}
      {isError && !isLoading && (
        <div className="card border-red-900/50 p-4 mb-6 flex items-center justify-between">
          <p className="text-red-400 text-sm">
            {error instanceof Error
              ? error.message
              : '스캔 목록을 불러오지 못했습니다.'}
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
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-3 border-b border-gray-800 text-xs text-gray-500 font-medium">
          <span>저장소</span>
          <span>상태</span>
          <span className="hidden sm:block">트리거</span>
          <span className="hidden md:block">탐지 건수</span>
          <span className="hidden lg:block">시작 시간</span>
          <span className="sr-only">상세</span>
        </div>

        {/* 로딩 스켈레톤 */}
        {isLoading && (
          <div className="divide-y divide-gray-800 animate-pulse">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-3.5 items-center"
              >
                <div>
                  <div className="h-3.5 bg-gray-800 rounded w-40 mb-1.5" />
                  <div className="h-3 bg-gray-800/60 rounded w-24" />
                </div>
                <div className="h-5 w-14 bg-gray-800 rounded-full" />
                <div className="h-4 w-10 bg-gray-800 rounded hidden sm:block" />
                <div className="h-4 w-8 bg-gray-800 rounded hidden md:block" />
                <div className="h-3 w-20 bg-gray-800 rounded hidden lg:block" />
                <div className="h-4 w-4 bg-gray-800 rounded" />
              </div>
            ))}
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && !isError && scans.length === 0 && (
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
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
              />
            </svg>
            <p className="text-sm font-medium text-gray-400 mb-1">
              스캔 이력이 없습니다
            </p>
            <p className="text-xs">
              저장소를 연동하고 스캔을 실행하면 이곳에 표시됩니다
            </p>
          </div>
        )}

        {/* 스캔 행 목록 */}
        {!isLoading && !isError && scans.length > 0 && (
          <div className="divide-y divide-gray-800/60">
            {scans.map((scan) => {
              const style = statusStyleMap[scan.status];
              return (
                <Link
                  key={scan.id}
                  href={`/scans/${scan.id}`}
                  className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-3.5 items-center hover:bg-gray-800/50 transition-colors"
                >
                  {/* 저장소 정보 */}
                  <div className="min-w-0">
                    <p className="text-white text-sm font-medium truncate">
                      {scan.repoFullName ?? scan.repoId}
                    </p>
                    <p className="text-gray-600 text-xs font-mono mt-0.5">
                      #{scan.id.slice(0, 8)}
                    </p>
                  </div>

                  {/* 상태 배지 */}
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${style.textColor} ${style.bgColor}`}
                  >
                    {style.pulse && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                    )}
                    {style.label}
                  </span>

                  {/* 트리거 타입 */}
                  <span className="hidden sm:block text-gray-500 text-xs shrink-0">
                    {triggerLabelMap[scan.triggerType]}
                  </span>

                  {/* 탐지 건수 */}
                  <span className="hidden md:block text-gray-300 text-sm font-medium tabular-nums shrink-0">
                    {scan.status === 'completed' ? scan.findingsCount : '—'}
                  </span>

                  {/* 시작 시간 */}
                  <time
                    dateTime={scan.startedAt ?? scan.createdAt}
                    className="hidden lg:block text-gray-500 text-xs shrink-0"
                  >
                    {new Date(scan.startedAt ?? scan.createdAt).toLocaleDateString(
                      'ko-KR',
                      {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      },
                    )}
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
              );
            })}
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
