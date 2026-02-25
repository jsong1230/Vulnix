import Link from 'next/link';
import { SeverityBadge } from '@/components/vulnerability/severity-badge';
import type { VulnerabilitySummary } from '@/lib/scan-api';

interface RecentVulnerabilitiesProps {
  vulnerabilities: VulnerabilitySummary[];
}

/**
 * 대시보드 — 최근 취약점 목록 컴포넌트
 * 심각도 배지 + 파일 경로 + 탐지 시각 표시
 */
export function RecentVulnerabilities({ vulnerabilities }: RecentVulnerabilitiesProps) {
  if (vulnerabilities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-600">
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
        <p className="text-sm">탐지된 취약점이 없습니다</p>
        <p className="text-xs mt-1">저장소를 연동하고 첫 스캔을 실행해보세요</p>
      </div>
    );
  }

  return (
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
          {/* 탐지 시각 */}
          <time
            dateTime={vuln.detectedAt}
            className="text-gray-600 text-xs shrink-0"
          >
            {new Date(vuln.detectedAt).toLocaleDateString('ko-KR', {
              month: 'short',
              day: 'numeric',
            })}
          </time>
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
  );
}
