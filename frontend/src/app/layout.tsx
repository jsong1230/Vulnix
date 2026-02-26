import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages } from 'next-intl/server';
import './globals.css';
import { Header } from '@/components/layout/header';
import { Sidebar } from '@/components/layout/sidebar';
import { QueryProvider } from '@/components/layout/query-provider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Vulnix — AI 보안 취약점 탐지 & 자동 패치',
  description:
    'GitHub 저장소의 보안 취약점을 자동으로 탐지하고 패치 PR을 생성합니다.',
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default async function RootLayout({ children }: RootLayoutProps) {
  // 쿠키 기반 로케일 읽기 (i18n/request.ts 설정 따름)
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className="h-full">
      <body className={`${inter.className} h-full`}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {/* 전체 레이아웃: 사이드바 + 메인 영역 */}
          <div className="flex h-full">
            {/* 사이드 내비게이션 */}
            <Sidebar />

            {/* 메인 콘텐츠 영역 */}
            <div className="flex flex-1 flex-col min-w-0">
              {/* 상단 헤더 */}
              <Header />

              {/* 페이지 콘텐츠 */}
              <main className="flex-1 overflow-y-auto p-6">
                <QueryProvider>{children}</QueryProvider>
              </main>
            </div>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
