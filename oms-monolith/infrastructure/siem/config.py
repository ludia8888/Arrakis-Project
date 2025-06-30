"""
SIEM 설정 및 DI 구성
"""
from typing import Optional
from shared.config.environment import StrictEnv
from infrastructure.siem.port import ISiemPort
from infrastructure.siem.adapter import (
    SiemHttpAdapter,
    MockSiemAdapter,
    KafkaSiemAdapter,
    BufferedSiemAdapter
)


def get_siem_adapter() -> Optional[ISiemPort]:
    """
    환경 설정에 따라 적절한 SIEM 어댑터 반환
    """
    env = StrictEnv()
    
    # SIEM 활성화 여부 확인
    if not env.get_str("ENABLE_SIEM_INTEGRATION", default="true").lower() in ("true", "1", "yes"):
        return None
    
    # 테스트 모드
    if env.get_str("TEST_MODE", default="false").lower() in ("true", "1", "yes"):
        return MockSiemAdapter()
    
    # SIEM 타입에 따라 적절한 어댑터 선택
    siem_type = env.get_str("SIEM_TYPE", default="http").lower()
    
    if siem_type == "http":
        from shared.config.environment import get_config
        config = get_config()
        endpoint = config.get("SIEM_ENDPOINT", "http://siem-collector:8088/services/collector")
        token = env.get_str("SIEM_TOKEN", default="")
        
        if not endpoint or not token:
            raise ValueError("SIEM_ENDPOINT and SIEM_TOKEN must be set for HTTP adapter")
        
        # 버퍼링 활성화 옵션
        if env.get_str("SIEM_BUFFERING", default="true").lower() in ("true", "1", "yes"):
            base_adapter = SiemHttpAdapter(endpoint=endpoint, token=token)
            return BufferedSiemAdapter(
                base_adapter=base_adapter,
                buffer_size=env.get_int("SIEM_BUFFER_SIZE", default=100),
                flush_interval=env.get_float("SIEM_FLUSH_INTERVAL", default=5.0)
            )
        else:
            return SiemHttpAdapter(endpoint=endpoint, token=token)
    
    elif siem_type == "kafka":
        from shared.config.environment import get_config
        config = get_config()
        bootstrap_servers = config.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        topic = env.get_str("KAFKA_TOPIC", default="oms-validation-events")
        return KafkaSiemAdapter(
            bootstrap_servers=bootstrap_servers,
            topic=topic
        )
    
    elif siem_type == "mock":
        return MockSiemAdapter()
    
    else:
        raise ValueError(f"Unknown SIEM type: {siem_type}")


# 싱글톤 인스턴스
_siem_adapter: Optional[ISiemPort] = None


def get_shared_siem_adapter() -> Optional[ISiemPort]:
    """
    공유 SIEM 어댑터 인스턴스 반환 (싱글톤)
    """
    global _siem_adapter
    if _siem_adapter is None:
        _siem_adapter = get_siem_adapter()
    return _siem_adapter