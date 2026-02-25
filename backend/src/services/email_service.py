"""SMTP 기반 이메일 발송 서비스"""

import os
import smtplib
from email import encoders
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailService:
    """SMTP 기반 이메일 발송 서비스.

    환경변수:
    - SMTP_HOST: SMTP 서버 호스트
    - SMTP_PORT: SMTP 포트 (기본 587, STARTTLS)
    - SMTP_USERNAME: SMTP 인증 사용자명
    - SMTP_PASSWORD: SMTP 인증 비밀번호
    - SMTP_FROM_EMAIL: 발신자 이메일
    - SMTP_FROM_NAME: 발신자 이름 (기본 "Vulnix Security")
    """

    def __init__(self) -> None:
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_username = os.environ.get("SMTP_USERNAME", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", "")
        self.smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Vulnix Security")

    def _is_configured(self) -> bool:
        """SMTP 설정이 완료되어 있는지 확인한다."""
        return bool(
            self.smtp_host
            and self.smtp_username
            and self.smtp_password
        )

    async def send_report_email(
        self,
        recipients: list[str],
        subject: str,
        body_html: str,
        attachment_path: str,
        attachment_name: str,
    ) -> bool:
        """리포트를 첨부하여 이메일을 발송한다.

        Args:
            recipients: 수신자 이메일 목록
            subject: 이메일 제목
            body_html: HTML 본문
            attachment_path: 첨부 파일 경로
            attachment_name: 첨부 파일 이름 (다운로드 시 표시될 이름)

        Returns:
            발송 성공 여부 (True/False)
        """
        # SMTP 환경변수 미설정 시 발송 건너뜀
        if not self._is_configured():
            return False

        # 첨부 파일 존재 여부 확인
        if not os.path.exists(attachment_path):
            return False

        try:
            # 멀티파트 이메일 메시지 구성
            msg = MIMEMultipart("mixed")
            msg["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            # HTML 본문 추가
            html_part = MIMEText(body_html, "html", "utf-8")
            msg.attach(html_part)

            # 첨부 파일 추가
            with open(attachment_path, "rb") as f:
                file_data = f.read()

            # 파일 확장자에 따라 MIME 타입 결정
            if attachment_name.endswith(".pdf"):
                attachment = MIMEApplication(file_data, _subtype="pdf")
            elif attachment_name.endswith(".json"):
                attachment = MIMEApplication(file_data, _subtype="json")
            else:
                attachment = MIMEApplication(file_data, _subtype="octet-stream")

            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment_name,
            )
            msg.attach(attachment)

            # SMTP 발송
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(
                    self.smtp_from_email,
                    recipients,
                    msg.as_string(),
                )

            return True

        except (smtplib.SMTPException, OSError, ConnectionRefusedError):
            return False
