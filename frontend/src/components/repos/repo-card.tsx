'use client';

import Link from 'next/link';
import { type Repository } from '@/lib/repos-api';
import { ScanTriggerButton } from './scan-trigger-button';
import { formatRelativeTime, cn } from '@/lib/utils';

interface RepoCardProps {
  repo: Repository;
}

/**
 * 보안 점수(0~100)를 색상 클래스로 변환
 * 90+: 초록(safe), 70~89: 노랑(warning), 70 미만: 빨강(danger)
 */
function getScoreColorClass(score: number | null): string {
  if (score === null) return 'text-gray-500';
  if (score >= 90) return 'text-safe-400';
  if (score >= 70) return 'text-warning-400';
  return 'text-danger-400';
}

/**
 * 저장소 카드 컴포넌트
 * 저장소명, 언어, 보안 점수, 마지막 스캔 시각, 스캔 트리거 버튼 표시
 */
export function RepoCard({ repo }: RepoCardProps) {
  const scoreColorClass = getScoreColorClass(repo.securityScore);

  return (
    <div className="card p-5 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-4">
        {/* 왼쪽: 저장소 정보 */}
        <div className="flex-1 min-w-0">
          <Link
            href={`/repos/${repo.id}`}
            className="block group"
          >
            <h3 className="text-white font-medium group-hover:text-indigo-300 transition-colors truncate">
              {repo.fullName}
            </h3>
          </Link>

          <div className="flex items-center gap-3 mt-1">
            {/* 언어 */}
            {repo.language && (
              <span className="text-gray-500 text-sm">{repo.language}</span>
            )}

            {/* 기본 브랜치 */}
            <span className="text-gray-600 text-xs">{repo.defaultBranch}</span>

            {/* 비활성 뱃지 */}
            {!repo.isActive && (
              <span className="text-xs px-1.5 py-0.5 bg-gray-800 text-gray-500 rounded border border-gray-700">
                비활성
              </span>
            )}
          </div>

          {/* 마지막 스캔 시각 */}
          <p className="text-gray-600 text-xs mt-2">
            {repo.lastScannedAt
              ? `마지막 스캔: ${formatRelativeTime(repo.lastScannedAt)}`
              : '아직 스캔하지 않았습니다'}
          </p>
        </div>

        {/* 오른쪽: 보안 점수 + 스캔 버튼 */}
        <div className="flex flex-col items-end gap-3 shrink-0">
          {/* 보안 점수 */}
          <div className="text-right">
            <div
              className={cn('text-2xl font-bold tabular-nums', scoreColorClass)}
            >
              {repo.securityScore !== null
                ? Math.round(repo.securityScore)
                : '—'}
            </div>
            <div className="text-gray-600 text-xs">보안 점수</div>
          </div>

          {/* 수동 스캔 버튼 (활성 저장소만) */}
          {repo.isActive && (
            <ScanTriggerButton repoId={repo.id} />
          )}
        </div>
      </div>
    </div>
  );
}
