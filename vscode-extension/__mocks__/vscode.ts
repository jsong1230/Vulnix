/**
 * vscode 모듈 Mock
 * - Jest 단위 테스트에서 vscode API를 직접 사용하지 않는 pure 로직 테스트 시 활용
 * - vscode 익스텐션 환경(ExtensionContext, DiagnosticCollection 등)을 시뮬레이션
 */

export enum DiagnosticSeverity {
  Error = 0,
  Warning = 1,
  Information = 2,
  Hint = 3,
}

export enum DiagnosticTag {
  Unnecessary = 1,
  Deprecated = 2,
}

export class Position {
  constructor(
    public readonly line: number,
    public readonly character: number
  ) {}
}

export class Range {
  public readonly start: Position;
  public readonly end: Position;

  constructor(
    startLineOrPosition: number | Position,
    startCharacter: number | Position,
    endLine?: number,
    endCharacter?: number
  ) {
    if (typeof startLineOrPosition === 'number' && typeof startCharacter === 'number') {
      this.start = new Position(startLineOrPosition, startCharacter);
      this.end = new Position(endLine ?? startLineOrPosition, endCharacter ?? startCharacter);
    } else if (startLineOrPosition instanceof Position && startCharacter instanceof Position) {
      this.start = startLineOrPosition;
      this.end = startCharacter;
    } else {
      this.start = new Position(0, 0);
      this.end = new Position(0, 0);
    }
  }
}

export class Diagnostic {
  public source?: string;
  public code?: string | number | { value: string | number; target: Uri };
  public tags?: DiagnosticTag[];

  constructor(
    public readonly range: Range,
    public readonly message: string,
    public readonly severity: DiagnosticSeverity = DiagnosticSeverity.Error
  ) {}
}

export class Uri {
  private constructor(
    public readonly scheme: string,
    public readonly path: string
  ) {}

  static file(path: string): Uri {
    return new Uri('file', path);
  }

  static parse(value: string): Uri {
    const [scheme, ...rest] = value.split('://');
    return new Uri(scheme ?? 'https', rest.join('://') ?? value);
  }

  toString(): string {
    return `${this.scheme}://${this.path}`;
  }

  get fsPath(): string {
    return this.path;
  }
}

export class TextEdit {
  constructor(
    public readonly range: Range,
    public readonly newText: string
  ) {}

  static replace(range: Range, newText: string): TextEdit {
    return new TextEdit(range, newText);
  }

  static insert(position: Position, newText: string): TextEdit {
    return new TextEdit(new Range(position, position), newText);
  }

  static delete(range: Range): TextEdit {
    return new TextEdit(range, '');
  }
}

export class WorkspaceEdit {
  private edits: Map<string, TextEdit[]> = new Map();

  set(uri: Uri, edits: TextEdit[]): void {
    this.edits.set(uri.toString(), edits);
  }

  get(uri: Uri): TextEdit[] {
    return this.edits.get(uri.toString()) ?? [];
  }

  has(uri: Uri): boolean {
    return this.edits.has(uri.toString());
  }
}

export enum CodeActionKind {
  Empty = '',
  QuickFix = 'quickfix',
  Refactor = 'refactor',
}

export class CodeAction {
  public edit?: WorkspaceEdit;
  public command?: { command: string; title: string; arguments?: unknown[] };

  constructor(
    public readonly title: string,
    public readonly kind?: CodeActionKind
  ) {}
}

// ExtensionContext.globalState 모의 구현
export class MockMemento {
  private storage: Map<string, unknown> = new Map();

  get<T>(key: string): T | undefined;
  get<T>(key: string, defaultValue: T): T;
  get<T>(key: string, defaultValue?: T): T | undefined {
    const value = this.storage.get(key) as T | undefined;
    return value !== undefined ? value : defaultValue;
  }

  async update(key: string, value: unknown): Promise<void> {
    if (value === undefined) {
      this.storage.delete(key);
    } else {
      this.storage.set(key, value);
    }
  }

  keys(): readonly string[] {
    return Array.from(this.storage.keys());
  }
}

export const window = {
  showErrorMessage: jest.fn(),
  showInformationMessage: jest.fn(),
  showWarningMessage: jest.fn(),
  createStatusBarItem: jest.fn(() => ({
    text: '',
    tooltip: '',
    command: '',
    show: jest.fn(),
    hide: jest.fn(),
    dispose: jest.fn(),
  })),
  createWebviewPanel: jest.fn(),
};

export const workspace = {
  getConfiguration: jest.fn((section?: string) => ({
    get: jest.fn((key: string, defaultValue?: unknown) => {
      const defaults: Record<string, unknown> = {
        'vulnix.serverUrl': 'https://api.vulnix.dev',
        'vulnix.apiKey': '',
        'vulnix.analyzeOnSave': true,
        'vulnix.severityFilter': 'all',
        serverUrl: 'https://api.vulnix.dev',
        apiKey: '',
        analyzeOnSave: true,
        severityFilter: 'all',
      };
      return defaults[key] ?? defaultValue;
    }),
    update: jest.fn(),
    has: jest.fn(),
    inspect: jest.fn(),
  })),
  applyEdit: jest.fn().mockResolvedValue(true),
  onDidSaveTextDocument: jest.fn(),
  onDidCloseTextDocument: jest.fn(),
  onDidChangeConfiguration: jest.fn(),
};

export const languages = {
  createDiagnosticCollection: jest.fn(() => ({
    set: jest.fn(),
    delete: jest.fn(),
    clear: jest.fn(),
    dispose: jest.fn(),
    forEach: jest.fn(),
    get: jest.fn(),
    has: jest.fn(),
  })),
  registerCodeActionsProvider: jest.fn(),
};

export const commands = {
  registerCommand: jest.fn(),
  executeCommand: jest.fn(),
};

export enum StatusBarAlignment {
  Left = 1,
  Right = 2,
}
