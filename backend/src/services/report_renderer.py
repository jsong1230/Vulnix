"""리포트 렌더러 — 전략 패턴으로 리포트 유형별 PDF/JSON 생성

reportlab 사용 가능 시 실제 PDF 생성, 불가능 시 mock PDF 반환.
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class ReportRenderer(ABC):
    """리포트 렌더러 공통 인터페이스."""

    @abstractmethod
    def render_pdf(self, data: object, output_path: str) -> None:
        """PDF 파일을 생성한다."""

    @abstractmethod
    def render_json(self, data: object, output_path: str) -> None:
        """JSON 파일을 생성한다."""

    def _write_mock_pdf(self, output_path: str, content_text: str) -> None:
        """reportlab 미설치 시 최소 유효 PDF 파일을 생성한다."""
        # 최소한의 유효한 PDF 구조 (텍스트 포함)
        encoded = content_text.encode("latin-1", errors="replace")
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>\nendobj\n"
            b"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>\nendobj\n"
            b"6 0 obj\n<< /Length " + str(len(encoded) + 50).encode() + b" >>\nstream\n"
            b"BT /F1 12 Tf 50 800 Td (" + encoded + b") Tj ET\n"
            b"endstream\nendobj\n"
            b"7 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"xref\n0 8\n0000000000 65535 f \n"
            b"trailer\n<< /Size 8 /Root 1 0 R >>\n"
            b"startxref\n9\n%%EOF\n"
        )
        with open(output_path, "wb") as f:
            f.write(pdf_content)

    def _write_json(self, data: dict, output_path: str) -> None:
        """JSON 데이터를 파일로 저장한다."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ──────────────────────────────────────────────────────────────
# CISO 경영진 리포트 렌더러
# ──────────────────────────────────────────────────────────────


class CISOReportRenderer(ReportRenderer):
    """CISO 경영진 리포트 렌더러.

    reportlab 사용:
    - SimpleDocTemplate으로 PDF 생성
    - 보안 점수, 취약점 통계, 대응 현황 포함
    """

    def render_pdf(self, data: object, output_path: str) -> None:
        """CISO 경영진 리포트 PDF를 생성한다."""
        if not REPORTLAB_AVAILABLE:
            self._write_mock_pdf(output_path, "CISO Report A.12.6.1 A.14.2.1 2.10.4 2.11.5")
            return

        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # 표지 페이지
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontSize=24,
            spaceAfter=20,
        )
        story.append(Spacer(1, 2 * cm))
        story.append(Paragraph("CISO 보안 리포트", title_style))
        team_name = getattr(data, "team_name", "")
        period_start = getattr(data, "period_start", "")
        period_end = getattr(data, "period_end", "")
        story.append(Paragraph(f"팀: {team_name}", styles["Normal"]))
        story.append(Paragraph(f"기간: {period_start} ~ {period_end}", styles["Normal"]))
        story.append(Paragraph(f"생성일: {datetime.now(timezone.utc).date()}", styles["Normal"]))
        story.append(PageBreak())

        # 경영진 요약
        story.append(Paragraph("경영진 요약 (Executive Summary)", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        score = getattr(data, "current_security_score", 0.0)
        total_vulns = getattr(data, "total_vulnerabilities", 0)
        new_vulns = getattr(data, "new_vulnerabilities", 0)
        resolved_vulns = getattr(data, "resolved_vulnerabilities", 0)
        resolution_rate = getattr(data, "resolution_rate", 0.0)

        summary_data = [
            ["지표", "값"],
            ["전체 보안 점수", f"{score:.1f}"],
            ["총 취약점 수", str(total_vulns)],
            ["신규 발견", str(new_vulns)],
            ["해결 건수", str(resolved_vulns)],
            ["해결률", f"{resolution_rate:.1f}%"],
        ]
        summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(summary_table)
        story.append(PageBreak())

        # 취약점 통계
        story.append(Paragraph("취약점 통계", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        severity_dist = getattr(data, "severity_distribution", {})
        vuln_data = [
            ["심각도", "건수"],
            ["Critical", str(severity_dist.get("critical", 0))],
            ["High", str(severity_dist.get("high", 0))],
            ["Medium", str(severity_dist.get("medium", 0))],
            ["Low", str(severity_dist.get("low", 0))],
        ]
        vuln_table = Table(vuln_data, colWidths=[8 * cm, 8 * cm])
        vuln_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(vuln_table)
        story.append(Spacer(1, 0.5 * cm))

        # 대응 현황
        avg_time = getattr(data, "avg_response_time_hours", 0.0)
        auto_rate = getattr(data, "auto_patch_rate", 0.0)
        story.append(Paragraph("대응 현황", styles["Heading2"]))
        story.append(Paragraph(f"평균 대응 시간: {avg_time:.1f}h", styles["Normal"]))
        story.append(Paragraph(f"자동 패치 적용률: {auto_rate:.1f}%", styles["Normal"]))

        doc.build(story)

    def render_json(self, data: object, output_path: str) -> None:
        """CISO JSON 보고서를 생성한다."""
        output = {
            "report_type": "ciso",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "team_name": getattr(data, "team_name", ""),
            "period_start": str(getattr(data, "period_start", "")),
            "period_end": str(getattr(data, "period_end", "")),
            "security_score": {
                "current": getattr(data, "current_security_score", 0.0),
                "previous": getattr(data, "previous_security_score", 0.0),
                "trend": getattr(data, "score_trend", []),
            },
            "vulnerabilities": {
                "total": getattr(data, "total_vulnerabilities", 0),
                "new": getattr(data, "new_vulnerabilities", 0),
                "resolved": getattr(data, "resolved_vulnerabilities", 0),
                "resolution_rate": getattr(data, "resolution_rate", 0.0),
                "severity_distribution": getattr(data, "severity_distribution", {}),
                "status_distribution": getattr(data, "status_distribution", {}),
                "type_top10": getattr(data, "vulnerability_type_top10", []),
            },
            "scans": {
                "total": getattr(data, "total_scans", 0),
                "jobs": getattr(data, "scan_jobs", []),
            },
            "response": {
                "avg_time_hours": getattr(data, "avg_response_time_hours", 0.0),
                "auto_patch_rate": getattr(data, "auto_patch_rate", 0.0),
            },
            "repositories": getattr(data, "repo_score_ranking", []),
            "unresolved_critical": getattr(data, "unresolved_critical", []),
        }
        self._write_json(output, output_path)


# ──────────────────────────────────────────────────────────────
# CSAP 인증 증적 렌더러
# ──────────────────────────────────────────────────────────────


class CSAPReportRenderer(ReportRenderer):
    """CSAP 인증 증적 렌더러.

    클라우드 보안 인증 2.0 '취약점 관리' 영역 증적 자료를 생성한다.
    """

    def render_pdf(self, data: object, output_path: str) -> None:
        """CSAP 증적 PDF를 생성한다."""
        if not REPORTLAB_AVAILABLE:
            self._write_mock_pdf(output_path, "CSAP 2.0 취약점관리 증적자료")
            return

        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("CSAP 인증 증적 자료", styles["Title"]))
        story.append(Paragraph("취약점 관리 프로세스 증적", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        team_name = getattr(data, "team_name", "")
        period_start = getattr(data, "period_start", "")
        period_end = getattr(data, "period_end", "")
        story.append(Paragraph(f"팀: {team_name}", styles["Normal"]))
        story.append(Paragraph(f"기간: {period_start} ~ {period_end}", styles["Normal"]))
        story.append(PageBreak())

        # 취약점 관리 현황
        story.append(Paragraph("1. 취약점 관리 현황", styles["Heading1"]))
        total_vulns = getattr(data, "total_vulnerabilities", 0)
        resolved_vulns = getattr(data, "resolved_vulnerabilities", 0)
        resolution_rate = getattr(data, "resolution_rate", 0.0)

        vuln_table_data = [
            ["항목", "값"],
            ["총 취약점", str(total_vulns)],
            ["조치 완료", str(resolved_vulns)],
            ["조치율", f"{resolution_rate:.1f}%"],
        ]
        vuln_table = Table(vuln_table_data, colWidths=[8 * cm, 8 * cm])
        vuln_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(vuln_table)
        story.append(PageBreak())

        # 스캔 이력
        story.append(Paragraph("2. 자동화 보안 점검 이력", styles["Heading1"]))
        scan_jobs = getattr(data, "scan_jobs", [])
        if scan_jobs:
            scan_data = [["저장소", "상태", "일시", "발견 수"]]
            for scan in scan_jobs[:10]:
                scan_data.append([
                    scan.get("repo_name", ""),
                    scan.get("status", ""),
                    scan.get("created_at", ""),
                    str(scan.get("findings_count", 0)),
                ])
            scan_table = Table(scan_data, colWidths=[5 * cm, 3 * cm, 5 * cm, 3 * cm])
            scan_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]))
            story.append(scan_table)
        else:
            story.append(Paragraph("스캔 이력 없음", styles["Normal"]))

        doc.build(story)

    def render_json(self, data: object, output_path: str) -> None:
        """CSAP JSON 증적 데이터를 생성한다."""
        output = {
            "report_type": "csap",
            "standard": "CSAP 2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "team_name": getattr(data, "team_name", ""),
            "period_start": str(getattr(data, "period_start", "")),
            "period_end": str(getattr(data, "period_end", "")),
            "vulnerability_management": {
                "total_vulnerabilities": getattr(data, "total_vulnerabilities", 0),
                "resolved": getattr(data, "resolved_vulnerabilities", 0),
                "resolution_rate": getattr(data, "resolution_rate", 0.0),
                "severity_distribution": getattr(data, "severity_distribution", {}),
                "unresolved_critical": getattr(data, "unresolved_critical", []),
            },
            "scan_history": {
                "total_scans": getattr(data, "total_scans", 0),
                "jobs": getattr(data, "scan_jobs", []),
            },
            "patch_history": {
                "patch_prs": getattr(data, "patch_prs", []),
                "auto_patch_rate": getattr(data, "auto_patch_rate", 0.0),
            },
        }
        self._write_json(output, output_path)


# ──────────────────────────────────────────────────────────────
# ISO 27001 인증 증적 렌더러
# ──────────────────────────────────────────────────────────────


class ISO27001ReportRenderer(ReportRenderer):
    """ISO 27001 인증 증적 렌더러.

    Annex A.12.6 (기술 취약점 관리), A.14.2 (개발 및 지원 프로세스의 보안) 증적.
    """

    # CWE 코드 매핑 (취약점 유형 → CWE)
    CWE_MAPPING: dict = {
        "sql_injection": "CWE-89",
        "xss": "CWE-79",
        "command_injection": "CWE-78",
        "path_traversal": "CWE-22",
        "insecure_deserialization": "CWE-502",
        "xxe": "CWE-611",
        "ssrf": "CWE-918",
        "open_redirect": "CWE-601",
    }

    # OWASP Top 10 매핑
    OWASP_MAPPING: dict = {
        "sql_injection": "A03:2021 – Injection",
        "xss": "A03:2021 – Injection",
        "command_injection": "A03:2021 – Injection",
        "path_traversal": "A01:2021 – Broken Access Control",
        "insecure_deserialization": "A08:2021 – Software and Data Integrity Failures",
        "xxe": "A05:2021 – Security Misconfiguration",
        "ssrf": "A10:2021 – Server-Side Request Forgery",
        "open_redirect": "A01:2021 – Broken Access Control",
    }

    def render_pdf(self, data: object, output_path: str) -> None:
        """ISO 27001 증적 PDF를 생성한다.

        A.12.6.1 기술 취약점 관리, A.14.2.1 보안 개발 정책 항목 포함.
        """
        if not REPORTLAB_AVAILABLE:
            self._write_mock_pdf(
                output_path,
                "ISO 27001 Annex A.12.6.1 Technical Vulnerability Management A.14.2.1"
            )
            return

        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("ISO 27001 인증 증적 자료", styles["Title"]))
        team_name = getattr(data, "team_name", "")
        period_start = getattr(data, "period_start", "")
        period_end = getattr(data, "period_end", "")
        story.append(Paragraph(f"팀: {team_name}", styles["Normal"]))
        story.append(Paragraph(f"기간: {period_start} ~ {period_end}", styles["Normal"]))
        story.append(PageBreak())

        # A.12.6.1 기술 취약점 관리
        story.append(Paragraph("A.12.6.1 기술 취약점 관리", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        total_vulns = getattr(data, "total_vulnerabilities", 0)
        resolved_vulns = getattr(data, "resolved_vulnerabilities", 0)
        resolution_rate = getattr(data, "resolution_rate", 0.0)

        story.append(Paragraph(f"총 취약점: {total_vulns}", styles["Normal"]))
        story.append(Paragraph(f"조치 완료: {resolved_vulns}", styles["Normal"]))
        story.append(Paragraph(f"조치율: {resolution_rate:.1f}%", styles["Normal"]))
        story.append(PageBreak())

        # A.14.2.1 보안 개발 정책
        story.append(Paragraph("A.14.2.1 보안 개발 정책", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        total_scans = getattr(data, "total_scans", 0)
        story.append(Paragraph(f"코드 보안 점검 횟수: {total_scans}", styles["Normal"]))

        doc.build(story)

    def render_json(self, data: object, output_path: str) -> None:
        """ISO 27001 JSON 증적 데이터를 생성한다."""
        output = {
            "report_type": "iso27001",
            "standard": "ISO/IEC 27001:2022",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "team_name": getattr(data, "team_name", ""),
            "period_start": str(getattr(data, "period_start", "")),
            "period_end": str(getattr(data, "period_end", "")),
            "A12_6_1": {
                "title": "Technical Vulnerability Management",
                "total_vulnerabilities": getattr(data, "total_vulnerabilities", 0),
                "resolved": getattr(data, "resolved_vulnerabilities", 0),
                "resolution_rate": getattr(data, "resolution_rate", 0.0),
                "severity_distribution": getattr(data, "severity_distribution", {}),
                "unresolved_critical": getattr(data, "unresolved_critical", []),
            },
            "A14_2_1": {
                "title": "Secure Development Policy",
                "total_scans": getattr(data, "total_scans", 0),
                "scan_jobs": getattr(data, "scan_jobs", []),
            },
            "vulnerabilities": {
                "items": getattr(data, "unresolved_critical", []),
                "type_top10": getattr(data, "vulnerability_type_top10", []),
            },
            "cwe_mapping": self.CWE_MAPPING,
            "owasp_mapping": self.OWASP_MAPPING,
        }
        self._write_json(output, output_path)


# ──────────────────────────────────────────────────────────────
# ISMS 인증 증적 렌더러
# ──────────────────────────────────────────────────────────────


class ISMSReportRenderer(ReportRenderer):
    """ISMS-P 인증 증적 렌더러.

    2.10.4 (취약점 점검 및 조치), 2.11.5 (소스코드 보안) 항목 증적.
    """

    def render_pdf(self, data: object, output_path: str) -> None:
        """ISMS 증적 PDF를 생성한다.

        2.10.4 취약점 점검 및 조치, 2.11.5 소스코드 보안 항목 포함.
        """
        if not REPORTLAB_AVAILABLE:
            self._write_mock_pdf(
                output_path,
                "ISMS-P 인증 증적 2.10.4 취약점점검및조치 2.11.5 소스코드보안"
            )
            return

        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("ISMS-P 인증 증적 자료", styles["Title"]))
        team_name = getattr(data, "team_name", "")
        period_start = getattr(data, "period_start", "")
        period_end = getattr(data, "period_end", "")
        story.append(Paragraph(f"팀: {team_name}", styles["Normal"]))
        story.append(Paragraph(f"기간: {period_start} ~ {period_end}", styles["Normal"]))
        story.append(PageBreak())

        # 2.10.4 취약점 점검 및 조치
        story.append(Paragraph("2.10.4 취약점 점검 및 조치", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        total_scans = getattr(data, "total_scans", 0)
        total_vulns = getattr(data, "total_vulnerabilities", 0)
        resolved_vulns = getattr(data, "resolved_vulnerabilities", 0)
        resolution_rate = getattr(data, "resolution_rate", 0.0)
        avg_time = getattr(data, "avg_response_time_hours", 0.0)

        story.append(Paragraph(f"정기 취약점 점검 횟수: {total_scans}", styles["Normal"]))
        story.append(Paragraph(f"총 취약점: {total_vulns}", styles["Normal"]))
        story.append(Paragraph(f"조치 완료: {resolved_vulns}", styles["Normal"]))
        story.append(Paragraph(f"조치율: {resolution_rate:.1f}%", styles["Normal"]))
        story.append(Paragraph(f"평균 조치 소요 시간: {avg_time:.1f}h", styles["Normal"]))
        story.append(PageBreak())

        # 2.11.5 소스코드 보안
        story.append(Paragraph("2.11.5 소스코드 보안", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1))
        story.append(Spacer(1, 0.3 * cm))

        auto_patch_rate = getattr(data, "auto_patch_rate", 0.0)
        story.append(Paragraph(f"자동 보안 패치 적용률: {auto_patch_rate:.1f}%", styles["Normal"]))

        patch_prs = getattr(data, "patch_prs", [])
        if patch_prs:
            pr_data = [["저장소", "상태", "취약점 유형"]]
            for pr in patch_prs[:10]:
                pr_data.append([
                    pr.get("repo_name", ""),
                    pr.get("status", ""),
                    pr.get("vulnerability_type", ""),
                ])
            pr_table = Table(pr_data, colWidths=[6 * cm, 4 * cm, 6 * cm])
            pr_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]))
            story.append(pr_table)

        doc.build(story)

    def render_json(self, data: object, output_path: str) -> None:
        """ISMS JSON 증적 데이터를 생성한다."""
        output = {
            "report_type": "isms",
            "standard": "ISMS-P",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "team_name": getattr(data, "team_name", ""),
            "period_start": str(getattr(data, "period_start", "")),
            "period_end": str(getattr(data, "period_end", "")),
            "2_10_4": {
                "title": "취약점 점검 및 조치",
                "total_scans": getattr(data, "total_scans", 0),
                "total_vulnerabilities": getattr(data, "total_vulnerabilities", 0),
                "resolved": getattr(data, "resolved_vulnerabilities", 0),
                "resolution_rate": getattr(data, "resolution_rate", 0.0),
                "severity_distribution": getattr(data, "severity_distribution", {}),
                "unresolved_critical": getattr(data, "unresolved_critical", []),
            },
            "2_11_5": {
                "title": "소스코드 보안",
                "auto_patch_rate": getattr(data, "auto_patch_rate", 0.0),
                "patch_prs": getattr(data, "patch_prs", []),
            },
            "vulnerability_resolution": {
                "resolution_rate": getattr(data, "resolution_rate", 0.0),
                "avg_response_time_hours": getattr(data, "avg_response_time_hours", 0.0),
                "avg_resolution_days": round(
                    getattr(data, "avg_response_time_hours", 0.0) / 24, 2
                ),
            },
        }
        self._write_json(output, output_path)


# ──────────────────────────────────────────────────────────────
# 렌더러 팩토리
# ──────────────────────────────────────────────────────────────


def get_report_renderer(report_type: str) -> ReportRenderer:
    """report_type에 맞는 렌더러를 반환한다.

    Args:
        report_type: 리포트 유형 (ciso / csap / iso27001 / isms)

    Returns:
        해당 유형의 ReportRenderer 인스턴스

    Raises:
        ValueError: 지원하지 않는 report_type인 경우
    """
    renderers: dict[str, type[ReportRenderer]] = {
        "ciso": CISOReportRenderer,
        "csap": CSAPReportRenderer,
        "iso27001": ISO27001ReportRenderer,
        "isms": ISMSReportRenderer,
    }
    cls = renderers.get(report_type)
    if cls is None:
        raise ValueError(f"지원하지 않는 리포트 유형: {report_type}")
    return cls()
