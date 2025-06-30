"""
Input Sanitization Performance Tests
ReDoS vulnerability prevention and performance validation
"""
import time
import pytest
from typing import List, Tuple

from core.validation.input_sanitization import (
    InputSanitizer, SanitizationLevel, get_input_sanitizer
)


class TestInputSanitizationPerformance:
    """Performance tests for input sanitization to prevent ReDoS attacks"""
    
    @pytest.fixture
    def sanitizer(self):
        """Create a sanitizer instance"""
        return get_input_sanitizer()
    
    @pytest.fixture
    def redos_payloads(self) -> List[Tuple[str, str]]:
        """Known ReDoS attack payloads"""
        return [
            # Exponential backtracking patterns
            ("email_bomb", "a" * 100 + "@" * 100),
            ("nested_groups", "((((((((((a))))))))))" * 10),
            ("alternation_bomb", "a|a|a|" * 100 + "b"),
            ("repetition_bomb", "a" * 1000 + "!" * 1000),
            ("unicode_bomb", "\u200b" * 10000),  # Zero-width spaces
            ("control_char_bomb", "\x00" * 1000 + "\x1f" * 1000),
            ("mixed_bomb", "a" * 500 + "\x00" + "b" * 500 + "'" + "c" * 500),
            
            # SQL injection patterns that could cause ReDoS
            ("sql_union", "' UNION SELECT " * 100),
            ("sql_comment", "/*" * 500 + "*/" * 500),
            
            # XSS patterns that could cause ReDoS
            ("xss_script", "<script>" * 100 + "</script>" * 100),
            ("xss_event", "onload=" * 200),
            
            # Path traversal patterns
            ("path_traversal", "../" * 1000),
            ("encoded_traversal", "%2e%2e%2f" * 500),
        ]
    
    @pytest.mark.benchmark
    def test_paranoid_level_performance(self, sanitizer, redos_payloads):
        """Test PARANOID level doesn't suffer from ReDoS"""
        max_allowed_time = 0.1  # 100ms max per input
        
        for payload_name, payload in redos_payloads:
            start_time = time.time()
            
            result = sanitizer.sanitize(payload, SanitizationLevel.PARANOID)
            
            elapsed_time = time.time() - start_time
            
            # Assert performance requirements
            assert elapsed_time < max_allowed_time, \
                f"Payload '{payload_name}' took {elapsed_time:.3f}s (max: {max_allowed_time}s)"
            
            # Assert sanitization was effective
            assert result.was_modified or result.detected_threats, \
                f"Payload '{payload_name}' should have been detected as malicious"
    
    @pytest.mark.benchmark
    def test_large_input_performance(self, sanitizer):
        """Test performance with large but legitimate inputs"""
        # 1MB of legitimate text
        large_input = "The quick brown fox jumps over the lazy dog. " * 25000
        
        start_time = time.time()
        result = sanitizer.sanitize(large_input, SanitizationLevel.PARANOID)
        elapsed_time = time.time() - start_time
        
        # Should handle 1MB in under 1 second
        assert elapsed_time < 1.0, f"Large input took {elapsed_time:.3f}s"
        
        # Should truncate to reasonable length
        assert len(result.sanitized_value) <= 10000
    
    @pytest.mark.benchmark 
    def test_concurrent_sanitization(self, sanitizer):
        """Test concurrent sanitization doesn't degrade performance"""
        import concurrent.futures
        
        def sanitize_input(text):
            return sanitizer.sanitize(text, SanitizationLevel.PARANOID)
        
        # Create mixed payloads
        payloads = [
            "normal input " * 10,
            "<script>alert('xss')</script>",
            "' OR 1=1 --",
            "../../../etc/passwd",
            "a" * 1000,
        ] * 20  # 100 total payloads
        
        # Sequential baseline
        start_time = time.time()
        sequential_results = [sanitize_input(p) for p in payloads]
        sequential_time = time.time() - start_time
        
        # Concurrent execution
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            concurrent_results = list(executor.map(sanitize_input, payloads))
        concurrent_time = time.time() - start_time
        
        # Concurrent should be faster or at least not significantly slower
        assert concurrent_time < sequential_time * 1.5, \
            f"Concurrent: {concurrent_time:.3f}s vs Sequential: {sequential_time:.3f}s"
        
        # Results should be identical
        for i, (seq_res, con_res) in enumerate(zip(sequential_results, concurrent_results)):
            assert seq_res.sanitized_value == con_res.sanitized_value, \
                f"Result mismatch at index {i}"
    
    @pytest.mark.parametrize("level", [
        SanitizationLevel.BASIC,
        SanitizationLevel.STANDARD,
        SanitizationLevel.STRICT,
        SanitizationLevel.PARANOID
    ])
    def test_sanitization_levels_performance(self, sanitizer, level):
        """Compare performance across different sanitization levels"""
        test_input = "Hello <script>alert('xss')</script> World! '../etc/passwd'"
        
        iterations = 1000
        start_time = time.time()
        
        for _ in range(iterations):
            sanitizer.sanitize(test_input, level)
        
        elapsed_time = time.time() - start_time
        avg_time = elapsed_time / iterations
        
        # Even PARANOID should be fast for normal inputs
        assert avg_time < 0.001, \
            f"Level {level.value} avg time: {avg_time*1000:.3f}ms per operation"
    
    def test_attack_detection_coverage(self, sanitizer, redos_payloads):
        """Verify attack patterns are detected without performance penalty"""
        detection_stats = {
            "sql_injection": 0,
            "xss_scripts": 0,
            "command_injection": 0,
            "path_traversal": 0,
            "other": 0
        }
        
        for payload_name, payload in redos_payloads:
            result = sanitizer.sanitize(payload, SanitizationLevel.PARANOID)
            
            if result.detected_threats:
                for threat in result.detected_threats:
                    if "sql" in threat.lower():
                        detection_stats["sql_injection"] += 1
                    elif "xss" in threat.lower() or "script" in threat.lower():
                        detection_stats["xss_scripts"] += 1
                    elif "command" in threat.lower():
                        detection_stats["command_injection"] += 1
                    elif "path" in threat.lower() or "traversal" in threat.lower():
                        detection_stats["path_traversal"] += 1
                    else:
                        detection_stats["other"] += 1
        
        # Should detect various attack types
        assert detection_stats["sql_injection"] > 0
        assert detection_stats["xss_scripts"] > 0
        assert detection_stats["path_traversal"] > 0
        
        # Calculate detection rate
        total_payloads = len(redos_payloads)
        detected_payloads = sum(1 for _, p in redos_payloads 
                               if sanitizer.sanitize(p, SanitizationLevel.PARANOID).detected_threats)
        detection_rate = detected_payloads / total_payloads * 100
        
        # Should detect at least 95% of malicious payloads
        assert detection_rate >= 95, f"Detection rate: {detection_rate:.1f}%"