"""토큰 암호화/복호화 및 Git 플랫폼 URL 검증 유틸리티

PAT(Personal Access Token) / App Password를 Fernet 대칭 암호화로 안전하게 저장하고,
self-managed Git 플랫폼 URL에 대해 SSRF(Server-Side Request Forgery) 방어를 수행한다.
"""

import base64
import ipaddress
import os
import socket
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """환경변수에서 암호화 키를 로드하여 Fernet 인스턴스를 반환한다.

    환경변수 TOKEN_ENCRYPTION_KEY가 설정되지 않은 경우(테스트/PoC 환경):
    임시 키를 생성한다. 운영 환경에서는 반드시 환경변수를 설정해야 한다.

    Returns:
        Fernet 인스턴스
    """
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        # 테스트/PoC 환경: 임시 키 생성 (운영에서는 반드시 환경변수 설정 필요)
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    # Fernet 키는 32바이트 base64url이어야 함
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # 유효하지 않은 키면 새 키로 폴백 (운영 환경에서는 이 케이스가 발생하지 않아야 함)
        return Fernet(Fernet.generate_key())


def encrypt_token(plain_token: str) -> str:
    """평문 토큰을 Fernet 대칭 암호화하여 base64 문자열로 반환한다.

    Args:
        plain_token: 암호화할 평문 토큰 (PAT, App Password 등)

    Returns:
        암호화된 토큰 문자열
    """
    return _get_fernet().encrypt(plain_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """암호화된 토큰을 복호화하여 평문으로 반환한다.

    복호화 실패(잘못된 키, 손상된 데이터 등) 시 빈 문자열을 반환한다.

    Args:
        encrypted_token: 암호화된 토큰 문자열

    Returns:
        복호화된 평문 토큰. 실패 시 빈 문자열.
    """
    try:
        return _get_fernet().decrypt(encrypted_token.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def validate_git_platform_url(url: str) -> bool:
    """Git 플랫폼 self-managed URL 유효성 검사를 수행한다.

    SSRF(Server-Side Request Forgery) 방어를 위해 다음을 검증한다:
    1. HTTPS 프로토콜 필수
    2. 유효한 hostname 필수
    3. DNS 조회 후 내부/사설 IP 차단

    Args:
        url: 검증할 Git 플랫폼 URL

    Returns:
        유효한 URL이면 True, 그렇지 않으면 False
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # DNS 조회 후 SSRF 방어 (내부/사설 IP 차단)
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            # DNS 조회 실패 시 허용 불가 (존재하지 않는 호스트)
            return False
        for addr_info in addr_infos:
            ip_str = addr_info[4][0]
            if _is_private_ip(ip_str):
                return False
        return True
    except Exception:
        return False


def _is_private_ip(ip: str) -> bool:
    """IP 주소가 내부/사설 IP 대역인지 확인한다.

    차단 대상 (IPv4):
    - 127.x.x.x (loopback)
    - 10.x.x.x (Class A private)
    - 172.16.x.x ~ 172.31.x.x (Class B private)
    - 192.168.x.x (Class C private)
    - 링크-로컬, 예약 대역 등

    차단 대상 (IPv6):
    - ::1 (loopback)
    - fc00::/7 (ULA)
    - fe80::/10 (link-local)
    - IPv4-mapped IPv6 주소는 매핑된 IPv4 기준으로 재검사

    Args:
        ip: 검사할 IP 주소 문자열

    Returns:
        내부/사설 IP이면 True, 공개 IP이면 False
    """
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv6Address):
            # 루프백 (::1)
            if addr.is_loopback:
                return True
            # IPv4-mapped (::ffff:x.x.x.x) — 매핑된 IPv4 주소로 재귀 검사
            if addr.ipv4_mapped is not None:
                return _is_private_ip(str(addr.ipv4_mapped))
            # ULA (fc00::/7)
            if addr in ipaddress.ip_network("fc00::/7"):
                return True
            # 링크-로컬 (fe80::/10)
            if addr in ipaddress.ip_network("fe80::/10"):
                return True
            return False
        # IPv4: is_private, is_loopback, is_link_local, is_reserved 모두 차단
        return (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
        )
    except ValueError:
        return True
