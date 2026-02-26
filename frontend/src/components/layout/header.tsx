import { getLocale, getTranslations } from 'next-intl/server';
import { LanguageSwitcher } from './language-switcher';
import { UserInfo } from './user-info';

/**
 * 상단 헤더 컴포넌트
 * 현재 페이지 컨텍스트 + 사용자 프로필 표시 + 언어 전환
 * TODO: 사용자 인증 상태 연동 (GET /api/v1/auth/me)
 */
export async function Header() {
  const locale = await getLocale();
  const t = await getTranslations('nav');

  return (
    <header className="h-14 border-b border-gray-800 flex items-center justify-between px-6 shrink-0">
      {/* 왼쪽: 알림 또는 검색 (추후 확장) */}
      <div className="flex items-center gap-3">
        {/* TODO: 검색 기능 추가 */}
      </div>

      {/* 오른쪽: 언어 전환 + 사용자 프로필 */}
      <div className="flex items-center gap-4">
        {/* 언어 전환 버튼 */}
        <LanguageSwitcher currentLocale={locale} />

        {/* 로그인 상태: /api/v1/auth/me 호출로 확인 */}
        <UserInfo loginLabel={t('login')} />
      </div>
    </header>
  );
}
