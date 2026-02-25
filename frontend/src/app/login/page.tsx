import { getTranslations } from 'next-intl/server';
import { getGitHubOAuthUrl } from '@/lib/auth';

/**
 * 로그인 페이지
 * GitHub OAuth 흐름 진입점
 */
export default async function LoginPage() {
  const githubOAuthUrl = getGitHubOAuthUrl();
  const t = await getTranslations('login');
  const tNav = await getTranslations('nav');

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* 로고 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">V</span>
            </div>
            <span className="text-white font-bold text-2xl">Vulnix</span>
          </div>
          <p className="text-gray-400 text-sm">{t('subtitle')}</p>
        </div>

        {/* 로그인 카드 */}
        <div className="card p-8">
          <h1 className="text-lg font-semibold text-white mb-2 text-center">
            {t('title')}
          </h1>
          <p className="text-gray-500 text-xs text-center mb-6">
            {t('description')}
          </p>

          {/* GitHub OAuth 로그인 버튼 */}
          <a
            href={githubOAuthUrl}
            className="btn-primary w-full py-3 text-base"
          >
            {/* GitHub 아이콘 */}
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2Z" />
            </svg>
            {t('loginWithGitHub')}
          </a>

          {/* 안내 문구 */}
          <p className="text-gray-500 text-xs text-center mt-4">
            {/* 저장소 읽기 및 PR 생성 권한 요청 안내 */}
            {t('subtitle')}
          </p>
        </div>

        {/* 하단 링크 */}
        <p className="text-center text-gray-600 text-sm mt-6">
          <a href="/" className="hover:text-gray-400 transition-colors">
            {tNav('dashboard')}
          </a>
        </p>
      </div>
    </div>
  );
}
