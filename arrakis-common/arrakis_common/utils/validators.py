"""
공통 검증 유틸리티
이메일, 패스워드, 전화번호 등의 검증 로직
"""

import re
from typing import Any, Dict, List, Optional


def validate_email(email: str) -> bool:
    """이메일 형식 검증"""
    if not email:
        return False

    # RFC 5322 기반 이메일 정규식 (간소화 버전)
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        return False

    # 추가 검증
    if email.count("@") != 1:
        return False

    local, domain = email.split("@")

    # 로컬 파트 검증
    if not local or len(local) > 64:
        return False

    # 도메인 파트 검증
    if not domain or len(domain) > 255:
        return False

    # 연속된 점 검사
    if ".." in email:
        return False

    return True


def validate_password(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = True,
) -> Dict[str, Any]:
    """
    패스워드 강도 검증

    Returns:
        Dict with 'valid' (bool) and 'issues' (List[str])
    """
    issues = []

    if not password:
        return {"valid": False, "issues": ["Password is required"]}

    # 길이 검사
    if len(password) < min_length:
        issues.append(f"Password must be at least {min_length} characters long")

    # 대문자 검사
    if require_uppercase and not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")

    # 소문자 검사
    if require_lowercase and not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")

    # 숫자 검사
    if require_digit and not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one digit")

    # 특수문자 검사
    if require_special:
        special_chars = r"!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            issues.append("Password must contain at least one special character")

    # 일반적인 약한 패스워드 검사
    weak_passwords = [
        "password",
        "12345678",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "letmein",
        "welcome",
        "123456789",
        "password1",
    ]

    if password.lower() in weak_passwords:
        issues.append("Password is too common. Please choose a stronger password")

    return {"valid": len(issues) == 0, "issues": issues}


def validate_phone(phone: str, country_code: Optional[str] = None) -> bool:
    """
    전화번호 형식 검증

    Args:
        phone: 전화번호 문자열
        country_code: 국가 코드 (예: 'KR', 'US')
    """
    if not phone:
        return False

    # 숫자와 일부 특수문자만 허용
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)

    if not cleaned.isdigit():
        return False

    # 국가별 검증
    if country_code == "KR":
        # 한국 전화번호 (010-xxxx-xxxx 형식)
        pattern = r"^(010|011|016|017|018|019)\d{7,8}$"
        return bool(re.match(pattern, cleaned))

    elif country_code == "US":
        # 미국 전화번호 (xxx-xxx-xxxx 형식)
        pattern = r"^1?\d{10}$"
        return bool(re.match(pattern, cleaned))

    else:
        # 기본 검증: 7-15자리 숫자
        return 7 <= len(cleaned) <= 15


def validate_username(
    username: str,
    min_length: int = 3,
    max_length: int = 30,
    allow_special: bool = False,
) -> Dict[str, Any]:
    """사용자명 검증"""
    issues = []

    if not username:
        return {"valid": False, "issues": ["Username is required"]}

    # 길이 검사
    if len(username) < min_length:
        issues.append(f"Username must be at least {min_length} characters long")

    if len(username) > max_length:
        issues.append(f"Username must be no more than {max_length} characters long")

    # 문자 검사
    if allow_special:
        pattern = r"^[a-zA-Z0-9_\-\.]+$"
    else:
        pattern = r"^[a-zA-Z0-9_]+$"

    if not re.match(pattern, username):
        if allow_special:
            issues.append(
                "Username can only contain letters, numbers, underscore, hyphen, "
                "and dot"
            )
        else:
            issues.append("Username can only contain letters, numbers, and underscore")

    # 시작 문자 검사
    if username and not username[0].isalnum():
        issues.append("Username must start with a letter or number")

    # 예약어 검사
    reserved_words = [
        "admin",
        "root",
        "system",
        "administrator",
        "moderator",
        "support",
        "api",
        "www",
        "mail",
        "ftp",
        "test",
    ]

    if username.lower() in reserved_words:
        issues.append("This username is reserved and cannot be used")

    return {"valid": len(issues) == 0, "issues": issues}


def validate_url(url: str) -> bool:
    """URL 형식 검증"""
    if not url:
        return False

    # URL 정규식
    pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return bool(pattern.match(url))


def validate_date(date_string: str, format: str = "%Y-%m-%d") -> bool:
    """날짜 형식 검증"""
    if not date_string:
        return False

    try:
        from datetime import datetime

        datetime.strptime(date_string, format)
        return True
    except ValueError:
        return False


def sanitize_input(
    input_string: str, max_length: Optional[int] = None, allow_html: bool = False
) -> str:
    """입력값 정제"""
    if not input_string:
        return ""

    # 길이 제한
    if max_length:
        input_string = input_string[:max_length]

    # HTML 태그 제거
    if not allow_html:
        # 간단한 HTML 제거 (프로덕션에서는 bleach 등 사용 권장)
        input_string = re.sub(r"<[^>]+>", "", input_string)

    # 위험한 문자 이스케이프
    dangerous_chars = {
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    for char, escape in dangerous_chars.items():
        input_string = input_string.replace(char, escape)

    # 공백 정리
    input_string = " ".join(input_string.split())

    return input_string.strip()
