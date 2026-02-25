# RepoCard

## 위치

`frontend/src/components/repos/repo-card.tsx`

## 역할

연동된 GitHub 저장소 한 건의 요약 정보를 카드 형태로 표시합니다.
저장소 목록 페이지(`/repos`)에서 사용됩니다.

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| repo | `Repository` | O | 저장소 데이터 객체 |

## Repository 타입

```typescript
interface Repository {
  id: string;
  fullName: string;       // "org/repo-name"
  defaultBranch: string;  // "main"
  language: string;       // "Python"
  isActive: boolean;      // 연동 활성 여부
  securityScore: number | null;   // 0~100, null = 미스캔
  lastScannedAt: string | null;   // ISO 8601 날짜 문자열
  isInitialScanDone: boolean;
}
```

## 보안 점수 색상 규칙

| 범위 | 색상 | Tailwind 클래스 |
|------|------|----------------|
| 90 이상 | 초록 | `text-safe-400` |
| 70~89 | 노랑 | `text-warning-400` |
| 70 미만 | 빨강 | `text-danger-400` |
| null | 회색 | `text-gray-500` |

## 특징

- 저장소 이름 클릭 시 `/repos/{id}` 상세 페이지로 이동
- 비활성 저장소는 "비활성" 뱃지 표시, 스캔 버튼 숨김
- `ScanTriggerButton` 컴포넌트를 내장하여 수동 스캔 기능 제공
- `'use client'` 지시어 적용 (ScanTriggerButton이 클라이언트 컴포넌트이기 때문)

## 사용 예시

```tsx
import { RepoCard } from '@/components/repos/repo-card';

<RepoCard repo={repo} />
```

## 의존 컴포넌트

- `ScanTriggerButton` — 수동 스캔 트리거 버튼
- `formatRelativeTime` (lib/utils) — 마지막 스캔 시각 상대 표시
- `cn` (lib/utils) — Tailwind 클래스 병합
