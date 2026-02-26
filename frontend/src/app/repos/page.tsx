'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { getRepos, getGitHubInstallations, registerRepo, type Repository, type GitHubRepo } from '@/lib/repos-api';
import { RepoCard } from '@/components/repos/repo-card';

/**
 * 저장소 목록 페이지
 * 연동된 GitHub 저장소 목록 및 보안 점수 표시
 * GET /api/v1/repos 호출로 실제 데이터 사용
 */
export default function ReposPage() {
  const t = useTranslations();
  const [repos, setRepos] = useState<Repository[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 가져오기 모달 상태
  const [showImport, setShowImport] = useState(false);
  const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([]);
  const [installationId, setInstallationId] = useState<number>(0);
  const [importLoading, setImportLoading] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [registering, setRegistering] = useState<number | null>(null);

  // 저장소 목록 로드
  const loadRepos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getRepos();
      setRepos(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : '저장소 목록을 불러오지 못했습니다.',
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRepos();
  }, [loadRepos]);

  // GitHub 설치된 저장소 목록 가져오기
  const loadGitHubRepos = useCallback(async () => {
    setImportLoading(true);
    setImportError(null);
    try {
      const data = await getGitHubInstallations();
      setInstallationId(data.installationId);
      setGithubRepos(data.repositories);
      setShowImport(true);
    } catch (err) {
      setImportError(
        err instanceof Error ? err.message : 'GitHub 저장소를 불러오지 못했습니다.',
      );
    } finally {
      setImportLoading(false);
    }
  }, []);

  // 저장소 연동 등록
  const handleRegister = useCallback(async (repo: GitHubRepo) => {
    setRegistering(repo.githubRepoId);
    try {
      await registerRepo({
        githubRepoId: repo.githubRepoId,
        fullName: repo.fullName,
        defaultBranch: repo.defaultBranch,
        language: repo.language ?? 'unknown',
        installationId,
      });
      await loadRepos();
      setGithubRepos((prev) =>
        prev.map((r) =>
          r.githubRepoId === repo.githubRepoId ? { ...r, alreadyConnected: true } : r,
        ),
      );
    } catch (err) {
      alert(err instanceof Error ? err.message : '연동에 실패했습니다.');
    } finally {
      setRegistering(null);
    }
  }, [installationId, loadRepos]);

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">{t('repos.title')}</h1>
          <p className="text-gray-400 mt-1 text-sm">
            Vulnix와 연동된 GitHub 저장소 목록
          </p>
        </div>

        {/* 저장소 연동 버튼 */}
        <button
          type="button"
          onClick={() => void loadGitHubRepos()}
          disabled={importLoading}
          className="btn-primary"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          {importLoading ? '불러오는 중...' : '저장소 연동'}
        </button>
      </div>

      {/* 로딩 상태 */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <svg
            className="w-8 h-8 text-indigo-400 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
            aria-label="로딩 중"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="ml-3 text-gray-400">{t('common.loading')}</span>
        </div>
      )}

      {/* 에러 상태 */}
      {!isLoading && error && (
        <div className="card p-6 border-danger-800 bg-danger-950">
          <div className="flex items-center gap-3">
            <svg
              className="w-5 h-5 text-danger-400 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
              />
            </svg>
            <p className="text-danger-300 text-sm">{error}</p>
          </div>
          <button
            onClick={() => void loadRepos()}
            className="mt-4 btn-secondary text-sm"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* 가져오기 에러 */}
      {importError && (
        <div className="card p-4 border-danger-800 bg-danger-950 mb-6">
          <p className="text-danger-300 text-sm">{importError}</p>
        </div>
      )}

      {/* GitHub 저장소 가져오기 모달 */}
      {showImport && (
        <div className="card p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white">GitHub 저장소 선택</h2>
            <button type="button" onClick={() => setShowImport(false)} className="text-gray-500 hover:text-white text-sm">닫기</button>
          </div>
          {githubRepos.length === 0 ? (
            <p className="text-gray-400 text-sm">접근 가능한 저장소가 없습니다.</p>
          ) : (
            <div className="space-y-2">
              {githubRepos.map((repo) => (
                <div key={repo.githubRepoId} className="flex items-center justify-between p-3 rounded-lg bg-gray-800">
                  <div>
                    <p className="text-white text-sm font-medium">{repo.fullName}</p>
                    <p className="text-gray-400 text-xs">{repo.language ?? 'unknown'} · {repo.defaultBranch}</p>
                  </div>
                  {repo.alreadyConnected ? (
                    <span className="text-xs text-green-400 font-medium">연동됨</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void handleRegister(repo)}
                      disabled={registering === repo.githubRepoId}
                      className="btn-primary text-xs py-1.5 px-3"
                    >
                      {registering === repo.githubRepoId ? '연동 중...' : '연동'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 저장소 목록 */}
      {!isLoading && !error && (
        <>
          {repos.length === 0 ? (
            /* 빈 상태 — GitHub App 설치 유도 */
            <div className="card p-16 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4">
                <svg
                  className="w-8 h-8 text-gray-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 16.5"
                  />
                </svg>
              </div>
              <h3 className="text-white font-medium mb-2">
                {t('repos.noRepos')}
              </h3>
              <p className="text-gray-500 text-sm mb-6 max-w-sm">
                GitHub App을 설치하여 저장소를 연동하면 자동으로 보안 스캔이
                시작됩니다.
              </p>
              <a
                href={`https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_SLUG ?? 'vulnix'}/installations/new`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                GitHub App 설치하기
              </a>
            </div>
          ) : (
            /* 저장소 카드 목록 */
            <div className="grid grid-cols-1 gap-4">
              {repos.map((repo) => (
                <RepoCard key={repo.id} repo={repo} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
