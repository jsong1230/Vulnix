# StatusActions 컴포넌트

**파일**: `frontend/src/components/vulnerability/status-actions.tsx`
**버전**: v1.0 (F-04)

## 개요

취약점 처리 상태를 변경하는 액션 버튼 그룹 컴포넌트.
현재 상태에 따라 가능한 액션 버튼만 노출한다.

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| vulnId | string | Y | 취약점 ID |
| currentStatus | VulnerabilityStatus | Y | 현재 취약점 처리 상태 |
| onStatusChange | (newStatus: VulnerabilityStatus) => void | Y | 상태 변경 요청 핸들러 |
| isPending | boolean | N | 뮤테이션 진행 중 여부 (기본값: false) |

## 타입

```typescript
type VulnerabilityStatus = 'open' | 'patched' | 'ignored' | 'false_positive';
```

## 상태별 가능한 액션

| 현재 상태 | 표시되는 버튼 |
|-----------|--------------|
| `open` | 오탐으로 표시, 무시, 패치 완료 |
| `false_positive` | 다시 열기 |
| `ignored` | 다시 열기 |
| `patched` | 다시 열기 |

## 동작

- 버튼 클릭 시 `window.confirm()`으로 확인 다이얼로그 표시
- 확인 후 `onStatusChange(newStatus)` 콜백 호출
- `isPending=true`이면 모든 버튼 disabled + "처리 중..." 텍스트 표시

## 사용 예시

```tsx
const { mutate: updateStatus, isPending } = useUpdateVulnerabilityStatus();

<StatusActions
  vulnId={vuln.id}
  currentStatus={vuln.status}
  onStatusChange={(newStatus) => updateStatus({ vulnId: vuln.id, status: newStatus })}
  isPending={isPending}
/>
```
