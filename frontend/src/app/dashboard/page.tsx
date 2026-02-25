'use client';

import { SummaryCard } from '@/components/dashboard/summary-card';
import { RecentVulnerabilities } from '@/components/dashboard/recent-vulnerabilities';
import { RecentScans } from '@/components/dashboard/recent-scans';
import { useDashboardSummary } from '@/lib/hooks/use-dashboard';
import { useVulnerabilityList } from '@/lib/hooks/use-vulnerabilities';

/**
 * 대시보드 페이지
 * 전체 보안 현황 요약 통계를 표시
 * React Query를 통해 /api/v1/dashboard/summary, /api/v1/vulnerabilities 연동
 */
export default function DashboardPage() {
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
  } = useDashboardSummary();

  // 최근 오픈 취약점 5건 (High 이상 우선)
  const {
    data: vulnsData,
    isLoading: vulnsLoading,
    isError: vulnsError,
  } = useVulnerabilityList({ status: 'open', page: 1, perPage: 5 });

  const isLoading = summaryLoading || vulnsLoading;
  const isError = summaryError || vulnsError;

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">대시보드</h1>
        <p className="text-gray-400 mt-1 text-sm">
          연동된 모든 저장소의 보안 취약점 현황
        </p>
      </div>

      {/* 에러 상태 */}
      {isError && !isLoading && (
        <div className="card border-red-900/50 p-4 mb-6 flex items-center justify-between">
          <p className="text-red-400 text-sm">데이터를 불러오지 못했습니다.</p>
          <button
            type="button"
            onClick={() => void refetchSummary()}
            className="btn-secondary text-xs"
          >
            재시도
          </button>
        </div>
      )}

      {/* 요약 통계 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {isLoading ? (
          /* 로딩 스켈레톤 */
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-5 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-24 mb-3" />
              <div className="h-8 bg-gray-700 rounded w-16 mb-2" />
              <div className="h-2 bg-gray-800 rounded w-32" />
            </div>
          ))
        ) : (
          <>
            <SummaryCard
              title="전체 취약점"
              value={summary?.totalVulnerabilities ?? 0}
              description="탐지된 총 취약점 수"
              variant="default"
            />
            <SummaryCard
              title="미해결 취약점"
              value={summary?.statusDistribution.open ?? 0}
              description="아직 패치되지 않은 항목"
              variant="danger"
            />
            <SummaryCard
              title="해결률"
              value={`${Math.round(summary?.resolutionRate ?? 0)}%`}
              description="패치 완료 / 전체"
              variant="safe"
            />
            <SummaryCard
              title="연동 저장소"
              value={summary?.repoCount ?? 0}
              description="스캔 활성화된 저장소"
              variant="default"
            />
          </>
        )}
      </div>

      {/* 최근 스캔 섹션 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 최근 취약점 목록 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            최근 탐지된 취약점
          </h2>
          {vulnsLoading ? (
            /* 취약점 목록 로딩 스켈레톤 */
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
          ) : (
            <RecentVulnerabilities vulnerabilities={vulnsData?.items ?? []} />
          )}
        </div>

        {/* 최근 스캔 히스토리 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            최근 스캔 기록
          </h2>
          {summaryLoading ? (
            /* 스캔 목록 로딩 스켈레톤 */
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-3">
                  <div className="h-5 w-12 bg-gray-700 rounded-full" />
                  <div className="flex-1">
                    <div className="h-3 bg-gray-700 rounded w-2/3 mb-1.5" />
                    <div className="h-2 bg-gray-800 rounded w-1/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <RecentScans scans={summary?.recentScans ?? []} />
          )}
        </div>
      </div>
    </div>
  );
}
