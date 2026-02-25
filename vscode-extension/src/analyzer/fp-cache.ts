/**
 * 오탐(False Positive) 패턴 캐시
 * - 서버에서 받아온 오탐 패턴을 로컬에 캐시
 * - glob 패턴 매칭으로 finding 필터링
 */

import { minimatch } from 'minimatch';

// FalsePositivePattern 재export (fp-cache.test.ts에서 이 파일에서 import함)
export type { FalsePositivePattern } from '../api/types';
import type { FalsePositivePattern } from '../api/types';
import type { Finding } from '../api/types';
import type { ApiClient } from '../api/client';

// FP 패턴 주기적 동기화 간격 (5분)
const SYNC_INTERVAL_MS = 5 * 60 * 1000;

// globalState 인터페이스 (vscode.Memento 하위 호환)
interface GlobalState {
  get(key: string): unknown;
  update(key: string, value: unknown): Promise<void>;
}

const STORAGE_KEY = 'vulnix.fpPatterns';

export class FPCache {
  private patterns: FalsePositivePattern[] = [];
  private readonly globalState: GlobalState;

  // ETag 캐시 (304 Not Modified 최적화)
  private currentEtag: string | undefined;

  constructor(globalState: GlobalState) {
    this.globalState = globalState;
    // globalState에서 이전에 저장된 패턴 복원
    const stored = globalState.get(STORAGE_KEY) as FalsePositivePattern[] | undefined;
    if (stored && Array.isArray(stored)) {
      this.patterns = stored;
    }
  }

  /**
   * 패턴 목록 동기식 로드 및 저장
   * globalState에도 영속화
   */
  loadPatterns(patterns: FalsePositivePattern[]): void {
    this.patterns = patterns;
    // 비동기 저장 (에러 무시)
    void this.globalState.update(STORAGE_KEY, patterns);
  }

  /**
   * 비동기 패턴 업데이트
   */
  async update(patterns: FalsePositivePattern[]): Promise<void> {
    this.patterns = patterns;
    await this.globalState.update(STORAGE_KEY, patterns);
  }

  /**
   * finding이 오탐 패턴에 매칭되는지 확인
   * - is_active === true 패턴만 고려
   * - semgrep_rule_id 완전 일치 AND (file_pattern 없거나 glob 매칭)
   */
  matchesAny(finding: { rule_id: string; file_path?: string }): boolean {
    const activePatterns = this.patterns.filter(p => p.is_active);

    for (const pattern of activePatterns) {
      // rule_id 완전 일치 확인
      if (pattern.semgrep_rule_id !== finding.rule_id) {
        continue;
      }

      // file_pattern이 없으면 rule_id만으로 매칭
      if (!pattern.file_pattern) {
        return true;
      }

      // file_path가 없으면 file_pattern 없는 경우에만 매칭됨 (이미 위에서 처리)
      if (!finding.file_path) {
        continue;
      }

      // glob 패턴 매칭
      if (minimatch(finding.file_path, pattern.file_pattern)) {
        return true;
      }
    }

    return false;
  }

  /**
   * 현재 캐시된 패턴 목록 반환
   */
  getPatterns(): FalsePositivePattern[] {
    return this.patterns;
  }

  /**
   * 서버에서 FP 패턴 동기화
   * - ETag 기반 조건부 요청 (304 시 스킵)
   * - 200 응답 시 패턴 업데이트
   */
  async sync(client: ApiClient): Promise<void> {
    try {
      const result = await client.getFalsePositivePatterns(this.currentEtag);
      if (result.notModified) {
        // 304 Not Modified: 변경 없으므로 스킵
        return;
      }
      // 새 패턴 업데이트 및 ETag 갱신
      await this.update(result.patterns);
      this.currentEtag = result.etag;
    } catch {
      // 동기화 실패 시 무시 (기존 캐시 유지)
    }
  }

  /**
   * FP 패턴 주기적 동기화 시작 (5분 간격)
   * - activate() 시점에 호출
   */
  syncPeriodically(client: ApiClient): void {
    setInterval(() => {
      void this.sync(client);
    }, SYNC_INTERVAL_MS);
  }
}
