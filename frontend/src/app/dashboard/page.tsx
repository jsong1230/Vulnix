'use client';

import { useTranslations } from 'next-intl';
import { SummaryCard } from '@/components/dashboard/summary-card';
import { RecentVulnerabilities } from '@/components/dashboard/recent-vulnerabilities';
import { RecentScans } from '@/components/dashboard/recent-scans';
import { SeverityChart } from '@/components/dashboard/severity-chart';
import { useDashboardSummary } from '@/lib/hooks/use-dashboard';
import { useVulnerabilityList } from '@/lib/hooks/use-vulnerabilities';

/**
 * 대시보드 페이지
 * 전체 보안 현황 요약 통계를 표시
 * React Query를 통해 /api/v1/dashboard/summary, /api/v1/vulnerabilities 연동
 */
export default function DashboardPage() {
  const t = useTranslations();
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
        <h1 className="text-2xl font-bold text-white">{t('nav.dashboard')}</h1>
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
              title={t('dashboard.totalVulnerabilities')}
              value={summary?.totalVulnerabilities ?? 0}
              description="탐지된 총 취약점 수"
              variant="default"
            />
            <SummaryCard
              title={t('dashboard.openVulnerabilities')}
              value={summary?.statusDistribution.open ?? 0}
              description="아직 패치되지 않은 항목"
              variant="danger"
            />
            <SummaryCard
              title={t('dashboard.securityScore')}
              value={`${Math.round(summary?.resolutionRate ?? 0)}%`}
              description="패치 완료 / 전체"
              variant="safe"
            />
            <SummaryCard
              title={t('repos.title')}
              value={summary?.repoCount ?? 0}
              description="스캔 활성화된 저장소"
              variant="default"
            />
          </>
        )}
      </div>

      {/* 심각도 분포 + 최근 스캔 섹션 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* 심각도 분포 차트 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">심각도 분포</h2>
          {summaryLoading ? (
            <div className="space-y-3 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-3 w-14 bg-gray-700 rounded" />
                  <div className="flex-1 h-2 bg-gray-700 rounded-full" />
                  <div className="h-3 w-6 bg-gray-700 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <SeverityChart
              distribution={
                summary?.severityDistribution ?? { critical: 0, high: 0, medium: 0, low: 0 }
              }
            />
          )}
        </div>

        {/* 처리 상태 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">처리 상태</h2>
          {summaryLoading ? (
            <div className="space-y-3 animate-pulse">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-3 w-16 bg-gray-700 rounded" />
                  <div className="flex-1 h-2 bg-gray-700 rounded-full" />
                  <div className="h-3 w-6 bg-gray-700 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { label: '미해결', key: 'open' as const, color: 'bg-red-500' },
                { label: '패치됨', key: 'patched' as const, color: 'bg-green-500' },
                { label: '무시됨', key: 'ignored' as const, color: 'bg-gray-500' },
                { label: '오탐', key: 'false_positive' as const, color: 'bg-yellow-500' },
              ].map(({ label, key, color }) => {
                const total = Object.values(summary?.statusDistribution ?? {}).reduce(
                  (a: number, b) => a + (b as number),
                  0,
                );
                const count = summary?.statusDistribution[key] ?? 0;
                const pct = total > 0 ? (count / total) * 100 : 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-14 shrink-0">{label}</span>
                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${color}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-300 w-6 text-right shrink-0">{count}</span>
                  </div>
                );
              })}
              <div className="pt-1 border-t border-gray-800 flex items-center justify-between text-xs text-gray-500">
                <span>해결률</span>
                <span className="text-gray-300">{Math.round(summary?.resolutionRate ?? 0)}%</span>
              </div>
            </div>
          )}
        </div>

        {/* 최근 스캔 히스토리 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            {t('dashboard.recentScans')}
          </h2>
          {summaryLoading ? (
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

      {/* 최근 취약점 */}
      <div className="grid grid-cols-1 gap-6">
        {/* 최근 취약점 목록 */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-white mb-4">
            {t('dashboard.recentVulnerabilities')}
          </h2>
          {vulnsLoading ? (
            /* 취약점 목록 로딩 스켈레톤 */
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 5 }).map((_, i) => (
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
      </div>
    </div>
  );
}
