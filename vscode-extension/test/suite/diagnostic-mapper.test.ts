/**
 * diagnostic-mapper.test.ts
 * - mapFindingToDiagnostic() 함수 단위 테스트
 * - 설계서 섹션 5-3: Finding -> vscode.Diagnostic 변환 규칙 검증
 *
 * 인수조건 F-11:
 *   - 코드 작성 중 실시간 취약점 하이라이팅
 *   - 취약점 위치에 인라인 패치 제안 표시
 */

import { DiagnosticSeverity, DiagnosticTag, Range } from 'vscode';
import { mapFindingToDiagnostic } from '../../src/diagnostics/diagnostic-mapper';
import type { Finding } from '../../src/api/types';

// 테스트용 Finding 기본 객체
const baseFinding: Finding = {
  rule_id: 'python.sqlalchemy.security.sql-injection',
  severity: 'high',
  message: '사용자 입력이 SQL 쿼리에 직접 삽입됩니다.',
  file_path: 'src/api/routes/users.py',
  start_line: 42,
  end_line: 45,
  start_col: 8,
  end_col: 55,
  code_snippet: 'db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
  cwe_id: 'CWE-89',
  owasp_category: 'A03:2021 - Injection',
  vulnerability_type: 'sql_injection',
  is_false_positive_filtered: false,
};

describe('mapFindingToDiagnostic()', () => {
  describe('심각도(severity) 매핑', () => {
    it('critical 심각도는 DiagnosticSeverity.Error로 매핑된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'critical' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.severity).toBe(DiagnosticSeverity.Error);
    });

    it('high 심각도는 DiagnosticSeverity.Error로 매핑된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'high' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.severity).toBe(DiagnosticSeverity.Error);
    });

    it('medium 심각도는 DiagnosticSeverity.Warning으로 매핑된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'medium' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.severity).toBe(DiagnosticSeverity.Warning);
    });

    it('low 심각도는 DiagnosticSeverity.Information으로 매핑된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'low' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.severity).toBe(DiagnosticSeverity.Information);
    });
  });

  describe('Range 변환 (라인 번호 0-base 변환)', () => {
    it('start_line 1-base를 0-base로 변환하여 range.start.line에 설정한다', () => {
      // Arrange: API 응답은 1-base (line 42), vscode.Range는 0-base (line 41)
      const finding: Finding = {
        ...baseFinding,
        start_line: 42,
        end_line: 45,
        start_col: 8,
        end_col: 55,
      };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert: 1-base -> 0-base 변환 확인
      expect(diagnostic.range.start.line).toBe(41); // 42 - 1
      expect(diagnostic.range.end.line).toBe(44);   // 45 - 1
    });

    it('start_col과 end_col을 range의 character에 그대로 설정한다', () => {
      // Arrange
      const finding: Finding = {
        ...baseFinding,
        start_line: 10,
        end_line: 10,
        start_col: 4,
        end_col: 30,
      };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.range.start.character).toBe(4);
      expect(diagnostic.range.end.character).toBe(30);
    });

    it('단일 라인 취약점의 range가 올바르게 설정된다', () => {
      // Arrange: 단일 라인 (start_line == end_line)
      const finding: Finding = {
        ...baseFinding,
        start_line: 78,
        end_line: 78,
        start_col: 10,
        end_col: 40,
      };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.range.start.line).toBe(77);
      expect(diagnostic.range.end.line).toBe(77);
      expect(diagnostic.range).toBeInstanceOf(Range);
    });
  });

  describe('메시지 포맷', () => {
    it('메시지 형식이 "[Vulnix] {severity}: {message} ({cwe_id})"이다', () => {
      // Arrange
      const finding: Finding = {
        ...baseFinding,
        severity: 'high',
        message: '사용자 입력이 SQL 쿼리에 직접 삽입됩니다.',
        cwe_id: 'CWE-89',
      };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.message).toBe(
        '[Vulnix] high: 사용자 입력이 SQL 쿼리에 직접 삽입됩니다. (CWE-89)'
      );
    });

    it('critical 심각도 메시지 포맷이 올바르다', () => {
      // Arrange
      const finding: Finding = {
        ...baseFinding,
        severity: 'critical',
        message: '하드코딩된 비밀번호가 감지되었습니다.',
        cwe_id: 'CWE-259',
      };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.message).toBe(
        '[Vulnix] critical: 하드코딩된 비밀번호가 감지되었습니다. (CWE-259)'
      );
    });
  });

  describe('source 및 code 설정', () => {
    it('source는 "Vulnix"로 설정된다', () => {
      // Act
      const diagnostic = mapFindingToDiagnostic(baseFinding);

      // Assert
      expect(diagnostic.source).toBe('Vulnix');
    });

    it('code.value는 rule_id로 설정된다', () => {
      // Act
      const diagnostic = mapFindingToDiagnostic(baseFinding);

      // Assert
      const code = diagnostic.code as { value: string; target: unknown };
      expect(code.value).toBe('python.sqlalchemy.security.sql-injection');
    });

    it('code.target은 CWE URL로 설정된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, cwe_id: 'CWE-89' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      const code = diagnostic.code as { value: string; target: { toString: () => string } };
      expect(code.target.toString()).toContain('89');
    });
  });

  describe('DiagnosticTag 설정', () => {
    it('low 심각도 진단에는 DiagnosticTag.Unnecessary 태그가 설정된다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'low' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.tags).toContain(DiagnosticTag.Unnecessary);
    });

    it('high 심각도 진단에는 DiagnosticTag.Unnecessary 태그가 없다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, severity: 'high' };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert: high는 Unnecessary 태그 없음
      const hasUnnecessaryTag = diagnostic.tags?.includes(DiagnosticTag.Unnecessary) ?? false;
      expect(hasUnnecessaryTag).toBe(false);
    });
  });

  describe('경계값 테스트', () => {
    it('start_line이 1(최소값)이면 range.start.line은 0이다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, start_line: 1, end_line: 1 };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.range.start.line).toBe(0);
    });

    it('start_col이 0이면 range.start.character는 0이다', () => {
      // Arrange
      const finding: Finding = { ...baseFinding, start_col: 0, end_col: 0 };

      // Act
      const diagnostic = mapFindingToDiagnostic(finding);

      // Assert
      expect(diagnostic.range.start.character).toBe(0);
    });
  });
});
