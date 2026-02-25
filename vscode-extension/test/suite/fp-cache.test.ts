/**
 * fp-cache.test.ts
 * - FPCache 클래스 단위 테스트
 * - 설계서 섹션 5-3: 오탐 패턴 캐시 (analyzer/fp-cache.ts) 검증
 *
 * 인수조건 F-11:
 *   - Vulnix 서버 연동하여 팀 오탐 규칙 동기화
 */

import { FPCache, FalsePositivePattern } from '../../src/analyzer/fp-cache';
import { MockMemento } from '../../__mocks__/vscode';
import type { Finding } from '../../src/api/types';

// 테스트용 Finding 기본 객체
const baseFinding: Finding = {
  rule_id: 'python.flask.security.xss',
  severity: 'medium',
  message: '사용자 입력이 HTML에 이스케이프 없이 삽입됩니다.',
  file_path: 'tests/conftest.py',
  start_line: 10,
  end_line: 10,
  start_col: 0,
  end_col: 40,
  code_snippet: 'return render_template_string(user_input)',
  cwe_id: 'CWE-79',
  owasp_category: 'A03:2021 - Injection',
  vulnerability_type: 'xss',
  is_false_positive_filtered: false,
};

// 테스트용 오탐 패턴 목록
const activePatterns: FalsePositivePattern[] = [
  {
    id: '550e8400-e29b-41d4-a716-446655440001',
    semgrep_rule_id: 'python.flask.security.xss',
    file_pattern: 'tests/**',
    reason: '테스트 코드에서 XSS 탐지 무시',
    is_active: true,
    updated_at: '2026-02-25T10:00:00Z',
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440002',
    semgrep_rule_id: 'python.secrets.hardcoded-password',
    file_pattern: 'tests/fixtures/**',
    reason: '테스트 픽스처에서 하드코딩 비밀번호 허용',
    is_active: true,
    updated_at: '2026-02-25T10:00:00Z',
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440003',
    semgrep_rule_id: 'python.logging.sensitive-data',
    file_pattern: 'scripts/**',
    reason: '배포 스크립트에서 로깅 허용',
    is_active: false, // 비활성 패턴
    updated_at: '2026-02-24T09:00:00Z',
  },
];

describe('FPCache', () => {
  let mockStorage: MockMemento;
  let fpCache: FPCache;

  beforeEach(() => {
    // Arrange: 매 테스트마다 깨끗한 스토리지로 초기화
    mockStorage = new MockMemento();
    fpCache = new FPCache(mockStorage);
  });

  describe('matchesAny(finding): rule_id 완전 일치 매칭', () => {
    it('rule_id가 정확히 일치하는 활성 패턴이 있으면 true를 반환한다', () => {
      // Arrange: 패턴 캐시에 xss 패턴 로드
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security.xss',
        file_path: 'tests/conftest.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(true);
    });

    it('rule_id가 일치하지 않으면 false를 반환한다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.sqlalchemy.security.sql-injection', // 패턴에 없는 rule_id
        file_path: 'tests/conftest.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(false);
    });

    it('rule_id가 부분 일치해도 false를 반환한다 (완전 일치만 허용)', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security', // 접두어만 일치 (부분 일치)
        file_path: 'tests/conftest.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert: 부분 일치는 허용하지 않음
      expect(result).toBe(false);
    });
  });

  describe('matchesAny(finding): file_pattern glob 매칭', () => {
    it('"tests/**" 패턴이 "tests/conftest.py" 경로에 매칭된다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security.xss',
        file_path: 'tests/conftest.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(true);
    });

    it('"tests/**" 패턴이 "tests/unit/test_api.py" 경로에 매칭된다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security.xss',
        file_path: 'tests/unit/test_api.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert: tests/** 는 하위 디렉토리도 매칭
      expect(result).toBe(true);
    });

    it('"tests/**" 패턴이 "src/api/routes.py" 경로에 매칭되지 않는다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security.xss',
        file_path: 'src/api/routes.py', // tests/ 하위가 아님
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(false);
    });

    it('"tests/fixtures/**" 패턴이 "tests/fixtures/sample.py" 경로에 매칭된다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.secrets.hardcoded-password',
        file_path: 'tests/fixtures/sample.py',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(true);
    });

    it('"tests/fixtures/**" 패턴이 "tests/conftest.py" 경로에 매칭되지 않는다', () => {
      // Arrange
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.secrets.hardcoded-password',
        file_path: 'tests/conftest.py', // fixtures/ 하위가 아님
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(false);
    });
  });

  describe('비활성 패턴 무시', () => {
    it('is_active가 false인 패턴은 매칭에서 제외된다', () => {
      // Arrange: python.logging.sensitive-data는 is_active=false
      fpCache.loadPatterns(activePatterns);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.logging.sensitive-data',
        file_path: 'scripts/deploy.sh',
      };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert: 비활성 패턴이므로 false
      expect(result).toBe(false);
    });

    it('패턴이 없으면 항상 false를 반환한다', () => {
      // Arrange: 빈 패턴 목록
      fpCache.loadPatterns([]);
      const finding: Finding = { ...baseFinding };

      // Act
      const result = fpCache.matchesAny(finding);

      // Assert
      expect(result).toBe(false);
    });
  });

  describe('globalState 기반 영속성', () => {
    it('loadPatterns() 후 globalState에 패턴이 저장된다', () => {
      // Arrange & Act
      fpCache.loadPatterns(activePatterns);

      // Assert: globalState에 저장됨을 확인
      const stored = mockStorage.get<FalsePositivePattern[]>('vulnix.fpPatterns');
      expect(stored).toBeDefined();
      expect(stored?.length).toBe(activePatterns.length);
    });

    it('새로운 FPCache 인스턴스가 globalState에서 패턴을 복원한다', () => {
      // Arrange: 첫 번째 인스턴스에서 패턴 저장
      fpCache.loadPatterns(activePatterns);

      // Act: 동일 스토리지로 새 인스턴스 생성
      const newFpCache = new FPCache(mockStorage);
      const finding: Finding = {
        ...baseFinding,
        rule_id: 'python.flask.security.xss',
        file_path: 'tests/conftest.py',
      };

      // Assert: 복원된 패턴으로 매칭
      expect(newFpCache.matchesAny(finding)).toBe(true);
    });
  });
});
