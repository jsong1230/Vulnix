'use client';

import Link from 'next/link';
import { SeverityBadge } from '@/components/vulnerability/severity-badge';
import { useScanDetail } from '@/lib/hooks/use-scans';
import { useVulnerabilityList } from '@/lib/hooks/use-vulnerabilities';
import type { ScanStatus } from '@/lib/scan-api';

interface ScanDetailPageProps {
  params: { id: string };
}

/** 스캔 상태별 배지 표시 설정 */
const statusConfig: Record<
  ScanStatus,
  { label: string; color: string; bgColor: string }
> = {
  queued: {
    label: '대기 중',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-400/10',
  },
  running: {
    label: '스캔 중',
    color: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
  },
  completed: {
    label: '완료',
    color: 'text-green-400',
    bgColor: 'bg-green-400/10',
  },
  failed: {
    label: '실패',
    color: 'text-red-400',
    bgColor: 'bg-red-400/10',
  },
};

/**
 * 소요 시간(초)을 "X분 Y초" 형식으로 변환
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (remainingSeconds === 0) return `${minutes}분`;
  return `${minutes}분 ${remainingSeconds}초`;
}

/**
 * 스캔 상세 페이지
 * React Query를 통해 /api/v1/scans/{id} 연동
 * queued/running 상태일 때 2초 간격 자동 폴링
 */
export default function ScanDetailPage({ params }: ScanDetailPageProps) {
  const { id } = params;

  // 스캔 상세 조회 (자동 폴링 포함)
  const {
    data: scan,
    isLoading: scanLoading,
    isError: scanError,
    error: scanErrorObj,
    refetch: refetchScan,
  } = useScanDetail(id);

  // 스캔 완료 후 해당 저장소의 취약점 목록 조회
  const isCompleted = scan?.status === 'completed';
  const {
    data: vulnsData,
    isLoading: vulnsLoading,
  } = useVulnerabilityList(
    { repoId: scan?.repoId, page: 1, perPage: 50 },
    // 완료 상태이고 repoId가 있을 때만 API 호출
    { enabled: isCompleted && Boolean(scan?.repoId) },
  );

  // ─── 로딩 상태 ────────────────────────────────────────────────────────────
  if (scanLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-4 bg-gray-800 rounded w-48 mb-6" />
        <div className="h-8 bg-gray-800 rounded w-64 mb-2" />
        <div className="h-4 bg-gray-800 rounded w-80 mb-8" />
        <div className="card p-6 h-32 mb-6" />
        <div className="grid grid-cols-3 gap-4">
          <div className="card p-4 h-20" />
          <div className="card p-4 h-20" />
          <div className="card p-4 h-20" />
        </div>
      </div>
    );
  }

  // ─── 에러 상태 ────────────────────────────────────────────────────────────
  if (scanError || !scan) {
    return (
      <div className="card border-red-900/50 p-6 flex items-center justify-between">
        <div>
          <p className="text-red-400 font-medium text-sm mb-1">
            스캔 정보를 불러오지 못했습니다
          </p>
          <p className="text-gray-600 text-xs">
            {scanErrorObj instanceof Error
              ? scanErrorObj.message
              : '알 수 없는 오류'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refetchScan()}
          className="btn-secondary text-sm"
        >
          재시도
        </button>
      </div>
    );
  }

  const statusDisplay = statusConfig[scan.status];
  const vulnerabilities = vulnsData?.items ?? [];

  return (
    <div>
      {/* 브레드크럼 */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/repos" className="hover:text-gray-300 transition-colors">
          저장소
        </Link>
        <span>/</span>
        <Link
          href={`/repos/${scan.repoId}`}
          className="hover:text-gray-300 transition-colors"
        >
          {scan.repoId}
        </Link>
        <span>/</span>
        <span className="text-gray-300">스캔 #{id.slice(0, 8)}</span>
      </div>

      {/* 스캔 헤더 */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            {/* 상태 배지 */}
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${statusDisplay.color} ${statusDisplay.bgColor}`}
            >
              {/* 실행 중일 때 펄스 애니메이션 */}
              {scan.status === 'running' && (
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              )}
              {statusDisplay.label}
            </span>
            <h1 className="text-xl font-bold text-white">스캔 결과</h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
            {scan.branch && <span>{scan.branch}</span>}
            {scan.branch && scan.commitSha && <span>·</span>}
            {scan.commitSha && (
              <span className="font-mono">{scan.commitSha.slice(0, 7)}</span>
            )}
            {scan.prNumber && (
              <>
                <span>·</span>
                <span>PR #{scan.prNumber}</span>
              </>
            )}
            {scan.durationSeconds !== null && scan.status === 'completed' && (
              <>
                <span>·</span>
                <span>소요 시간 {formatDuration(scan.durationSeconds)}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 스캔 진행 중 안내 (queued/running) */}
      {(scan.status === 'queued' || scan.status === 'running') && (
        <div className="card p-6 mb-6 flex items-center gap-4">
          <div className="w-10 h-10 bg-blue-900/30 rounded-full flex items-center justify-center shrink-0">
            <svg
              className="w-5 h-5 text-blue-400 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
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
          </div>
          <div>
            <p className="text-white font-medium text-sm">
              {scan.status === 'queued'
                ? '스캔 대기 중...'
                : 'Semgrep + Claude AI 분석 중...'}
            </p>
            <p className="text-gray-500 text-xs mt-0.5">
              2초마다 자동으로 상태를 업데이트합니다
            </p>
          </div>
        </div>
      )}

      {/* 실패 시 에러 메시지 */}
      {scan.status === 'failed' && scan.errorMessage && (
        <div className="card border-red-900/50 p-6 mb-6">
          <h3 className="text-red-400 font-medium text-sm mb-2">오류 발생</h3>
          <pre className="text-gray-400 text-xs font-mono bg-gray-950 p-3 rounded overflow-x-auto">
            {scan.errorMessage}
          </pre>
        </div>
      )}

      {/* 완료 시 요약 통계 */}
      {scan.status === 'completed' && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-white tabular-nums">
              {scan.findingsCount}
            </div>
            <div className="text-gray-500 text-xs mt-1">전체 탐지</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-red-400 tabular-nums">
              {scan.truePositivesCount}
            </div>
            <div className="text-gray-500 text-xs mt-1">실제 취약점</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-gray-500 tabular-nums">
              {scan.falsePositivesCount}
            </div>
            <div className="text-gray-500 text-xs mt-1">오탐</div>
          </div>
        </div>
      )}

      {/* 취약점 목록 (완료 상태 + 데이터 있을 때) */}
      {isCompleted && (
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            탐지된 취약점
          </h2>
          {vulnsLoading ? (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-3">
                  <div className="h-5 w-14 bg-gray-700 rounded" />
                  <div className="flex-1">
                    <div className="h-3 bg-gray-700 rounded w-3/4 mb-1.5" />
                    <div className="h-2 bg-gray-800 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : vulnerabilities.length > 0 ? (
            <div className="space-y-1">
              {vulnerabilities.map((vuln) => (
                <Link
                  key={vuln.id}
                  href={`/vulnerabilities/${vuln.id}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition-colors"
                >
                  <SeverityBadge severity={vuln.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium">
                      {vuln.vulnerabilityType}
                    </p>
                    <p className="text-gray-500 text-xs truncate">
                      {vuln.filePath}:{vuln.startLine}
                    </p>
                  </div>
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
          ) : (
            <p className="text-gray-600 text-sm text-center py-8">
              탐지된 취약점이 없습니다
            </p>
          )}
        </div>
      )}
    </div>
  );
}
