'use client';

import { useRouter } from 'next/navigation';
import { useTransition } from 'react';

// 지원하는 로케일 목록
const LOCALES = [
  { code: 'ko', label: 'KO' },
  { code: 'en', label: 'EN' },
] as const;

type LocaleCode = (typeof LOCALES)[number]['code'];

interface LanguageSwitcherProps {
  currentLocale: string;
}

/**
 * 언어 전환 컴포넌트
 * locale 쿠키를 변경하고 페이지를 새로고침하여 번역을 적용합니다
 */
export function LanguageSwitcher({ currentLocale }: LanguageSwitcherProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const handleLocaleChange = (locale: LocaleCode) => {
    if (locale === currentLocale) return;

    // locale 쿠키 설정 (1년 만료)
    document.cookie = `locale=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;

    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <div className="flex items-center gap-1">
      {LOCALES.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => handleLocaleChange(code)}
          disabled={isPending}
          className={[
            'px-2 py-1 text-xs font-medium rounded transition-colors',
            currentLocale === code
              ? 'bg-indigo-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-800',
            isPending ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
          ].join(' ')}
          aria-label={`Switch to ${code === 'ko' ? '한국어' : 'English'}`}
          aria-pressed={currentLocale === code}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
