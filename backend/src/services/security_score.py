"""보안 점수 계산 유틸리티 (F-07 설계서 공식 통일)"""


def calc_security_score(critical: int, high: int, medium: int, low: int) -> float:
    """F-07 설계서 공식에 따라 보안 점수를 계산한다.

    score = max(0, 100 - (critical*25 + high*10 + medium*5 + low*1))
    open 상태 취약점 수를 각 인자로 전달해야 한다.

    Args:
        critical: open 상태 critical 취약점 수
        high: open 상태 high 취약점 수
        medium: open 상태 medium 취약점 수
        low: open 상태 low 취약점 수

    Returns:
        0.0 ~ 100.0 범위의 보안 점수
    """
    return max(0.0, 100.0 - (critical * 25 + high * 10 + medium * 5 + low * 1))
