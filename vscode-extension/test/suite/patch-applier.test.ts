/**
 * patch-applier.test.ts
 * - parseDiffToEdits() 함수 단위 테스트
 * - 설계서 섹션 5-3: 패치 diff를 WorkspaceEdit로 변환 (code-actions/patch-applier.ts) 검증
 *
 * 인수조건 F-11:
 *   - 패치 제안 수락 시 코드 자동 수정
 */

import { parseDiffToEdits } from '../../src/code-actions/patch-applier';
import { TextEdit, Range } from 'vscode';

describe('parseDiffToEdits()', () => {
  describe('단일 라인 교체 diff 파싱', () => {
    it('단일 라인 삭제 후 교체 diff를 TextEdit 배열로 변환한다', () => {
      // Arrange: 단일 라인 교체 unified diff
      // @@ -42,1 +42,1 @@ (42번 라인 1줄 교체)
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,1 +42,1 @@',
        '-    db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        '+    db.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert
      expect(edits).toBeDefined();
      expect(edits.length).toBeGreaterThan(0);
    });

    it('단일 라인 교체 시 TextEdit의 range가 올바른 라인을 가리킨다', () => {
      // Arrange: 42번 라인 교체 (0-base: 41번)
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,1 +42,1 @@',
        '-    old_code = "vulnerable"',
        '+    new_code = "safe"',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: range는 0-base, 42번 라인 -> index 41
      expect(edits[0]).toBeInstanceOf(TextEdit);
      expect(edits[0].range.start.line).toBe(41); // 1-base 42 -> 0-base 41
    });

    it('단일 라인 교체 시 TextEdit의 newText가 교체 내용을 포함한다', () => {
      // Arrange
      const newCode = '    db.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})';
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,1 +42,1 @@',
        '-    db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        `+${newCode}`,
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: newText에 교체 코드가 포함됨 (선행 '+' 제거됨)
      expect(edits[0].newText).toContain('db.execute(text(');
    });
  });

  describe('멀티 라인 diff 파싱', () => {
    it('멀티 라인 교체 diff를 TextEdit 배열로 변환한다', () => {
      // Arrange: 42~45번 라인 교체
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,4 +42,5 @@',
        '-    result = db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        '-    user = result.fetchone()',
        '-    if not user:',
        '-        return None',
        '+    stmt = text("SELECT * FROM users WHERE id = :user_id")',
        '+    result = db.execute(stmt, {"user_id": user_id})',
        '+    user = result.fetchone()',
        '+    if not user:',
        '+        return None',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert
      expect(edits).toBeDefined();
      expect(edits.length).toBeGreaterThan(0);
    });

    it('멀티 라인 diff에서 삭제된 라인의 range가 올바르게 설정된다', () => {
      // Arrange: 42~43번 라인 (2줄) 교체
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,2 +42,2 @@',
        '-    line_one_old()',
        '-    line_two_old()',
        '+    line_one_new()',
        '+    line_two_new()',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: 42~43 라인 범위 (0-base: 41~42)
      const firstEdit = edits[0];
      expect(firstEdit.range.start.line).toBe(41); // 1-base 42 -> 0-base 41
    });

    it('여러 hunk가 있는 diff를 파싱하면 여러 TextEdit를 반환한다', () => {
      // Arrange: 두 개의 hunk (서로 다른 위치 변경)
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -10,1 +10,1 @@',
        '-    password = "hardcoded"',
        '+    password = os.getenv("DB_PASSWORD")',
        '@@ -42,1 +42,1 @@',
        '-    db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        '+    db.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: 두 개의 hunk -> 두 개 이상의 TextEdit
      expect(edits.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('에러 케이스', () => {
    it('빈 diff 문자열을 전달하면 빈 배열을 반환한다', () => {
      // Act
      const edits = parseDiffToEdits('');

      // Assert
      expect(edits).toEqual([]);
    });

    it('hunk 헤더(@@ ... @@)가 없는 diff를 전달하면 빈 배열을 반환한다', () => {
      // Arrange: hunk 헤더 없는 잘못된 diff
      const invalidDiff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '-    old_code()',
        '+    new_code()',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(invalidDiff);

      // Assert
      expect(edits).toEqual([]);
    });
  });

  describe('경계값 테스트', () => {
    it('1번 라인 교체 diff를 파싱하면 range.start.line이 0이다', () => {
      // Arrange: 파일의 첫 번째 라인 교체
      const diff = [
        '--- a/src/config.py',
        '+++ b/src/config.py',
        '@@ -1,1 +1,1 @@',
        '-DB_PASSWORD = "admin123"',
        '+DB_PASSWORD = os.getenv("DB_PASSWORD", "")',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: 1번 라인 -> 0-base index 0
      expect(edits[0].range.start.line).toBe(0);
    });

    it('삭제만 있는 diff(추가 없음)를 파싱하면 빈 텍스트로 교체한다', () => {
      // Arrange: 라인 삭제 diff
      const diff = [
        '--- a/src/api/routes/users.py',
        '+++ b/src/api/routes/users.py',
        '@@ -42,1 +42,0 @@',
        '-    vulnerable_code()',
      ].join('\n');

      // Act
      const edits = parseDiffToEdits(diff);

      // Assert: 삭제 -> newText는 빈 문자열
      expect(edits.length).toBeGreaterThan(0);
      expect(edits[0].newText).toBe('');
    });
  });
});
