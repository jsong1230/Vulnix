'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { SeverityBadge } from '@/components/vulnerability/severity-badge';
import { ScanTriggerButton } from '@/components/repos/scan-trigger-button';
import {
  getRepo,
  getRepoScans,
  getRepoVulnerabilities,
  type Repository,
  type ScanSummary,
  type VulnerabilitySummary,
} from '@/lib/repos-api';
import { formatRelativeTime, translateScanStatus, translateVulnStatus } from '@/lib/utils';

interface RepoDetailPageProps {
  params: { id: string };
}

/**
 * 스캔 상태별 색상 설정
 */
const SCAN_STATUS_STYLE: Record<
  ScanSummary['status'],
  { textColor: string; bgColor: string }
> = {
  queued: { textColor: 'text-yellow-400', bgColor: 'bg-yellow-400/10' },
  running: { textColor: 'text-blue-400', bgColor: 'bg-blue-400/10' },
  completed: { textColor: 'text-safe-400', bgColor: 'bg-safe-400/10' },
  failed: { textColor: 'text-danger-400', bgColor: 'bg-danger-400/10' },
};

/**
 * 저장소 상세 페이지
 * 저장소 기본 정보, 최근 스캔 목록, 취약점 목록 표시
 * GET /api/v1/repos/{id}, /scans, /vulnerabilities 연동
 */
export default function RepoDetailPage({ params }: RepoDetailPageProps) {
  const { id } = params;

  const [repo, setRepo] = useState<Repository | null>(null);
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<
    VulnerabilitySummary[]
  >([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 저장소 데이터 로드 (병렬 요청)
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [repoData, scansData, vulnsData] = await Promise.all([
        getRepo(id),
        getRepoScans(id),
        getRepoVulnerabilities(id),
      ]);
      setRepo(repoData);
      setScans(scansData);
      setVulnerabilities(vulnsData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '저장소 정보를 불러오지 못했습니다.',
      );
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // 로딩 상태
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <svg
          className="w-8 h-8 text-indigo-400 animate-spin"
          fill="none"
          viewBox="0 0 24 24"
          aria-label="로딩 중"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <span className="ml-3 text-gray-400">불러오는 중...</span>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div>
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/repos" className="hover:text-gray-300 transition-colors">
            저장소
          </Link>
        </div>
        <div className="card p-6 border-danger-800 bg-danger-950">
          <p className="text-danger-300 text-sm mb-4">{error}</p>
          <button
            onClick={() => void loadData()}
            className="btn-secondary text-sm"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  // 저장소 없음 (404)
  if (!repo) {
    return (
      <div>
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/repos" className="hover:text-gray-300 transition-colors">
            저장소
          </Link>
        </div>
        <div className="card p-12 text-center text-gray-500">
          <p className="text-sm">저장소를 찾을 수 없습니다.</p>
          <Link href="/repos" className="mt-4 btn-secondary text-sm inline-flex">
            저장소 목록으로 돌아가기
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* 브레드크럼 */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/repos" className="hover:text-gray-300 transition-colors">
          저장소
        </Link>
        <span>/</span>
        <span className="text-gray-300">{repo.fullName}</span>
      </div>

      {/* 저장소 헤더 */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">{repo.fullName}</h1>
          <div className="flex items-center gap-3 mt-2">
            {repo.language && (
              <>
                <span className="text-gray-500 text-sm">{repo.language}</span>
                <span className="text-gray-700">·</span>
              </>
            )}
            <span className="text-gray-500 text-sm">
              기본 브랜치: {repo.defaultBranch}
            </span>
            {!repo.isActive && (
              <>
                <span className="text-gray-700">·</span>
                <span className="text-xs px-1.5 py-0.5 bg-gray-800 text-gray-500 rounded border border-gray-700">
                  비활성
                </span>
              </>
            )}
          </div>
          {repo.lastScannedAt && (
            <p className="text-gray-600 text-xs mt-1">
              마지막 스캔: {formatRelativeTime(repo.lastScannedAt)}
            </p>
          )}
        </div>

        {/* 수동 스캔 버튼 */}
        {repo.isActive && (
          <ScanTriggerButton repoId={repo.id} onSuccess={() => void loadData()} />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 취약점 목록 — 2/3 폭 */}
        <div className="lg:col-span-2">
          <div className="card p-6">
            <h2 className="text-base font-semibold text-white mb-4">
              취약점 목록
              {vulnerabilities.length > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-500">
                  ({vulnerabilities.length}건)
                </span>
              )}
            </h2>

            {vulnerabilities.length === 0 ? (
              <div className="py-8 text-center text-gray-600">
                <svg
                  className="w-10 h-10 mx-auto mb-3 text-gray-800"
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
                <p className="text-sm">탐지된 취약점이 없습니다</p>
              </div>
            ) : (
              <div className="space-y-1">
                {vulnerabilities.map((vuln) => (
                  <Link
                    key={vuln.id}
                    href={`/vulnerabilities/${vuln.id}`}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition-colors"
                  >
                    <SeverityBadge severity={vuln.severity} />
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {vuln.vulnerabilityType}
                      </p>
                      <p className="text-gray-500 text-xs truncate">
                        {vuln.filePath}:{vuln.startLine}
                      </p>
                    </div>
                    <span className="text-gray-600 text-xs shrink-0">
                      {translateVulnStatus(vuln.status)}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 최근 스캔 히스토리 — 1/3 폭 */}
        <div>
          <div className="card p-6">
            <h2 className="text-base font-semibold text-white mb-4">
              최근 스캔
            </h2>

            {scans.length === 0 ? (
              <div className="py-8 text-center text-gray-600">
                <p className="text-sm">스캔 기록이 없습니다</p>
              </div>
            ) : (
              <div className="space-y-2">
                {scans.map((scan) => {
                  const statusStyle = SCAN_STATUS_STYLE[scan.status];
                  return (
                    <Link
                      key={scan.id}
                      href={`/scans/${scan.id}`}
                      className="block p-3 rounded-lg hover:bg-gray-800 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        {/* 스캔 상태 배지 */}
                        <span
                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${statusStyle.textColor} ${statusStyle.bgColor}`}
                        >
                          {scan.status === 'running' && (
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                          )}
                          {translateScanStatus(scan.status)}
                        </span>
                        <span className="text-xs text-gray-600">
                          {formatRelativeTime(scan.createdAt)}
                        </span>
                      </div>
                      <p className="text-gray-300 text-sm truncate">
                        {scan.branch ?? '—'}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        {scan.findingsCount}건 탐지
                        {scan.durationSeconds !== null && (
                          <span className="ml-2 text-gray-600">
                            ({scan.durationSeconds}초)
                          </span>
                        )}
                      </p>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
