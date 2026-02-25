import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-8 text-center">
      <div className="text-6xl font-bold text-gray-700 mb-4">404</div>
      <h2 className="text-lg font-semibold text-white mb-2">페이지를 찾을 수 없습니다</h2>
      <p className="text-gray-400 text-sm mb-6">요청하신 페이지가 존재하지 않거나 이동되었습니다.</p>
      <Link href="/dashboard" className="btn-primary">
        대시보드로 이동
      </Link>
    </div>
  );
}
