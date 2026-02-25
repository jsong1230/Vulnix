# ScanTriggerButton

## 위치

`frontend/src/components/repos/scan-trigger-button.tsx`

## 역할

수동 스캔 트리거 버튼 컴포넌트입니다.
클릭 시 `POST /api/v1/scans`를 호출하여 스캔 작업을 큐에 등록합니다.

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| repoId | `string` | O | 스캔할 저장소 UUID |
| onSuccess | `(job: ScanJob) => void` | X | 스캔 트리거 성공 후 콜백 |

## ScanJob 타입

```typescript
interface ScanJob {
  id: string;
  repoId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  triggerType: string;
  branch: string | null;
  commitSha: string | null;
  findingsCount: number;
  triggeredAt: string;
  createdAt: string;
}
```

## 상태

| 상태 | 표시 |
|------|------|
| 기본 | 검색 아이콘 + "수동 스캔" 텍스트 |
| 로딩 | 회전 스피너 + "스캔 중..." 텍스트, 버튼 비활성화 |

## 에러 처리 (alert)

| HTTP 상태 | 안내 메시지 |
|-----------|------------|
| 429 | "이미 스캔이 진행 중입니다. 완료 후 다시 시도해 주세요." |
| 400 | "비활성 저장소는 스캔할 수 없습니다." |
| 기타 | `스캔 시작에 실패했습니다: {error.message}` |

## 특징

- `'use client'` 지시어 적용 (상태 관리, 클릭 이벤트 필요)
- `disabled` 속성으로 중복 클릭 방지
- 기존 `btn-primary` CSS 클래스 재사용

## 사용 예시

```tsx
import { ScanTriggerButton } from '@/components/repos/scan-trigger-button';

// 기본 사용
<ScanTriggerButton repoId="uuid-string" />

// 성공 콜백과 함께
<ScanTriggerButton
  repoId="uuid-string"
  onSuccess={(job) => console.log('스캔 시작:', job.id)}
/>
```

## 의존 모듈

- `triggerScan` (lib/repos-api) — 스캔 트리거 API 호출
- `ApiError` (lib/api-client) — HTTP 상태 코드별 에러 분기
