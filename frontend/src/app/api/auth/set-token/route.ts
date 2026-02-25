/**
 * HttpOnly 쿠키 설정 API Route
 * XSS 취약점 방지: localStorage 대신 HttpOnly 쿠키에 JWT 저장
 */
import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  const { access_token, refresh_token } = (await req.json()) as {
    access_token: string;
    refresh_token?: string;
  };

  if (!access_token) {
    return NextResponse.json(
      { success: false, error: 'access_token이 필요합니다.' },
      { status: 400 },
    );
  }

  const cookieStore = await cookies();
  const isProduction = process.env.NODE_ENV === 'production';

  // Access Token — 1시간 유효
  cookieStore.set('access_token', access_token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: 'lax',
    maxAge: 60 * 60, // 1시간
    path: '/',
  });

  // Refresh Token — 7일 유효 (선택적)
  if (refresh_token) {
    cookieStore.set('refresh_token', refresh_token, {
      httpOnly: true,
      secure: isProduction,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7, // 7일
      path: '/',
    });
  }

  return NextResponse.json({ success: true, ok: true });
}
