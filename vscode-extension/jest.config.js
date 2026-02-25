/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/test/suite'],
  testMatch: ['**/*.test.ts'],
  moduleNameMapper: {
    '^vscode$': '<rootDir>/__mocks__/vscode.ts',
  },
  transform: {
    '^.+\\.ts$': [
      'ts-jest',
      {
        // RED 단계: 구현 파일 없음 -> 런타임에서 모듈 not found 에러로 FAIL
        // 타입 컴파일 에러는 무시하고 런타임 에러를 통해 FAIL 확인
        diagnostics: false,
        tsconfig: {
          strict: true,
          esModuleInterop: true,
          moduleResolution: 'node',
          target: 'ES2020',
          module: 'commonjs',
          resolveJsonModule: true,
        },
      },
    ],
  },
  // 각 테스트 파일이 독립적으로 모듈을 로드하도록 설정
  resetModules: true,
};
