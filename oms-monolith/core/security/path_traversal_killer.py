"""
🔥 완전한 Path Traversal 차단 시스템
모든 변형과 우회 기법을 완벽 차단
"""
import os
import re
import urllib.parse
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


class PathTraversalKiller:
    """Path Traversal 공격 완전 차단"""
    
    def __init__(self):
        self.attack_patterns = [
            # 기본 패턴
            r'\.\.[\\/]',
            r'[\\/]\.\.',
            
            # 단일 인코딩
            r'%2e%2e%2f',
            r'%2e%2e%5c',
            r'\.\.%2f',
            r'\.\.%5c',
            
            # 이중 인코딩
            r'%252e%252e%252f',
            r'%252e%252e%255c',
            r'%252e%252e',
            
            # 삼중 인코딩
            r'%25252e%25252e%25252f',
            
            # 유니코드 인코딩
            r'%c0%ae%c0%ae%c0%af',
            r'%c1%9c%c1%9c%c0%af',
            
            # 경로 압축 변형
            r'\.{2,}[\\/]',
            r'\.{3,}[\\/]{2,}',
            r'\.{4,}[\\/]{2,}',
            
            # 시스템 경로
            r'(?i)[\\/]etc[\\/]passwd',
            r'(?i)[\\/]windows[\\/]system32',
            r'(?i)c:[\\/]windows',
            r'(?i)[\\/]root[\\/]',
            r'(?i)[\\/]home[\\/]',
            r'(?i)[\\/]usr[\\/]bin',
            r'(?i)[\\/]var[\\/]log',
            
            # 특수 경로
            r'(?i)[\\/]admin[\\/]',
            r'(?i)[\\/]config[\\/]',
            r'(?i)[\\/]backup[\\/]',
            r'(?i)[\\/]\.git[\\/]',
            r'(?i)[\\/]\.env',
            r'(?i)[\\/]\.htaccess',
            
            # 파일 확장자 공격
            r'(?i)\.php[\?#]',
            r'(?i)\.jsp[\?#]',
            r'(?i)\.asp[\?#]',
            r'(?i)\.exe[\?#]',
        ]
        
        self.compiled_patterns = [re.compile(pattern) for pattern in self.attack_patterns]
    
    def kill_path_traversal(self, url_path: str) -> Tuple[bool, List[str]]:
        """
        완전한 Path Traversal 검증
        
        Returns:
            (is_safe, detected_attacks)
        """
        if not url_path:
            return True, []
        
        detected_attacks = []
        original_path = url_path
        
        # 🔥 STEP 1: 다중 디코딩 검사
        decoded_paths = [url_path]
        
        # 최대 5단계 디코딩
        current_path = url_path
        for i in range(5):
            try:
                # URL 디코딩
                new_path = urllib.parse.unquote(current_path)
                if new_path != current_path:
                    decoded_paths.append(new_path)
                    current_path = new_path
                else:
                    break
                
                # Plus 디코딩
                plus_decoded = urllib.parse.unquote_plus(current_path)
                if plus_decoded != current_path:
                    decoded_paths.append(plus_decoded)
                    current_path = plus_decoded
                    
            except Exception:
                # 디코딩 실패는 의심스러운 신호
                detected_attacks.append(f"DECODE_ERROR_STAGE_{i}")
                break
        
        # 🔥 STEP 2: 모든 디코딩된 경로 검사
        for i, path in enumerate(decoded_paths):
            # 정규화 시도
            try:
                normalized = os.path.normpath(path)
                if normalized != path:
                    decoded_paths.append(normalized)
            except Exception:
                detected_attacks.append(f"NORMPATH_ERROR_{i}")
            
            # 패턴 매칭
            for j, pattern in enumerate(self.compiled_patterns):
                if pattern.search(path):
                    detected_attacks.append(f"PATTERN_{j}_STAGE_{i}")
        
        # 🔥 STEP 3: 경로 구조 분석
        path_parts = original_path.split('/')
        for part in path_parts:
            if part.startswith('..'):
                detected_attacks.append("DOT_DOT_SEGMENT")
            if '%' in part and len(part) > 10:
                detected_attacks.append("SUSPICIOUS_ENCODING")
            if part.count('.') > 3:
                detected_attacks.append("EXCESSIVE_DOTS")
        
        # 🔥 STEP 4: 길이 및 깊이 검사
        if len(original_path) > 1000:
            detected_attacks.append("OVERSIZED_PATH")
        
        if original_path.count('/') > 20:
            detected_attacks.append("EXCESSIVE_DEPTH")
        
        # 🔥 STEP 5: 특수 문자 검사
        suspicious_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
        if any(char in original_path for char in suspicious_chars):
            detected_attacks.append("NULL_BYTE_INJECTION")
        
        is_safe = len(detected_attacks) == 0
        
        if not is_safe:
            logger.critical(f"🔥 PATH TRAVERSAL ATTACK KILLED: {original_path} - {detected_attacks}")
        
        return is_safe, detected_attacks


# 전역 인스턴스
_path_killer = None

def get_path_traversal_killer() -> PathTraversalKiller:
    """전역 Path Traversal Killer 인스턴스"""
    global _path_killer
    if _path_killer is None:
        _path_killer = PathTraversalKiller()
        logger.info("🔥 Path Traversal Killer initialized")
    return _path_killer