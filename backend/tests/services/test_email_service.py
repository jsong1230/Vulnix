"""F-10 이메일 서비스 단위 테스트 — RED 단계

EmailService.send_report_email() SMTP 발송, 첨부 파일, 다수 수신자,
SMTP 실패 처리를 대상으로 실패하는 테스트를 작성한다.

구현이 없으므로 모두 FAIL(ImportError 또는 AssertionError)이어야 한다.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pdf_file():
    """테스트용 더미 PDF 파일 픽스처."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # 최소 PDF 헤더 작성
        f.write(b"%PDF-1.4\n%%EOF\n")
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_json_file():
    """테스트용 더미 JSON 파일 픽스처."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write('{"security_score": 75.5, "total_vulnerabilities": 42}')
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def smtp_env_vars(monkeypatch):
    """SMTP 환경변수 픽스처."""
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "vulnix@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test_password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "vulnix@test.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "Vulnix Security")


# ──────────────────────────────────────────────────────────────
# U-1023: SMTP 발송 성공 테스트
# ──────────────────────────────────────────────────────────────

class TestEmailServiceSendSuccess:
    """이메일 발송 성공 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_smtp_발송_성공_True_반환(self, sample_pdf_file, smtp_env_vars):
        """U-1023: SMTP mock 정상 동작 시 True 반환하고 sendmail 1회 호출."""
        from src.services.email_service import EmailService

        service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.sendmail = MagicMock()

            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] CISO 보안 리포트",
                body_html="<h1>보안 리포트</h1>",
                attachment_path=sample_pdf_file,
                attachment_name="ciso_report.pdf",
            )

        assert result is True, "SMTP 발송 성공 시 True를 반환해야 한다"
        mock_smtp_instance.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_sendmail_수신자_목록_정확(self, sample_pdf_file, smtp_env_vars):
        """U-1023: sendmail 호출 시 수신자 목록이 정확해야 한다."""
        from src.services.email_service import EmailService

        service = EmailService()
        recipients = ["ciso@company.com"]

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.sendmail = MagicMock()

            await service.send_report_email(
                recipients=recipients,
                subject="[Vulnix] CISO 보안 리포트",
                body_html="<h1>보안 리포트</h1>",
                attachment_path=sample_pdf_file,
                attachment_name="ciso_report.pdf",
            )

        call_args = mock_smtp_instance.sendmail.call_args
        assert call_args is not None, "sendmail이 호출되어야 한다"
        # sendmail(from, to, msg) — to가 수신자 목록 포함하는지 확인
        call_positional = call_args[0] if call_args[0] else []
        call_keyword = call_args[1] if call_args[1] else {}
        to_addresses = call_positional[1] if len(call_positional) > 1 else call_keyword.get("to_addrs", [])
        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]
        assert "ciso@company.com" in str(to_addresses), \
            f"수신자 ciso@company.com이 sendmail to 인자에 포함되어야 한다 (실제: {to_addresses})"


# ──────────────────────────────────────────────────────────────
# U-1024: SMTP 연결 실패 테스트
# ──────────────────────────────────────────────────────────────

class TestEmailServiceSendFailure:
    """이메일 발송 실패 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_smtp_연결_실패_False_반환(self, sample_pdf_file, smtp_env_vars):
        """U-1024: SMTP ConnectionRefusedError 시 False 반환."""
        from src.services.email_service import EmailService

        service = EmailService()

        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("연결 거부됨")):
            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] CISO 보안 리포트",
                body_html="<h1>보안 리포트</h1>",
                attachment_path=sample_pdf_file,
                attachment_name="ciso_report.pdf",
            )

        assert result is False, "SMTP 연결 실패 시 False를 반환해야 한다"

    @pytest.mark.asyncio
    async def test_smtp_연결_실패_예외_미전파(self, sample_pdf_file, smtp_env_vars):
        """U-1024: SMTP 연결 실패 시 예외가 호출자에게 전파되면 안 된다."""
        from src.services.email_service import EmailService

        service = EmailService()

        # 예외가 외부로 전파되지 않고 False를 반환하는지 확인
        with patch("smtplib.SMTP", side_effect=OSError("네트워크 오류")):
            try:
                result = await service.send_report_email(
                    recipients=["ciso@company.com"],
                    subject="[Vulnix] 테스트",
                    body_html="<p>테스트</p>",
                    attachment_path=sample_pdf_file,
                    attachment_name="report.pdf",
                )
                # 예외 없이 False를 반환해야 함
                assert result is False, "SMTP 오류 시 예외 전파 없이 False를 반환해야 한다"
            except Exception as e:
                pytest.fail(f"SMTP 오류가 예외로 전파되면 안 된다: {e}")

    @pytest.mark.asyncio
    async def test_smtp_인증_실패_False_반환(self, sample_pdf_file, smtp_env_vars):
        """SMTP 인증 실패(SMTPAuthenticationError) 시 False 반환."""
        import smtplib
        from src.services.email_service import EmailService

        service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.login = MagicMock(
                side_effect=smtplib.SMTPAuthenticationError(535, b"Authentication failed")
            )

            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] 리포트",
                body_html="<p>내용</p>",
                attachment_path=sample_pdf_file,
                attachment_name="report.pdf",
            )

        assert result is False, "SMTP 인증 실패 시 False를 반환해야 한다"


# ──────────────────────────────────────────────────────────────
# U-1025: 첨부 파일 포함 테스트
# ──────────────────────────────────────────────────────────────

class TestEmailServiceAttachment:
    """이메일 첨부 파일 처리 테스트"""

    @pytest.mark.asyncio
    async def test_pdf_첨부_파일_포함(self, sample_pdf_file, smtp_env_vars):
        """U-1025: sendmail에 전달된 메시지에 PDF 첨부가 포함되어야 한다."""
        from src.services.email_service import EmailService

        service = EmailService()
        sent_messages = []

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg):
                sent_messages.append(msg)

            mock_smtp_instance.sendmail = MagicMock(side_effect=capture_sendmail)

            await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] CISO 리포트",
                body_html="<h1>보안 리포트</h1>",
                attachment_path=sample_pdf_file,
                attachment_name="ciso_report.pdf",
            )

        assert len(sent_messages) == 1, "sendmail이 1회 호출되어야 한다"
        message_str = sent_messages[0] if isinstance(sent_messages[0], str) else sent_messages[0].as_string()
        # Content-Disposition: attachment 또는 PDF MIME 타입 포함 확인
        assert (
            "attachment" in message_str.lower()
            or "application/pdf" in message_str.lower()
            or "ciso_report" in message_str.lower()
        ), "이메일 메시지에 PDF 첨부 정보가 포함되어야 한다"

    @pytest.mark.asyncio
    async def test_json_첨부_파일_포함(self, sample_json_file, smtp_env_vars):
        """JSON 리포트를 첨부 파일로 포함할 수 있어야 한다."""
        from src.services.email_service import EmailService

        service = EmailService()
        sent_messages = []

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg):
                sent_messages.append(msg)

            mock_smtp_instance.sendmail = MagicMock(side_effect=capture_sendmail)

            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] CSAP 증적 데이터",
                body_html="<h1>CSAP 증적</h1>",
                attachment_path=sample_json_file,
                attachment_name="csap_evidence.json",
            )

        assert result is True, "JSON 첨부 이메일 발송이 성공해야 한다"


# ──────────────────────────────────────────────────────────────
# U-1026: 다수 수신자 테스트
# ──────────────────────────────────────────────────────────────

class TestEmailServiceMultipleRecipients:
    """다수 수신자 이메일 발송 테스트"""

    @pytest.mark.asyncio
    async def test_다수_수신자_발송_성공(self, sample_pdf_file, smtp_env_vars):
        """U-1026: 수신자 3명 지정 시 sendmail에 3명 모두 포함."""
        from src.services.email_service import EmailService

        service = EmailService()
        recipients = ["a@co.com", "b@co.com", "c@co.com"]
        captured_to = []

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg):
                if isinstance(to_addrs, list):
                    captured_to.extend(to_addrs)
                else:
                    captured_to.append(to_addrs)

            mock_smtp_instance.sendmail = MagicMock(side_effect=capture_sendmail)

            result = await service.send_report_email(
                recipients=recipients,
                subject="[Vulnix] 보안 리포트",
                body_html="<h1>리포트</h1>",
                attachment_path=sample_pdf_file,
                attachment_name="report.pdf",
            )

        assert result is True, "다수 수신자 발송이 성공해야 한다"

        # sendmail이 호출되었고 수신자 3명이 모두 포함되어야 한다
        mock_smtp_instance.sendmail.assert_called_once()
        call_args = mock_smtp_instance.sendmail.call_args[0]
        to_arg = call_args[1] if len(call_args) > 1 else []
        to_str = str(to_arg)
        for recipient in recipients:
            assert recipient in to_str, \
                f"수신자 {recipient}가 sendmail 인자에 포함되어야 한다 (실제: {to_str})"

    @pytest.mark.asyncio
    async def test_단일_수신자_발송_성공(self, sample_pdf_file, smtp_env_vars):
        """수신자 1명도 정상 발송 가능해야 한다."""
        from src.services.email_service import EmailService

        service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.sendmail = MagicMock()

            result = await service.send_report_email(
                recipients=["single@company.com"],
                subject="[Vulnix] 리포트",
                body_html="<p>내용</p>",
                attachment_path=sample_pdf_file,
                attachment_name="report.pdf",
            )

        assert result is True, "단일 수신자 발송이 성공해야 한다"
        mock_smtp_instance.sendmail.assert_called_once()


# ──────────────────────────────────────────────────────────────
# 경계 조건 테스트
# ──────────────────────────────────────────────────────────────

class TestEmailServiceEdgeCases:
    """EmailService 경계 조건 테스트"""

    @pytest.mark.asyncio
    async def test_smtp_환경변수_미설정_시_발송_건너뜀(self, sample_pdf_file, monkeypatch):
        """SMTP 환경변수 미설정 시 발송을 건너뛰고 False 반환 (리포트 생성 실패 아님)."""
        from src.services.email_service import EmailService

        # SMTP 환경변수 제거
        for env_var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD"]:
            monkeypatch.delenv(env_var, raising=False)

        service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.sendmail = MagicMock()

            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] 리포트",
                body_html="<p>내용</p>",
                attachment_path=sample_pdf_file,
                attachment_name="report.pdf",
            )

        # 환경변수 미설정 시 발송 건너뜀 — 예외 없이 False 또는 None 반환
        assert result in (False, None), \
            "SMTP 환경변수 미설정 시 발송을 건너뛰고 False/None을 반환해야 한다"

    @pytest.mark.asyncio
    async def test_첨부_파일_경로_없음_오류_처리(self, smtp_env_vars):
        """존재하지 않는 첨부 파일 경로 지정 시 안전하게 처리되어야 한다."""
        from src.services.email_service import EmailService

        service = EmailService()
        nonexistent_path = "/nonexistent/path/report.pdf"

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
            mock_smtp_instance.sendmail = MagicMock()

            # FileNotFoundError를 외부에 전파하지 않고 처리해야 한다
            result = await service.send_report_email(
                recipients=["ciso@company.com"],
                subject="[Vulnix] 리포트",
                body_html="<p>내용</p>",
                attachment_path=nonexistent_path,
                attachment_name="report.pdf",
            )

        # 파일 없으면 발송 실패 (False) 또는 예외 처리하여 False 반환
        assert result is False, "존재하지 않는 첨부 파일 시 False를 반환해야 한다"
