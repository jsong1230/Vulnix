/**
 * 패치 적용기
 * - unified diff 형식을 파싱하여 vscode.TextEdit 배열로 변환
 * - WorkspaceEdit를 통해 실제 문서에 패치 적용
 */

import * as vscode from 'vscode';

// hunk 정보 타입
interface Hunk {
  oldStart: number;  // 1-base
  oldCount: number;
  newStart: number;  // 1-base
  newCount: number;
  removedLines: string[];
  addedLines: string[];
}

/**
 * unified diff 헤더 파싱
 * "@@ -L,N +L,N @@" 형식
 */
function parseHunkHeader(line: string): Hunk | null {
  const match = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
  if (!match) return null;

  return {
    oldStart: parseInt(match[1], 10),
    oldCount: match[2] !== undefined ? parseInt(match[2], 10) : 1,
    newStart: parseInt(match[3], 10),
    newCount: match[4] !== undefined ? parseInt(match[4], 10) : 1,
    removedLines: [],
    addedLines: [],
  };
}

/**
 * unified diff 형식을 파싱하여 vscode.TextEdit 배열로 변환
 *
 * @param diff unified diff 문자열
 * @returns vscode.TextEdit 배열
 */
export function parseDiffToEdits(diff: string): vscode.TextEdit[] {
  if (!diff.trim()) {
    return [];
  }

  const lines = diff.split('\n');
  const edits: vscode.TextEdit[] = [];
  const hunks: Hunk[] = [];
  let currentHunk: Hunk | null = null;

  for (const line of lines) {
    if (line.startsWith('@@ ')) {
      // 이전 hunk 저장
      if (currentHunk) {
        hunks.push(currentHunk);
      }
      currentHunk = parseHunkHeader(line);
    } else if (currentHunk) {
      if (line.startsWith('-')) {
        currentHunk.removedLines.push(line.slice(1));
      } else if (line.startsWith('+')) {
        currentHunk.addedLines.push(line.slice(1));
      }
      // context 라인(공백 시작)은 무시
    }
  }

  // 마지막 hunk 저장
  if (currentHunk) {
    hunks.push(currentHunk);
  }

  // hunk가 없으면 빈 배열 반환
  if (hunks.length === 0) {
    return [];
  }

  // 각 hunk를 TextEdit으로 변환
  for (const hunk of hunks) {
    // 삭제 범위: oldStart ~ oldStart + oldCount - 1 (0-base 변환)
    const startLine = hunk.oldStart - 1; // 1-base → 0-base

    let endLine: number;
    let endChar: number;

    if (hunk.oldCount === 0) {
      // 삽입 전용 (삭제 없음)
      endLine = startLine;
      endChar = 0;
    } else {
      endLine = startLine + hunk.removedLines.length;
      endChar = 0;
    }

    const range = new vscode.Range(startLine, 0, endLine, endChar);

    // 새 텍스트 생성
    let newText: string;
    if (hunk.addedLines.length === 0) {
      // 삭제 전용: 빈 문자열
      newText = '';
    } else {
      newText = hunk.addedLines.join('\n');
    }

    edits.push(vscode.TextEdit.replace(range, newText));
  }

  return edits;
}

/**
 * 문서에 diff 패치 적용
 *
 * @param document vscode.TextDocument
 * @param diff unified diff 문자열
 * @returns 적용 성공 여부
 */
export async function applyPatch(document: vscode.TextDocument, diff: string): Promise<boolean> {
  const edits = parseDiffToEdits(diff);

  if (edits.length === 0) {
    return false;
  }

  const workspaceEdit = new vscode.WorkspaceEdit();
  workspaceEdit.set(document.uri, edits);

  return vscode.workspace.applyEdit(workspaceEdit);
}
