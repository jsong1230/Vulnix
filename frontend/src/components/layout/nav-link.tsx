'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavLinkProps {
  href: string;
  label: string;
  icon: React.ReactNode;
}

/**
 * 현재 경로를 감지하여 활성 스타일을 적용하는 클라이언트 내비게이션 링크
 */
export function NavLink({ href, label, icon }: NavLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm ${
        isActive
          ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-700/40'
          : 'text-gray-400 hover:text-white hover:bg-gray-800 border border-transparent'
      }`}
    >
      {icon}
      {label}
    </Link>
  );
}
