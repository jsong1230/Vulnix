# LanguageSwitcher 컴포넌트

## 개요
한국어/영어 전환을 위한 클라이언트 컴포넌트. `locale` 쿠키를 설정하고 `router.refresh()`로 페이지를 재렌더링하여 번역을 즉시 적용합니다.

## 위치
`frontend/src/components/layout/language-switcher.tsx`

## Props

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `currentLocale` | `string` | 필수 | 현재 활성 로케일 코드 (`'ko'` 또는 `'en'`) |

## 사용 예시

```tsx
// 서버 컴포넌트에서 locale을 읽어 전달
import { getLocale } from 'next-intl/server';
import { LanguageSwitcher } from './language-switcher';

export async function Header() {
  const locale = await getLocale();
  return (
    <header>
      <LanguageSwitcher currentLocale={locale} />
    </header>
  );
}
```

## 동작 방식

1. `ko` / `en` 두 버튼을 렌더링합니다.
2. 현재 로케일과 일치하는 버튼은 `bg-indigo-600 text-white`로 강조됩니다.
3. 버튼 클릭 시:
   - `document.cookie`로 `locale` 쿠키를 1년 만료로 설정합니다.
   - `useTransition`을 활용해 `router.refresh()`를 호출합니다.
   - 서버 컴포넌트가 새 로케일로 재렌더링되며 번역이 적용됩니다.
4. 전환 중에는 버튼이 비활성화(`disabled`)되어 중복 클릭을 방지합니다.

## 스타일
- 활성 로케일 버튼: `bg-indigo-600 text-white`
- 비활성 버튼: `text-gray-400 hover:text-white hover:bg-gray-800`
- 전환 중: `opacity-50 cursor-not-allowed`

## 접근성
- 각 버튼에 `aria-label`로 언어 전체 명칭 제공
- `aria-pressed`로 현재 선택 상태 표시

## 의존성
- `next-intl` — 번역 인프라
- `next/navigation` — `useRouter`
- React `useTransition` — 비동기 상태 전환 처리
