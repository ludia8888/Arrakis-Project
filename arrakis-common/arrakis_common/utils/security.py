"""
공통 보안 유틸리티
패스워드 해싱, 토큰 생성 등의 보안 관련 기능
"""
import base64
import hashlib
import hmac
import secrets
from typing import Optional, Tuple

from cryptography.hazmat.backends import default_backend

# Production cryptography dependencies - required for RSA operations
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from passlib.context import CryptContext

CRYPTOGRAPHY_AVAILABLE = True

# 패스워드 해싱 컨텍스트
pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")


def hash_password(password: str) -> str:
    """패스워드 해싱"""
    if not password:
        raise ValueError("Password cannot be empty")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """패스워드 검증"""
    if not plain_password or not hashed_password:
        return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def generate_token(length: int = 32) -> str:
    """보안 토큰 생성"""
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """API 키 생성"""
    # 프리픽스 + 랜덤 토큰
    prefix = "ak"
    token = secrets.token_urlsafe(32)
    return f"{prefix}_{token}"


def generate_secret_key(length: int = 32) -> str:
    """시크릿 키 생성"""
    return secrets.token_hex(length)


def generate_salt(length: int = 16) -> str:
    """솔트 생성"""
    return secrets.token_hex(length)


def hash_data(data: str, algorithm: str = "sha256") -> str:
    """데이터 해싱"""
    if algorithm == "sha256":
        return hashlib.sha256(data.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def encode_base64(data: bytes) -> str:
    """Base64 인코딩"""
    return base64.b64encode(data).decode("utf-8")


def decode_base64(data: str) -> bytes:
    """Base64 디코딩"""
    return base64.b64decode(data.encode("utf-8"))


def constant_time_compare(val1: str, val2: str) -> bool:
    """상수 시간 문자열 비교 (타이밍 공격 방지)"""
    return secrets.compare_digest(val1, val2)


def generate_otp_secret() -> str:
    """OTP 시크릿 생성"""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")


def mask_sensitive_data(
    data: str, visible_start: int = 4, visible_end: int = 4, mask_char: str = "*"
) -> str:
    """민감한 데이터 마스킹"""
    if not data:
        return ""

    length = len(data)

    # 짧은 문자열은 전체 마스킹
    if length <= visible_start + visible_end:
        return mask_char * length

    # 시작과 끝 부분만 보이기
    masked_length = length - visible_start - visible_end
    return data[:visible_start] + (mask_char * masked_length) + data[-visible_end:]


def generate_csrf_token() -> str:
    """CSRF 토큰 생성"""
    return secrets.token_urlsafe(32)


def create_secure_filename(filename: str) -> str:
    """보안 파일명 생성"""
    import os
    import re

    # 파일명과 확장자 분리
    base, ext = os.path.splitext(filename)

    # 위험한 문자 제거
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"[-\s]+", "-", base)

    # 길이 제한
    base = base[:100]

    # 타임스탬프 추가
    import time

    timestamp = int(time.time())

    return f"{base}_{timestamp}{ext}"


def encrypt_data(data: str, key: str) -> str:
 """
 간단한 데이터 암호화 (개발용)
 프로덕션에서는 cryptography 라이브러리의 Fernet 사용 권장
 """
 # XOR 기반 간단한 암호화 (개발용)
 key_bytes = key.encode()
 data_bytes = data.encode()

 encrypted = bytearray()
 for i, byte in enumerate(data_bytes):
 key_byte = key_bytes[i % len(key_bytes)]
 encrypted.append(byte ^ key_byte)

 return encode_base64(bytes(encrypted))


def decrypt_data(encrypted_data: str, key: str) -> str:
 """
 간단한 데이터 복호화 (개발용)
 프로덕션에서는 cryptography 라이브러리의 Fernet 사용 권장
 """
 encrypted_bytes = decode_base64(encrypted_data)
 key_bytes = key.encode()

 decrypted = bytearray()
 for i, byte in enumerate(encrypted_bytes):
 key_byte = key_bytes[i % len(key_bytes)]
 decrypted.append(byte ^ key_byte)

 return decrypted.decode()


class RateLimiter:
 """간단한 Rate Limiter (메모리 기반)"""

 def __init__(self, max_requests: int = 100, window_seconds: int = 60):
 self.max_requests = max_requests
 self.window_seconds = window_seconds
 self._requests = {}

 def is_allowed(self, key: str) -> bool:
 """요청 허용 여부 확인"""
 import time

 now = time.time()

 # 오래된 요청 정리
 if key in self._requests:
 self._requests[key] = [
 timestamp
 for timestamp in self._requests[key]
 if now - timestamp < self.window_seconds
 ]
 else:
 self._requests[key] = []

 # 요청 수 확인
 if len(self._requests[key]) >= self.max_requests:
 return False

 # 요청 기록
 self._requests[key].append(now)
 return True


# HMAC 관련 함수들
def calculate_hmac(data: bytes, key: bytes, algorithm: str = "sha256") -> bytes:
 """HMAC 계산"""
 if algorithm == "sha256":
 return hmac.new(key, data, hashlib.sha256).digest()
 elif algorithm == "sha512":
 return hmac.new(key, data, hashlib.sha512).digest()
 else:
 raise ValueError(f"Unsupported HMAC algorithm: {algorithm}")


def verify_hmac(
 data: bytes, signature: bytes, key: bytes, algorithm: str = "sha256"
) -> bool:
 """HMAC 검증"""
 try:
 expected = calculate_hmac(data, key, algorithm)
 return hmac.compare_digest(signature, expected)
 except Exception:
 return False


# 호환성을 위한 추가 함수들 (common_security 대체)
def encrypt_text(text: str, key: Optional[str] = None) -> str:
 """텍스트 암호화 (common_security 호환)"""
 if key is None:
 key = generate_secret_key()
 return encrypt_data(text, key)


def decrypt_text(encrypted_text: str, key: str) -> str:
 """텍스트 복호화 (common_security 호환)"""
 return decrypt_data(encrypted_text, key)


# RSA 서명 관련 함수들 (cryptography 라이브러리 필요)
def generate_signing_key(key_size: int = 2048) -> str:
 """RSA 개인키 생성"""

 private_key = rsa.generate_private_key(
 public_exponent = 65537, key_size = key_size, backend = default_backend()
 )

 pem = private_key.private_bytes(
 encoding = serialization.Encoding.PEM,
 format = serialization.PrivateFormat.PKCS8,
 encryption_algorithm = serialization.NoEncryption(),
 )

 return pem.decode()


def sign(data: bytes, private_key: str) -> str:
 """RSA 서명"""

 # PEM 형식의 개인키 로드
 key = serialization.load_pem_private_key(
 private_key.encode(), password = None, backend = default_backend()
 )

 # PSS 패딩과 SHA256을 사용하여 서명
 signature = key.sign(
 data,
 padding.PSS(
 mgf = padding.MGF1(hashes.SHA256()), salt_length = padding.PSS.MAX_LENGTH
 ),
 hashes.SHA256(),
 )

 return base64.b64encode(signature).decode()


def verify_signature(data: bytes, signature: str, public_key: str) -> bool:
 """RSA 서명 검증"""

 try:
 # Base64 디코딩
 sig_bytes = base64.b64decode(signature)

 # PEM 형식의 공개키 로드
 key = serialization.load_pem_public_key(
 public_key.encode(), backend = default_backend()
 )

 # PSS 패딩과 SHA256을 사용하여 검증
 key.verify(
 sig_bytes,
 data,
 padding.PSS(
 mgf = padding.MGF1(hashes.SHA256()), salt_length = padding.PSS.MAX_LENGTH
 ),
 hashes.SHA256(),
 )
 return True
 except Exception:
 return False


def generate_rsa_keypair(key_size: int = 2048) -> Tuple[str, str]:
 """RSA 키 쌍 생성 (개인키, 공개키)"""

 private_key = rsa.generate_private_key(
 public_exponent = 65537, key_size = key_size, backend = default_backend()
 )

 # 개인키 PEM 형식
 private_pem = private_key.private_bytes(
 encoding = serialization.Encoding.PEM,
 format = serialization.PrivateFormat.PKCS8,
 encryption_algorithm = serialization.NoEncryption(),
 ).decode()

 # 공개키 PEM 형식
 public_key = private_key.public_key()
 public_pem = public_key.public_bytes(
 encoding = serialization.Encoding.PEM,
 format = serialization.PublicFormat.SubjectPublicKeyInfo,
 ).decode()

 return private_pem, public_pem
