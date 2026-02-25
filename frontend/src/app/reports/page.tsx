'use client';

import { useState } from 'react';
import { useReports, useGenerateReport, useDownloadReport } from '@/lib/hooks/use-reports';
import type { ReportType } from '@/lib/reports-api';

// ─── 아이콘 ────────────────────────────────────────────────────────────────────

const DocumentIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
  </svg>
);

const DownloadIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

// ─── 리포트 유형 배지 ─────────────────────────────────────────────────────────

const REPORT_TYPE_STYLES: Record<ReportType, string> = {
  CSAP: 'bg-blue-900/40 text-blue-400 border-blue-800/50',
  ISO27001: 'bg-amber-900/40 text-amber-400 border-amber-800/50',
  ISMS: 'bg-teal-900/40 text-teal-400 border-teal-800/50',
};

function ReportTypeBadge({ type }: { type: ReportType }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${REPORT_TYPE_STYLES[type]}`}
    >
      {type === 'ISO27001' ? 'ISO 27001' : type}
    </span>
  );
}

// ─── 상태 배지 ────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles = {
    pending: 'bg-yellow-900/40 text-yellow-400',
    completed: 'bg-emerald-900/40 text-emerald-400',
    failed: 'bg-red-900/40 text-red-400',
  };
  const labels = {
    pending: '생성 중',
    completed: '완료',
    failed: '실패',
  };
  const key = status as keyof typeof styles;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[key] ?? 'bg-gray-800 text-gray-400'}`}>
      {labels[key] ?? status}
    </span>
  );
}

// ─── 날짜 포맷 ────────────────────────────────────────────────────────────────

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// ─── 생성 폼 ──────────────────────────────────────────────────────────────────

interface GenerateFormState {
  reportType: ReportType;
  startDate: string;
  endDate: string;
  teamName: string;
}

function GenerateReportForm() {
  const today = new Date().toISOString().slice(0, 10);
  const oneMonthAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);

  const [form, setForm] = useState<GenerateFormState>({
    reportType: 'CSAP',
    startDate: oneMonthAgo,
    endDate: today,
    teamName: '',
  });

  const generateMutation = useGenerateReport();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    generateMutation.mutate({
      reportType: form.reportType,
      startDate: form.startDate,
      endDate: form.endDate,
      teamName: form.teamName || undefined,
    });
  };

  return (
    <div className="card p-6 mb-6">
      <h2 className="text-base font-semibold text-white mb-4">리포트 생성</h2>
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {/* 리포트 유형 */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              리포트 유형
            </label>
            <select
              value={form.reportType}
              onChange={(e) =>
                setForm((f) => ({ ...f, reportType: e.target.value as ReportType }))
              }
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="CSAP">CSAP</option>
              <option value="ISO27001">ISO 27001</option>
              <option value="ISMS">ISMS</option>
            </select>
          </div>

          {/* 시작일 */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              시작일
            </label>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((f) => ({ ...f, startDate: e.target.value }))}
              required
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 [color-scheme:dark]"
            />
          </div>

          {/* 종료일 */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              종료일
            </label>
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((f) => ({ ...f, endDate: e.target.value }))}
              required
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 [color-scheme:dark]"
            />
          </div>

          {/* 팀 */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              팀 (선택)
            </label>
            <input
              type="text"
              value={form.teamName}
              onChange={(e) => setForm((f) => ({ ...f, teamName: e.target.value }))}
              placeholder="예: 보안팀"
              className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* 에러 */}
        {generateMutation.isError && (
          <p className="text-red-400 text-xs mb-3">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : '리포트 생성에 실패했습니다.'}
          </p>
        )}

        {/* 성공 메시지 */}
        {generateMutation.isSuccess && (
          <p className="text-emerald-400 text-xs mb-3">
            리포트 생성을 요청했습니다. 완료되면 목록에 표시됩니다.
          </p>
        )}

        <button
          type="submit"
          disabled={generateMutation.isPending}
          className="btn-primary"
        >
          {generateMutation.isPending ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              생성 중...
            </>
          ) : (
            <>
              <DocumentIcon />
              리포트 생성
            </>
          )}
        </button>
      </form>
    </div>
  );
}

// ─── 페이지 ───────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { data: reports, isLoading, isError, refetch } = useReports();
  const downloadMutation = useDownloadReport();

  const handleDownload = (id: string, type: ReportType, createdAt: string) => {
    const date = new Date(createdAt).toISOString().slice(0, 10);
    const filename = `vulnix-report-${type}-${date}.pdf`;
    downloadMutation.mutate({ id, filename });
  };

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
          <DocumentIcon />
          CISO 리포트
        </h1>
        <p className="text-gray-400 mt-1 text-sm">
          규정 준수(CSAP, ISO 27001, ISMS) 보안 리포트를 생성하고 다운로드하세요.
        </p>
      </div>

      {/* 리포트 생성 폼 */}
      <GenerateReportForm />

      {/* 리포트 목록 섹션 */}
      <div>
        <h2 className="text-base font-semibold text-white mb-3">생성된 리포트</h2>

        {/* 에러 */}
        {isError && (
          <div className="card border-red-900/50 p-4 mb-4 flex items-center justify-between">
            <p className="text-red-400 text-sm">데이터를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => void refetch()} className="btn-secondary text-xs">
              재시도
            </button>
          </div>
        )}

        {/* 로딩 */}
        {isLoading && (
          <div className="space-y-2 animate-pulse">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="card p-4">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-16 bg-gray-700 rounded-full" />
                  <div className="h-4 w-32 bg-gray-700 rounded" />
                  <div className="ml-auto h-5 w-12 bg-gray-700 rounded" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && reports?.length === 0 && (
          <div className="card p-12 text-center">
            <div className="flex justify-center mb-3 text-gray-600">
              <DocumentIcon />
            </div>
            <p className="text-gray-400 text-sm">생성된 리포트가 없습니다.</p>
            <p className="text-gray-500 text-xs mt-1">위 폼에서 첫 번째 리포트를 생성해보세요.</p>
          </div>
        )}

        {/* 리포트 목록 테이블 */}
        {!isLoading && reports && reports.length > 0 && (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">유형</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">기간</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">팀</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">생성일</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">상태</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-3">
                      <ReportTypeBadge type={report.reportType} />
                    </td>
                    <td className="px-4 py-3 text-gray-300 text-xs">
                      {formatDate(report.startDate)} ~ {formatDate(report.endDate)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {report.teamName ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {formatDate(report.createdAt)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={report.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {report.status === 'completed' && (
                        <button
                          type="button"
                          onClick={() =>
                            handleDownload(report.id, report.reportType, report.createdAt)
                          }
                          disabled={downloadMutation.isPending}
                          className="btn-secondary text-xs px-2.5 py-1.5 gap-1"
                        >
                          <DownloadIcon />
                          다운로드
                        </button>
                      )}
                      {report.status === 'pending' && (
                        <span className="text-xs text-yellow-400 animate-pulse">생성 중...</span>
                      )}
                      {report.status === 'failed' && (
                        <span className="text-xs text-red-400">실패</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
