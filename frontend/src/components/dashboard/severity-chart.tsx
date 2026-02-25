/**
 * 심각도 분포 막대 차트 (순수 SVG, 외부 의존성 없음)
 */

interface SeverityDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface SeverityChartProps {
  distribution: SeverityDistribution;
}

const SEVERITY_CONFIG = [
  { key: 'critical' as const, label: 'Critical', color: '#ef4444', bg: 'bg-red-500' },
  { key: 'high'     as const, label: 'High',     color: '#f97316', bg: 'bg-orange-500' },
  { key: 'medium'   as const, label: 'Medium',   color: '#eab308', bg: 'bg-yellow-500' },
  { key: 'low'      as const, label: 'Low',      color: '#3b82f6', bg: 'bg-blue-500' },
];

export function SeverityChart({ distribution }: SeverityChartProps) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-gray-600 text-sm">
        취약점이 없습니다
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {SEVERITY_CONFIG.map(({ key, label, bg }) => {
        const count = distribution[key];
        const pct = total > 0 ? (count / total) * 100 : 0;

        return (
          <div key={key} className="flex items-center gap-3">
            {/* 라벨 */}
            <span className="text-xs text-gray-400 w-14 shrink-0">{label}</span>

            {/* 프로그레스 바 */}
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${bg}`}
                style={{ width: `${pct}%` }}
              />
            </div>

            {/* 카운트 */}
            <span className="text-xs text-gray-300 w-6 text-right shrink-0">{count}</span>
          </div>
        );
      })}

      {/* 합계 */}
      <div className="pt-1 border-t border-gray-800 flex items-center justify-between text-xs text-gray-500">
        <span>합계</span>
        <span className="text-gray-300">{total}</span>
      </div>
    </div>
  );
}
