'use client';

import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { SeverityBadge } from '@/components/vulnerability/severity-badge';
import { CodeViewer } from '@/components/vulnerability/code-viewer';
import { PatchDiffViewer } from '@/components/vulnerability/patch-diff-viewer';
import { StatusActions } from '@/components/vulnerability/status-actions';
import {
  useVulnerabilityDetail,
  useUpdateVulnerabilityStatus,
} from '@/lib/hooks/use-vulnerabilities';
import type { VulnerabilityStatus } from '@/lib/scan-api';

interface VulnDetailPageProps {
  params: { id: string };
}

/** 취약점 처리 상태 배지 스타일 */
const statusStyleMap: Record<VulnerabilityStatus, string> = {
  open: 'text-red-400 bg-red-400/10',
  patched: 'text-green-400 bg-green-400/10',
  ignored: 'text-gray-400 bg-gray-400/10',
  false_positive: 'text-yellow-400 bg-yellow-400/10',
};

/**
 * 취약점 상세 페이지
 * React Query로 /api/v1/vulnerabilities/{id} 연동
 * 코드 뷰어, 패치 diff 뷰어, 상태 변경 기능 포함
 */
export default function VulnerabilityDetailPage({
  params,
}: VulnDetailPageProps) {
  const t = useTranslations();
  const { id } = params;

  const {
    data: vuln,
    isLoading,
    isError,
    error,
    refetch,
  } = useVulnerabilityDetail(id);

  const { mutate: updateStatus, isPending } = useUpdateVulnerabilityStatus();

  const handleStatusChange = (newStatus: VulnerabilityStatus) => {
    updateStatus({ vulnId: id, status: newStatus });
  };

  // ─── 로딩 상태 ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-4 bg-gray-800 rounded w-48 mb-6" />
        <div className="h-8 bg-gray-800 rounded w-64 mb-2" />
        <div className="h-4 bg-gray-800 rounded w-96 mb-8" />
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="card p-6 h-48" />
          <div className="card p-6 h-48" />
        </div>
      </div>
    );
  }

  // ─── 에러 상태 ────────────────────────────────────────────────────────────
  if (isError || !vuln) {
    return (
      <div className="card border-red-900/50 p-6 flex items-center justify-between">
        <div>
          <p className="text-red-400 font-medium text-sm mb-1">
            취약점 정보를 불러오지 못했습니다
          </p>
          <p className="text-gray-600 text-xs">
            {error instanceof Error ? error.message : '알 수 없는 오류'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refetch()}
          className="btn-secondary text-sm"
        >
          재시도
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* 브레드크럼 */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/repos" className="hover:text-gray-300 transition-colors">
          {t('repos.title')}
        </Link>
        <span>/</span>
        {vuln.repoId && (
          <>
            <Link
              href={`/repos/${vuln.repoId}`}
              className="hover:text-gray-300 transition-colors"
            >
              {vuln.repoFullName ?? vuln.repoId}
            </Link>
            <span>/</span>
          </>
        )}
        <span className="text-gray-300">취약점 상세</span>
      </div>

      {/* 취약점 헤더 */}
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <SeverityBadge severity={vuln.severity} size="lg" />
            {/* 처리 상태 배지 */}
            <span
              className={`inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium ${statusStyleMap[vuln.status]}`}
            >
              {t(`vulnerability.status.${vuln.status}`)}
            </span>
            <h1 className="text-xl font-bold text-white">
              {vuln.vulnerabilityType}
            </h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
            {vuln.cweId && <span>{vuln.cweId}</span>}
            {vuln.cweId && vuln.owaspCategory && <span>·</span>}
            {vuln.owaspCategory && <span>{vuln.owaspCategory}</span>}
            {(vuln.cweId || vuln.owaspCategory) && <span>·</span>}
            <span>
              {vuln.filePath}:{vuln.startLine}–{vuln.endLine}
            </span>
          </div>
        </div>

        {/* 상태 변경 액션 버튼 */}
        <StatusActions
          vulnId={id}
          currentStatus={vuln.status}
          onStatusChange={handleStatusChange}
          isPending={isPending}
        />
      </div>

      {/* 패치 PR 링크 (있을 경우) */}
      {vuln.patchPr?.githubPrUrl && (
        <div className="card p-4 mb-6 flex items-center gap-3">
          <svg
            className="w-5 h-5 text-green-400 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
            />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-medium">패치 PR이 생성되었습니다</p>
            {vuln.patchPr.patchDescription && (
              <p className="text-gray-500 text-xs truncate">
                {vuln.patchPr.patchDescription}
              </p>
            )}
          </div>
          <a
            href={vuln.patchPr.githubPrUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary text-sm flex items-center gap-1.5 shrink-0"
          >
            PR #{vuln.patchPr.githubPrNumber} 보기
            {/* 외부 링크 아이콘 */}
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
              />
            </svg>
          </a>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* 취약한 코드 스니펫 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            취약한 코드
          </h2>
          {vuln.codeSnippet ? (
            <CodeViewer
              codeSnippet={vuln.codeSnippet}
              startLine={vuln.startLine}
              highlightStart={vuln.startLine}
              highlightEnd={vuln.endLine}
            />
          ) : (
            <p className="text-gray-600 text-sm">코드 스니펫이 없습니다.</p>
          )}
        </div>

        {/* LLM 분석 결과 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            AI 분석 결과
          </h2>

          {/* 확신도 */}
          {vuln.llmConfidence !== null && (
            <div className="mb-4">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-400">탐지 확신도</span>
                <span className="text-white font-medium">
                  {Math.round(vuln.llmConfidence * 100)}%
                </span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all"
                  style={{ width: `${vuln.llmConfidence * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* 취약점 설명 */}
          {vuln.description && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">취약점 설명</h3>
              <p className="text-gray-300 text-sm leading-relaxed">
                {vuln.description}
              </p>
            </div>
          )}

          {/* LLM 판단 근거 */}
          {vuln.llmReasoning && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">판단 근거</h3>
              <p className="text-gray-300 text-sm leading-relaxed">
                {vuln.llmReasoning}
              </p>
            </div>
          )}

          {/* 참고 자료 */}
          {vuln.references.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">참고 자료</h3>
              <ul className="space-y-1">
                {vuln.references.map((ref) => (
                  <li key={ref}>
                    <a
                      href={ref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-400 hover:text-indigo-300 text-sm transition-colors break-all"
                    >
                      {ref}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* 패치 Diff */}
        {vuln.patchPr?.patchDiff ? (
          <div className="card p-6 xl:col-span-2">
            <h2 className="text-base font-semibold text-white mb-4">
              제안된 패치
            </h2>
            <PatchDiffViewer diff={vuln.patchPr.patchDiff} />
          </div>
        ) : (
          <div className="card p-6 xl:col-span-2 flex items-center gap-4 text-gray-600">
            <svg
              className="w-8 h-8 text-gray-800 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-gray-400">
                패치 코드 생성 대기 중
              </p>
              <p className="text-xs mt-0.5">
                LLM 에이전트가 패치 코드를 생성합니다
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
