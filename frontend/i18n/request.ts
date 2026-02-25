import { getRequestConfig } from 'next-intl/server';
import { cookies } from 'next/headers';

// next-intl 요청 설정 — 쿠키에서 locale 읽어 번역 메시지 로드
export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const locale = cookieStore.get('locale')?.value ?? 'ko';
  const validLocale = ['ko', 'en'].includes(locale) ? locale : 'ko';

  return {
    locale: validLocale,
    messages: (await import(`../messages/${validLocale}.json`)).default,
  };
});
