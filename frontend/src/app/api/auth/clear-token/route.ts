/**
 * HttpOnly 쿠키 삭제 API Route
 * 로그아웃 시 서버 사이드에서 쿠키 삭제 (HttpOnly 쿠키는 JS로 직접 삭제 불가)
 */
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function POST() {
  const cookieStore = await cookies();

  // Access Token 쿠키 삭제
  cookieStore.delete('access_token');

  // Refresh Token 쿠키 삭제
  cookieStore.delete('refresh_token');

  return NextResponse.json({ success: true, ok: true });
}
