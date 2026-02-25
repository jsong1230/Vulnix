# CodeViewer 컴포넌트

**파일**: `frontend/src/components/vulnerability/code-viewer.tsx`
**버전**: v1.0 (F-04)

## 개요

취약한 코드 스니펫을 줄 번호와 함께 표시하는 읽기 전용 뷰어 컴포넌트.
취약 라인 범위를 노란 배경으로 하이라이트한다.

설계서 ADR-F04-004: Monaco Editor 없이 `<pre>` + CSS 줄 번호 방식 사용 (번들 크기 최소화).

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| codeSnippet | string | Y | 표시할 코드 문자열 (줄바꿈 `\n` 기준으로 분리) |
| startLine | number | Y | 코드 스니펫 첫 번째 줄의 실제 파일 내 줄 번호 |
| highlightStart | number | Y | 취약 라인 하이라이트 시작 줄 번호 (파일 기준) |
| highlightEnd | number | Y | 취약 라인 하이라이트 끝 줄 번호 (파일 기준) |

## 사용 예시

```tsx
<CodeViewer
  codeSnippet={vuln.codeSnippet}
  startLine={vuln.startLine}
  highlightStart={vuln.startLine}
  highlightEnd={vuln.endLine}
/>
```

## 동작

- `codeSnippet`을 `\n`으로 분리하여 줄 단위 렌더링
- 각 줄에 `startLine + index` 줄 번호 표시
- `highlightStart ~ highlightEnd` 범위의 줄은 `bg-yellow-900/20` 배경 + `text-yellow-100` 텍스트 적용
- 나머지 줄은 `text-gray-300`
- 가로 스크롤 지원 (`overflow-x-auto`)
- 줄 번호 영역은 사용자 선택 불가 (`select-none`)

## 스타일

- 배경: `bg-gray-950` (코드 에디터 느낌의 어두운 배경)
- 테두리: `border border-gray-800`
- 폰트: `font-mono text-sm`
- 하이라이트 줄: `bg-yellow-900/20` (반투명 노란 배경)
