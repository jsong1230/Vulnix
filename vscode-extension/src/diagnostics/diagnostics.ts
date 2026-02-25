/**
 * 진단 컬렉션 관리자
 * - vscode.DiagnosticCollection을 래핑하여 Finding 기반 진단 관리
 */

import * as vscode from 'vscode';
import type { Finding } from '../api/types';
import { mapFindingToDiagnostic } from './diagnostic-mapper';

export class DiagnosticsManager {
  private readonly collection: vscode.DiagnosticCollection;

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection('vulnix');
  }

  /**
   * 특정 파일의 진단 업데이트
   */
  update(uri: vscode.Uri, findings: Finding[]): void {
    const diagnostics = findings.map(mapFindingToDiagnostic);
    this.collection.set(uri, diagnostics);
  }

  /**
   * 특정 파일의 진단 제거
   */
  clearFor(uri: vscode.Uri): void {
    this.collection.delete(uri);
  }

  /**
   * 모든 진단 제거
   */
  clearAll(): void {
    this.collection.clear();
  }

  /**
   * 리소스 해제
   */
  dispose(): void {
    this.collection.dispose();
  }
}
