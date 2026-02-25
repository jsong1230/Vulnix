import Link from 'next/link';
import type { RecentScanItem, ScanStatus } from '@/lib/scan-api';

interface RecentScansProps {
  scans: RecentScanItem[];
}

/** 스캔 상태별 배지 스타일 매핑 */
const statusStyleMap: Record<ScanStatus, { label: string; textColor: string; bgColor: string }> = {
  queued: {
    label: '대기 중',
    textColor: 'text-yellow-400',
    bgColor: 'bg-yellow-400/10',
  },
  running: {
    label: '스캔 중',
    textColor: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
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

/**
 * 대시보드 — 최근 스캔 목록 컴포넌트
 * 상태 배지 + 저장소명 + 결과 수 표시
 */
export function RecentScans({ scans }: RecentScansProps) {
  if (scans.length === 0) {
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
            d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
          />
        </svg>
        <p className="text-sm">스캔 기록이 없습니다</p>
        <p className="text-xs mt-1">GitHub Webhook이 연결되면 자동으로 스캔됩니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {scans.map((scan) => {
        const statusStyle = statusStyleMap[scan.status];
        return (
          <Link
            key={scan.id}
            href={`/scans/${scan.id}`}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800 transition-colors"
          >
            {/* 상태 배지 */}
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${statusStyle.textColor} ${statusStyle.bgColor}`}
            >
              {scan.status === 'running' && (
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              )}
              {statusStyle.label}
            </span>
            {/* 저장소명 */}
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">
                {scan.repoFullName}
              </p>
              {scan.status === 'completed' && (
                <p className="text-gray-500 text-xs">
                  탐지 {scan.findingsCount}건 / 실제 {scan.truePositivesCount}건
                </p>
              )}
            </div>
            {/* 생성 시각 */}
            <time
              dateTime={scan.createdAt}
              className="text-gray-600 text-xs shrink-0"
            >
              {new Date(scan.createdAt).toLocaleDateString('ko-KR', {
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
        );
      })}
    </div>
  );
}
