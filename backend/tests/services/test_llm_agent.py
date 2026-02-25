"""LLMAgent 단위 테스트 — F-02 RED 단계

구현이 완료되지 않은 상태에서 실행하면 모두 FAIL이어야 한다.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from src.services.llm_agent import LLMAgent, LLMAnalysisResult
from src.services.semgrep_engine import SemgrepFinding


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    """LLMAgent 인스턴스 픽스처.

    anthropic.Anthropic 생성자를 mock하여 외부 네트워크 연결 없이 테스트한다.
    """
    with patch("anthropic.Anthropic") as mock_sync_cls:
        mock_sync_cls.return_value = MagicMock()
        a = LLMAgent()

    # _client를 AsyncMock으로 완전히 교체
    mock_async_client = MagicMock()
    mock_async_client.messages = AsyncMock()
    a._client = mock_async_client
    return a


@pytest.fixture
def sql_injection_finding():
    """SQL Injection SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.python.sql_injection.string_format",
        severity="ERROR",
        file_path="app/db.py",
        start_line=5,
        end_line=5,
        code_snippet='cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
        message="SQL Injection 취약점 탐지: f-string 사용",
        cwe=["CWE-89"],
    )


@pytest.fixture
def xss_finding():
    """XSS SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.python.xss.flask_render_html",
        severity="ERROR",
        file_path="app/views.py",
        start_line=10,
        end_line=10,
        code_snippet="return make_response(user_input)",
        message="XSS 취약점 탐지: 사용자 입력 직접 반환",
        cwe=["CWE-79"],
    )


@pytest.fixture
def hardcoded_creds_finding():
    """Hardcoded Credentials SemgrepFinding 픽스처."""
    return SemgrepFinding(
        rule_id="vulnix.python.hardcoded_creds.password_assignment",
        severity="ERROR",
        file_path="config.py",
        start_line=3,
        end_line=3,
        code_snippet='DB_PASSWORD = "super_secret_password_123"',
        message="Hardcoded Credentials 탐지: 패스워드가 하드코딩됨",
        cwe=["CWE-798"],
    )


@pytest.fixture
def three_findings(sql_injection_finding, xss_finding, hardcoded_creds_finding):
    """3개의 SemgrepFinding 목록 픽스처."""
    return [sql_injection_finding, xss_finding, hardcoded_creds_finding]


@pytest.fixture
def sql_injection_code():
    """SQL Injection 취약 파일 내용 픽스처."""
    return '''import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()
'''


@pytest.fixture
def analysis_response_true_positive():
    """단일 진양성 결과를 담은 LLM 분석 응답 픽스처."""
    return json.dumps({
        "results": [
            {
                "rule_id": "vulnix.python.sql_injection.string_format",
                "is_true_positive": True,
                "confidence": 0.95,
                "severity": "High",
                "reasoning": "사용자 입력(user_id)이 f-string을 통해 SQL 쿼리에 직접 삽입되어 있어 SQL Injection 공격에 취약합니다.",
                "owasp_category": "A03:2021 - Injection",
                "vulnerability_type": "sql_injection",
            }
        ]
    })


@pytest.fixture
def analysis_response_false_positive():
    """오탐 결과를 담은 LLM 분석 응답 픽스처."""
    return json.dumps({
        "results": [
            {
                "rule_id": "vulnix.python.sql_injection.string_format",
                "is_true_positive": False,
                "confidence": 0.9,
                "severity": "Low",
                "reasoning": "해당 코드는 테스트 픽스처로, 실제 사용자 입력이 아닌 상수값을 사용합니다.",
                "owasp_category": None,
                "vulnerability_type": "sql_injection",
            }
        ]
    })


@pytest.fixture
def analysis_response_all_false_positives():
    """3건 모두 오탐 결과를 담은 LLM 분석 응답 픽스처."""
    return json.dumps({
        "results": [
            {
                "rule_id": "vulnix.python.sql_injection.string_format",
                "is_true_positive": False,
                "confidence": 0.85,
                "severity": "Low",
                "reasoning": "오탐으로 판단",
                "owasp_category": None,
                "vulnerability_type": "sql_injection",
            },
            {
                "rule_id": "vulnix.python.xss.flask_render_html",
                "is_true_positive": False,
                "confidence": 0.80,
                "severity": "Low",
                "reasoning": "오탐으로 판단",
                "owasp_category": None,
                "vulnerability_type": "xss",
            },
            {
                "rule_id": "vulnix.python.hardcoded_creds.password_assignment",
                "is_true_positive": False,
                "confidence": 0.75,
                "severity": "Low",
                "reasoning": "오탐으로 판단",
                "owasp_category": None,
                "vulnerability_type": "hardcoded_credentials",
            },
        ]
    })


@pytest.fixture
def patch_response():
    """패치 생성 LLM 응답 픽스처."""
    return json.dumps({
        "patch_diff": '--- a/app/db.py\n+++ b/app/db.py\n@@ -5,1 +5,1 @@\n-    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n+    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))',
        "patch_description": "f-string SQL 쿼리를 파라미터화된 쿼리로 변경합니다.",
        "references": ["https://cwe.mitre.org/data/definitions/89.html"],
    })


def _make_claude_message(text: str) -> MagicMock:
    """Claude API 응답 객체를 시뮬레이션하는 헬퍼."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ──────────────────────────────────────────────────────────────
# analyze_findings() 테스트
# ──────────────────────────────────────────────────────────────

async def test_analyze_findings_returns_results(
    agent,
    sql_injection_code,
    sql_injection_finding,
    analysis_response_true_positive,
    patch_response,
):
    """정상 분석 흐름에서 LLMAnalysisResult 목록을 반환한다."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        _make_claude_message(analysis_response_true_positive),
        _make_claude_message(patch_response),
    ])

    # Act
    results = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[sql_injection_finding],
    )

    # Assert
    assert isinstance(results, list)
    assert len(results) == 1
    assert isinstance(results[0], LLMAnalysisResult)
    assert results[0].is_true_positive is True
    assert results[0].severity.lower() in ("high", "critical", "medium", "low", "informational")


async def test_analyze_findings_filters_false_positives(
    agent,
    sql_injection_code,
    sql_injection_finding,
    analysis_response_false_positive,
):
    """LLM이 오탐으로 판정한 결과를 올바르게 필터링한다."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(
        return_value=_make_claude_message(analysis_response_false_positive)
    )

    # Act
    results = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[sql_injection_finding],
    )

    # Assert
    assert len(results) == 1
    assert results[0].is_true_positive is False
    # 오탐이면 패치를 생성하지 않으므로 patch_diff가 None
    assert results[0].patch_diff is None


async def test_analyze_findings_assigns_severity(
    agent,
    sql_injection_code,
    sql_injection_finding,
    analysis_response_true_positive,
    patch_response,
):
    """LLM이 심각도를 올바르게 분류한다 (Critical/High/Medium/Low/Informational)."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        _make_claude_message(analysis_response_true_positive),
        _make_claude_message(patch_response),
    ])

    # Act
    results = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[sql_injection_finding],
    )

    # Assert
    assert results[0].severity == "High"


async def test_analyze_findings_empty_input_returns_empty(agent, sql_injection_code):
    """빈 findings 입력 시 LLM을 호출하지 않고 빈 리스트를 반환한다."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock()

    # Act
    results = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[],
    )

    # Assert
    assert results == []
    # LLM 호출이 없어야 함
    agent._client.messages.create.assert_not_called()


async def test_analyze_findings_rate_limit_retry(
    agent,
    sql_injection_code,
    sql_injection_finding,
    analysis_response_true_positive,
    patch_response,
):
    """RateLimitError 발생 시 재시도하여 정상 응답을 반환한다."""
    # Arrange: 1회 rate limit 후 2회째 정상 응답
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"type": "rate_limit_error"}},
        ),
        _make_claude_message(analysis_response_true_positive),
        _make_claude_message(patch_response),
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        results = await agent.analyze_findings(
            file_content=sql_injection_code,
            file_path="app/db.py",
            findings=[sql_injection_finding],
        )

    # Assert
    assert len(results) == 1
    assert results[0].is_true_positive is True


async def test_analyze_findings_maps_cwe_owasp(
    agent,
    sql_injection_code,
    sql_injection_finding,
    analysis_response_true_positive,
    patch_response,
):
    """분석 결과에 CWE/OWASP 매핑이 포함된다."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        _make_claude_message(analysis_response_true_positive),
        _make_claude_message(patch_response),
    ])

    # Act
    results = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[sql_injection_finding],
    )

    # Assert
    result = results[0]
    # owasp_category 또는 references에 OWASP/CWE 정보가 포함되어야 함
    assert hasattr(result, "owasp_category") or len(result.references) > 0


# ──────────────────────────────────────────────────────────────
# _generate_patch() 테스트
# ──────────────────────────────────────────────────────────────

async def test_generate_patch_returns_diff(
    agent,
    sql_injection_finding,
    sql_injection_code,
    patch_response,
):
    """패치 생성 시 unified diff 형식 문자열을 반환한다."""
    # Arrange
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(
        return_value=_make_claude_message(patch_response)
    )

    # Act
    patch_diff = await agent._generate_patch(
        finding=sql_injection_finding,
        file_content=sql_injection_code,
    )

    # Assert
    assert patch_diff is not None
    assert isinstance(patch_diff, str)
    # unified diff 형식 확인 (--- 또는 +++ 포함)
    assert "---" in patch_diff or "+++" in patch_diff


async def test_generate_patch_returns_none_when_not_possible(
    agent,
    sql_injection_finding,
    sql_injection_code,
):
    """패치 생성이 불가능하면 None을 반환한다."""
    # Arrange: 패치 불가 응답
    no_patch_response = json.dumps({
        "patch_diff": None,
        "patch_description": "이 취약점은 자동 패치가 어렵습니다.",
        "references": [],
    })
    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(
        return_value=_make_claude_message(no_patch_response)
    )

    # Act
    patch_diff = await agent._generate_patch(
        finding=sql_injection_finding,
        file_content=sql_injection_code,
    )

    # Assert
    assert patch_diff is None


# ──────────────────────────────────────────────────────────────
# _parse_analysis_response() 테스트
# ──────────────────────────────────────────────────────────────

def test_parse_analysis_response_valid_json(agent, analysis_response_true_positive):
    """올바른 JSON 응답을 파싱하여 결과 목록을 반환한다."""
    # Act
    parsed = agent._parse_analysis_response(analysis_response_true_positive)

    # Assert
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["is_true_positive"] is True
    assert parsed[0]["severity"] == "High"


def test_parse_analysis_response_json_with_code_block(agent):
    """```json 래퍼로 감싼 JSON 응답도 정상 파싱한다."""
    # Arrange
    wrapped_json = '```json\n{"results": [{"rule_id": "test", "is_true_positive": true, "confidence": 0.9, "severity": "High", "reasoning": "test"}]}\n```'

    # Act
    parsed = agent._parse_analysis_response(wrapped_json)

    # Assert
    assert len(parsed) == 1
    assert parsed[0]["rule_id"] == "test"


def test_parse_analysis_response_invalid_json_returns_empty(agent):
    """자연어 응답(JSON 아님)은 경고 로그를 남기고 빈 목록을 반환한다."""
    # Arrange
    natural_language_response = "이 코드에는 SQL Injection 취약점이 있습니다. 파라미터화된 쿼리를 사용하세요."

    # Act
    result = agent._parse_analysis_response(natural_language_response)

    # Assert
    assert result == []


# ──────────────────────────────────────────────────────────────
# 파일별 배치 처리 테스트
# ──────────────────────────────────────────────────────────────

async def test_batch_processing_by_file(
    agent,
    sql_injection_finding,
    xss_finding,
    sql_injection_code,
):
    """파일별로 findings를 그룹화하여 LLM을 배치 호출한다."""
    # Arrange: 두 findings가 다른 파일에 있음
    # sql_injection_finding -> app/db.py
    # xss_finding -> app/views.py

    xss_content = '''from flask import request, make_response
def render_name():
    user_input = request.args.get("name")
    return make_response(user_input)
'''

    analysis_for_db = json.dumps({
        "results": [{
            "rule_id": "vulnix.python.sql_injection.string_format",
            "is_true_positive": True,
            "confidence": 0.95,
            "severity": "High",
            "reasoning": "SQL Injection 취약점",
            "owasp_category": "A03:2021 - Injection",
            "vulnerability_type": "sql_injection",
        }]
    })

    analysis_for_views = json.dumps({
        "results": [{
            "rule_id": "vulnix.python.xss.flask_render_html",
            "is_true_positive": True,
            "confidence": 0.90,
            "severity": "Medium",
            "reasoning": "XSS 취약점",
            "owasp_category": "A03:2021 - Injection",
            "vulnerability_type": "xss",
        }]
    })

    patch_diff = json.dumps({
        "patch_diff": "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-bad\n+good",
        "patch_description": "수정됨",
        "references": [],
    })

    agent._client.messages = AsyncMock()
    # 2개 파일 x (1차 분석 + 2차 패치) = 최대 4번 호출
    agent._client.messages.create = AsyncMock(side_effect=[
        _make_claude_message(analysis_for_db),
        _make_claude_message(patch_diff),
        _make_claude_message(analysis_for_views),
        _make_claude_message(patch_diff),
    ])

    # Act: db.py에 대한 분석 실행
    results_db = await agent.analyze_findings(
        file_content=sql_injection_code,
        file_path="app/db.py",
        findings=[sql_injection_finding],
    )

    # Assert
    assert len(results_db) == 1
    assert results_db[0].is_true_positive is True


# ──────────────────────────────────────────────────────────────
# _call_claude_with_retry() 테스트
# ──────────────────────────────────────────────────────────────

async def test_call_claude_with_retry_rate_limit_success(agent):
    """Rate limit 후 재시도하여 성공하면 정상 응답 텍스트를 반환한다."""
    # Arrange: 1회 RateLimitError 후 2회째 성공
    success_response = _make_claude_message('{"results": []}')

    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        anthropic.RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429),
            body={"error": {"type": "rate_limit_error"}},
        ),
        success_response,
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        result = await agent._call_claude_with_retry(
            messages=[{"role": "user", "content": "test"}]
        )

    # Assert
    assert result == '{"results": []}'


async def test_call_claude_with_retry_max_retries_exceeded(agent):
    """최대 재시도 횟수를 초과하면 RateLimitError를 발생시킨다."""
    # Arrange: 4회 연속 RateLimitError
    rate_limit_error = anthropic.RateLimitError(
        message="Rate limit",
        response=MagicMock(status_code=429),
        body={"error": {"type": "rate_limit_error"}},
    )

    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        rate_limit_error,
        rate_limit_error,
        rate_limit_error,
        rate_limit_error,
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act & Assert
        with pytest.raises(anthropic.RateLimitError):
            await agent._call_claude_with_retry(
                messages=[{"role": "user", "content": "test"}],
                max_retries=3,
            )


async def test_call_claude_with_retry_server_error_retries(agent):
    """서버 에러(500) 후 재시도하여 성공하면 정상 응답을 반환한다."""
    # Arrange: 1회 500 에러 후 성공
    success_response = _make_claude_message('{"results": []}')

    mock_http_response = MagicMock()
    mock_http_response.status_code = 500

    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(side_effect=[
        anthropic.APIStatusError(
            message="Internal Server Error",
            response=mock_http_response,
            body={"error": {"type": "server_error"}},
        ),
        success_response,
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Act
        result = await agent._call_claude_with_retry(
            messages=[{"role": "user", "content": "test"}]
        )

    # Assert
    assert result == '{"results": []}'


async def test_call_claude_with_retry_4xx_no_retry(agent):
    """4xx 에러(401 등)는 재시도 없이 즉시 APIStatusError를 발생시킨다."""
    # Arrange
    mock_http_response = MagicMock()
    mock_http_response.status_code = 401

    agent._client.messages = AsyncMock()
    agent._client.messages.create = AsyncMock(
        side_effect=anthropic.APIStatusError(
            message="Unauthorized",
            response=mock_http_response,
            body={"error": {"type": "authentication_error"}},
        )
    )

    # Act & Assert
    with pytest.raises(anthropic.APIStatusError):
        await agent._call_claude_with_retry(
            messages=[{"role": "user", "content": "test"}]
        )

    # 재시도 없이 1번만 호출되어야 함
    assert agent._client.messages.create.call_count == 1


# ──────────────────────────────────────────────────────────────
# _prepare_file_content() 테스트
# ──────────────────────────────────────────────────────────────

def test_prepare_file_content_short_file_returns_full(agent, sql_injection_finding):
    """500줄 이하 파일은 전체 내용을 반환한다."""
    # Arrange: 200줄짜리 파일
    content = "\n".join(f"line {i}" for i in range(200))
    findings = [sql_injection_finding]

    # Act
    result = agent._prepare_file_content(content, findings)

    # Assert
    assert result == content


def test_prepare_file_content_long_file_trims_to_relevant(agent):
    """500줄 초과 파일은 취약점 주변 라인만 반환한다."""
    # Arrange: 1000줄짜리 파일, 취약점은 400번째 줄
    lines = [f"line {i}" for i in range(1000)]
    content = "\n".join(lines)

    finding = SemgrepFinding(
        rule_id="vulnix.python.sql_injection.string_format",
        severity="ERROR",
        file_path="app.py",
        start_line=400,
        end_line=400,
        code_snippet="line 400",
        message="취약점",
        cwe=["CWE-89"],
    )

    # Act
    result = agent._prepare_file_content(content, [finding])

    # Assert
    # 전체 내용이 아님
    assert result != content
    # 400번 줄 근방 내용은 포함되어야 함
    assert "line 399" in result or "line 400" in result or "line 401" in result


def test_prepare_file_content_long_file_with_many_findings_returns_full(agent):
    """500줄 초과이지만 findings가 5개 이상이면 전체를 반환한다."""
    # Arrange: 800줄 파일 + findings 6건
    content = "\n".join(f"line {i}" for i in range(800))

    findings = [
        SemgrepFinding(
            rule_id=f"vulnix.python.some_rule.{i}",
            severity="ERROR",
            file_path="app.py",
            start_line=i * 100,
            end_line=i * 100,
            code_snippet=f"line {i * 100}",
            message="취약점",
            cwe=["CWE-89"],
        )
        for i in range(1, 7)  # 6건
    ]

    # Act
    result = agent._prepare_file_content(content, findings)

    # Assert
    assert result == content
