import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Tailwind CSS 클래스 병합 유틸리티
 * clsx + tailwind-merge 조합으로 조건부 클래스 적용 및 충돌 해결
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * 날짜를 한국어 상대 시간으로 표시
 * 예: "3분 전", "2시간 전", "어제"
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return '방금 전';
  if (diffMinutes < 60) return `${diffMinutes}분 전`;
  if (diffHours < 24) return `${diffHours}시간 전`;
  if (diffDays === 1) return '어제';
  if (diffDays < 7) return `${diffDays}일 전`;

  // 7일 이상은 날짜 표시
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * 스캔 소요 시간을 읽기 쉬운 형식으로 변환
 * 예: 65 -> "1분 5초"
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = seconds % 60;
  if (remainSeconds === 0) return `${minutes}분`;
  return `${minutes}분 ${remainSeconds}초`;
}

/**
 * 보안 점수(0~100)를 등급으로 변환
 * A(90+), B(75+), C(60+), D(40+), F(미만)
 */
export function scoreToGrade(score: number): {
  grade: string;
  label: string;
  color: string;
} {
  if (score >= 90) return { grade: 'A', label: '매우 안전', color: 'text-safe-400' };
  if (score >= 75) return { grade: 'B', label: '안전', color: 'text-safe-500' };
  if (score >= 60) return { grade: 'C', label: '주의 필요', color: 'text-warning-400' };
  if (score >= 40) return { grade: 'D', label: '위험', color: 'text-orange-400' };
  return { grade: 'F', label: '매우 위험', color: 'text-danger-400' };
}

/**
 * 취약점 심각도를 한국어로 변환
 */
export function translateSeverity(
  severity: 'critical' | 'high' | 'medium' | 'low',
): string {
  const map = {
    critical: '치명적',
    high: '높음',
    medium: '보통',
    low: '낮음',
  };
  return map[severity];
}

/**
 * 스캔 상태를 한국어로 변환
 */
export function translateScanStatus(
  status: 'queued' | 'running' | 'completed' | 'failed',
): string {
  const map = {
    queued: '대기 중',
    running: '스캔 중',
    completed: '완료',
    failed: '실패',
  };
  return map[status];
}

/**
 * 취약점 상태를 한국어로 변환
 */
export function translateVulnStatus(
  status: 'open' | 'patched' | 'ignored' | 'false_positive',
): string {
  const map = {
    open: '미해결',
    patched: '패치 완료',
    ignored: '무시됨',
    false_positive: '오탐',
  };
  return map[status];
}
