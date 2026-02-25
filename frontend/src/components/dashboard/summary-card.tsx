import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

type SummaryCardVariant = 'default' | 'danger' | 'warning' | 'safe';

interface SummaryCardProps {
  title: string;
  value: string | number;
  description?: string;
  variant?: SummaryCardVariant;
}

/**
 * 대시보드 요약 통계 카드 컴포넌트
 * 취약점 수, 해결률 등 핵심 지표를 표시
 */
export function SummaryCard({
  title,
  value,
  description,
  variant = 'default',
}: SummaryCardProps) {
  // variant별 색상 설정
  const valueColorMap: Record<SummaryCardVariant, string> = {
    default: 'text-white',
    danger: 'text-danger-400',
    warning: 'text-warning-400',
    safe: 'text-safe-400',
  };

  const borderColorMap: Record<SummaryCardVariant, string> = {
    default: 'border-gray-800',
    danger: 'border-danger-900/50',
    warning: 'border-warning-900/50',
    safe: 'border-safe-900/50',
  };

  return (
    <div
      className={twMerge(
        clsx(
          'card p-5',
          borderColorMap[variant],
        ),
      )}
    >
      {/* 카드 제목 */}
      <p className="text-gray-400 text-sm font-medium">{title}</p>

      {/* 핵심 수치 */}
      <p
        className={twMerge(
          clsx(
            'text-3xl font-bold mt-2 mb-1 tabular-nums',
            valueColorMap[variant],
          ),
        )}
      >
        {value}
      </p>

      {/* 부가 설명 */}
      {description && (
        <p className="text-gray-600 text-xs">{description}</p>
      )}
    </div>
  );
}
