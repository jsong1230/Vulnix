# PatchDiffViewer 컴포넌트

**파일**: `frontend/src/components/vulnerability/patch-diff-viewer.tsx`
**버전**: v1.0 (F-04)

## 개요

unified diff 형식의 문자열을 파싱하여 줄별로 색상을 적용해 렌더링하는 컴포넌트.
설계서 ADR-F04-004: `+`/`-` 접두사 기반 줄별 색상 처리 방식 사용.

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| diff | string | Y | unified diff 형식 문자열 |

## 사용 예시

```tsx
<PatchDiffViewer diff={vuln.patchPr.patchDiff} />
```

## 색상 규칙

| 줄 패턴 | 색상 | 배경 |
|---------|------|------|
| `+` 시작 (추가, `+++` 제외) | `text-green-300` | `bg-green-900/30` |
| `-` 시작 (삭제, `---` 제외) | `text-red-300` | `bg-red-900/30` |
| `@@` 시작 (헝크 헤더) | `text-blue-400` | 없음 |
| `+++` / `---` (파일명 줄) | `text-gray-500` | 없음 |
| 나머지 (문맥 줄) | `text-gray-400` | 없음 |

## 스타일

- 배경: `bg-gray-950`
- 테두리: `border border-gray-800`
- 폰트: `font-mono text-sm`
- 각 줄은 `px-4 py-0.5 whitespace-pre`
- 가로 스크롤 지원 (`overflow-x-auto`)
