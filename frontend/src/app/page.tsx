import Link from 'next/link';

/**
 * 랜딩 페이지
 * Vulnix 핵심 가치 제안 + GitHub 로그인 CTA
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* 네비게이션 */}
      <nav className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Vulnix 로고 */}
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">V</span>
            </div>
            <span className="text-white font-bold text-xl">Vulnix</span>
          </div>

          <Link href="/login" className="btn-primary">
            GitHub으로 시작하기
          </Link>
        </div>
      </nav>

      {/* 히어로 섹션 */}
      <main className="flex-1 flex items-center justify-center px-6 py-20">
        <div className="max-w-4xl mx-auto text-center">
          {/* 배지 */}
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-900/40 border border-indigo-700/50 rounded-full text-indigo-400 text-sm mb-8">
            <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            AI 기반 보안 취약점 자동 탐지
          </div>

          {/* 메인 타이틀 */}
          <h1 className="text-5xl font-bold text-white mb-6 leading-tight">
            코드 보안을{' '}
            <span className="text-indigo-400">자동화</span>하세요
          </h1>

          {/* 부제목 */}
          <p className="text-xl text-gray-400 mb-12 max-w-2xl mx-auto leading-relaxed">
            Vulnix는 GitHub 저장소의 보안 취약점을 Semgrep과 Claude AI로
            자동 탐지하고, 즉시 패치 PR을 생성합니다.
          </p>

          {/* 핵심 가치 제안 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="card p-6 text-left">
              <div className="w-10 h-10 bg-danger-900/50 border border-danger-700/50 rounded-lg flex items-center justify-center mb-4">
                {/* SQL Injection, XSS, Hardcoded Credentials 탐지 아이콘 */}
                <svg
                  className="w-5 h-5 text-danger-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
                  />
                </svg>
              </div>
              <h3 className="text-white font-semibold mb-2">정밀 취약점 탐지</h3>
              <p className="text-gray-400 text-sm">
                SQL Injection, XSS, 하드코딩된 자격증명 등을 Semgrep + Claude AI
                하이브리드로 오탐 없이 탐지합니다.
              </p>
            </div>

            <div className="card p-6 text-left">
              <div className="w-10 h-10 bg-safe-900/50 border border-safe-700/50 rounded-lg flex items-center justify-center mb-4">
                {/* 패치 PR 자동 생성 아이콘 */}
                <svg
                  className="w-5 h-5 text-safe-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                  />
                </svg>
              </div>
              <h3 className="text-white font-semibold mb-2">자동 패치 PR</h3>
              <p className="text-gray-400 text-sm">
                취약점 탐지 즉시 Claude AI가 최소 변경 원칙으로 패치 코드를
                생성하고 GitHub PR을 자동으로 올립니다.
              </p>
            </div>

            <div className="card p-6 text-left">
              <div className="w-10 h-10 bg-indigo-900/50 border border-indigo-700/50 rounded-lg flex items-center justify-center mb-4">
                {/* 실시간 대시보드 아이콘 */}
                <svg
                  className="w-5 h-5 text-indigo-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"
                  />
                </svg>
              </div>
              <h3 className="text-white font-semibold mb-2">보안 현황 대시보드</h3>
              <p className="text-gray-400 text-sm">
                모든 저장소의 취약점 현황, 심각도 분포, 해결률을 한눈에
                파악할 수 있는 실시간 대시보드를 제공합니다.
              </p>
            </div>
          </div>

          {/* CTA 버튼 */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/login" className="btn-primary px-8 py-3 text-base">
              {/* GitHub 아이콘 */}
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2Z" />
              </svg>
              GitHub으로 무료 시작하기
            </Link>
            <Link href="/dashboard" className="btn-secondary px-8 py-3 text-base">
              데모 보기
            </Link>
          </div>
        </div>
      </main>

      {/* 푸터 */}
      <footer className="border-t border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto text-center text-gray-600 text-sm">
          2026 Vulnix. PoC v0.1
        </div>
      </footer>
    </div>
  );
}
