'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { triggerScan, type ScanJob } from '@/lib/repos-api';
import { ApiError } from '@/lib/api-client';

interface ScanTriggerButtonProps {
  repoId: string;
  /** 스캔 성공 후 콜백 (선택) */
  onSuccess?: (job: ScanJob) => void;
}

/**
 * 수동 스캔 트리거 버튼 컴포넌트
 * 클릭 시 POST /api/v1/scans 호출, 로딩 스피너 표시
 * 성공 시 /scans/{job.id} 페이지로 이동하여 실시간 진행 상태 확인
 */
export function ScanTriggerButton({ repoId, onSuccess }: ScanTriggerButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const router = useRouter();

  const handleClick = async () => {
    if (isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const job = await triggerScan(repoId);
      onSuccess?.(job);
      // alert 대신 스캔 상세 페이지로 이동하여 진행 상태 실시간 확인
      router.push(`/scans/${job.id}`);
    } catch (error) {
      // 이미 스캔이 진행 중인 경우 (429)
      if (error instanceof ApiError && error.statusCode === 429) {
        setErrorMessage('이미 스캔이 진행 중입니다. 완료 후 다시 시도해 주세요.');
      } else if (error instanceof ApiError && error.statusCode === 400) {
        setErrorMessage('비활성 저장소는 스캔할 수 없습니다.');
      } else if (error instanceof Error) {
        setErrorMessage(`스캔 시작에 실패했습니다: ${error.message}`);
      } else {
        setErrorMessage('스캔 시작 중 알 수 없는 오류가 발생했습니다.');
      }
      setIsLoading(false);
    }
    // 성공 시 setIsLoading(false) 호출 불필요 — 페이지 이동으로 컴포넌트 언마운트
  };

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="btn-primary disabled:opacity-60 disabled:cursor-not-allowed"
        aria-label="수동 스캔 시작"
      >
        {isLoading ? (
          /* 로딩 스피너 */
          <>
            <svg
              className="w-4 h-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
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
            스캔 중...
          </>
        ) : (
          /* 기본 상태 — 검색 아이콘 */
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
              />
            </svg>
            수동 스캔
          </>
        )}
      </button>
      {/* 에러 메시지 인라인 표시 (alert 대체) */}
      {errorMessage && (
        <p className="text-red-400 text-xs mt-2">{errorMessage}</p>
      )}
    </div>
  );
}
