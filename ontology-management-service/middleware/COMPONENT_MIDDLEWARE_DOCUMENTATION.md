# ComponentMiddleware 문서

## 개요

ComponentMiddleware는 온톨로지 관리 서비스(OMS)를 위한 엔터프라이즈급 미들웨어 시스템으로, 모듈형 플러그인 기반 아키텍처를 제공합니다. 동적 컴포넌트 로딩, 생명주기 관리, 컴포넌트 간 통신을 가능하게 합니다.

## 목적

협업 개발 환경에서 ComponentMiddleware는 다음과 같은 역할을 합니다:

1. **모듈형 아키텍처**: 모놀리식 코드를 관리 가능한 독립적인 컴포넌트로 분해
2. **플러그인 시스템**: 팀이 핵심 코드를 수정하지 않고 독립적으로 기능을 개발할 수 있도록 지원
3. **동적 로딩**: 서비스 재시작 없이 컴포넌트를 추가, 제거, 업데이트 가능
4. **의존성 관리**: 컴포넌트 의존성의 자동 해결 및 주입
5. **생명주기 관리**: 표준화된 초기화, 헬스체크, 종료 절차

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    ComponentMiddleware                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  컴포넌트   │  │  컴포넌트   │  │  컴포넌트   │       │
│  │   매니저    │  │  레지스트리 │  │   로더      │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                 │                 │               │
│  ┌──────▼─────────────────▼─────────────────▼──────┐       │
│  │              컴포넌트 풀                         │       │
│  ├─────────────────────────────────────────────────┤       │
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│       │
│  │ │ 인증    │ │ 캐시    │ │ 검색    │ │ 내보내기││       │
│  │ │컴포넌트 │ │컴포넌트 │ │컴포넌트 │ │컴포넌트 ││       │
│  │ └─────────┘ └─────────┘ └─────────┘ └─────────┘│       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 핵심 개념

### 1. 컴포넌트 정의

컴포넌트는 다음과 같은 특징을 가진 독립적인 기능 단위입니다:
- 고유한 식별자 보유
- `IComponent` 인터페이스 구현
- 자체 생명주기 관리
- 다른 컴포넌트에 의존 가능

```python
class IComponent(ABC):
    """모든 컴포넌트의 기본 인터페이스"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """컴포넌트 초기화"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """컴포넌트 정상 종료"""
        pass
    
    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """컴포넌트 상태 확인"""
        pass
```

### 2. 컴포넌트 유형

#### 서비스 컴포넌트
- 장시간 실행되는 서비스 (예: 백그라운드 워커)
- 예시: `NotificationService`, `SyncService`

#### 기능 컴포넌트
- 애플리케이션에 특정 기능 추가
- 예시: `SearchComponent`, `ExportComponent`

#### 통합 컴포넌트
- 외부 서비스와 연결
- 예시: `ElasticsearchComponent`, `S3Component`

#### 미들웨어 컴포넌트
- 요청/응답 흐름 수정
- 예시: `RateLimitComponent`, `CacheComponent`

### 3. 컴포넌트 생명주기

```
┌──────────┐     ┌──────────────┐     ┌─────────┐     ┌──────────┐
│  등록됨  │ --> │   초기화중   │ --> │  활성   │ --> │  중지중  │
└──────────┘     └──────────────┘     └─────────┘     └──────────┘
                                            │                │
                                            ▼                ▼
                                      ┌─────────┐      ┌──────────┐
                                      │  실패   │      │  중지됨  │
                                      └─────────┘      └──────────┘
```

## 사용 예시

### 1. 컴포넌트 생성

```python
from middleware.component_middleware import IComponent, component

@component(
    name="email_notification",
    version="1.0.0",
    dependencies=["smtp_client", "template_engine"]
)
class EmailNotificationComponent(IComponent):
    """이메일 알림 컴포넌트"""
    
    def __init__(self, smtp_client, template_engine):
        self.smtp_client = smtp_client
        self.template_engine = template_engine
        self.initialized = False
    
    async def initialize(self):
        """이메일 서비스 연결 초기화"""
        await self.smtp_client.connect()
        self.initialized = True
        logger.info("이메일 알림 컴포넌트 초기화 완료")
    
    async def shutdown(self):
        """이메일 서비스 연결 종료"""
        await self.smtp_client.disconnect()
        self.initialized = False
        logger.info("이메일 알림 컴포넌트 종료 완료")
    
    def health_check(self):
        """이메일 서비스 상태 확인"""
        return HealthCheckResult(
            healthy=self.initialized and self.smtp_client.is_connected(),
            message="이메일 서비스 정상" if self.initialized else "초기화되지 않음"
        )
    
    async def send_email(self, to: str, subject: str, template: str, data: dict):
        """템플릿을 사용하여 이메일 전송"""
        if not self.initialized:
            raise ComponentNotInitializedError("이메일 컴포넌트가 초기화되지 않음")
        
        html = await self.template_engine.render(template, data)
        await self.smtp_client.send(to, subject, html)
```

### 2. 컴포넌트 등록

```python
# 애플리케이션 시작 시
from middleware.component_middleware import ComponentManager

# 컴포넌트 매니저 가져오기
manager = ComponentManager.get_instance()

# 컴포넌트 등록
manager.register_component(EmailNotificationComponent)
manager.register_component(SearchComponent)
manager.register_component(CacheComponent)

# 모든 컴포넌트 초기화
await manager.initialize_all()
```

### 3. 엔드포인트에서 컴포넌트 사용

```python
from fastapi import Depends
from middleware.component_middleware import get_component

@router.post("/api/v1/users/invite")
async def invite_user(
    email: str,
    email_component: EmailNotificationComponent = Depends(get_component("email_notification"))
):
    """이메일로 사용자 초대"""
    await email_component.send_email(
        to=email,
        subject="초대합니다!",
        template="invitation",
        data={"invite_link": "https://..."}
    )
    return {"status": "초대 발송 완료"}
```

### 4. 동적 컴포넌트 로딩

```python
# 런타임에 컴포넌트 로드
new_component = manager.load_component_from_file("plugins/analytics_component.py")
await manager.register_and_initialize(new_component)

# 컴포넌트 언로드
await manager.unload_component("old_analytics")
```

## 설정

컴포넌트는 다음 방법으로 설정할 수 있습니다:

1. **환경 변수**
```bash
COMPONENT_EMAIL_SMTP_HOST=smtp.gmail.com
COMPONENT_EMAIL_SMTP_PORT=587
```

2. **설정 파일**
```yaml
components:
  email_notification:
    smtp_host: smtp.gmail.com
    smtp_port: 587
    use_tls: true
```

3. **런타임 설정**
```python
manager.configure_component("email_notification", {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587
})
```

## 모범 사례

### 1. 컴포넌트 설계
- **단일 책임**: 각 컴포넌트는 하나의 명확한 목적을 가져야 함
- **느슨한 결합**: 컴포넌트 간 의존성 최소화
- **인터페이스 기반**: 구현이 아닌 인터페이스에 의존
- **설정 가능**: 하드코딩 대신 설정 사용

### 2. 오류 처리
- 컴포넌트는 자체 오류를 우아하게 처리해야 함
- 초기화 실패가 애플리케이션 충돌로 이어지지 않아야 함
- 의미 있는 헬스체크 정보 제공

### 3. 테스팅
```python
# 컴포넌트를 독립적으로 테스트
async def test_email_component():
    # 모의 의존성 생성
    mock_smtp = MockSMTPClient()
    mock_template = MockTemplateEngine()
    
    # 컴포넌트 생성
    component = EmailNotificationComponent(mock_smtp, mock_template)
    
    # 생명주기 테스트
    await component.initialize()
    assert component.health_check().healthy
    
    # 기능 테스트
    await component.send_email("test@example.com", "테스트", "template", {})
    assert mock_smtp.sent_count == 1
    
    # 정리
    await component.shutdown()
```

### 4. 문서화
모든 컴포넌트는 다음을 포함해야 합니다:
- 목적에 대한 명확한 설명
- 의존성 목록
- 설정 옵션
- 사용 예시
- 오류 시나리오

## 모니터링 및 관찰 가능성

ComponentMiddleware는 내장 모니터링을 제공합니다:

```python
# 컴포넌트 메트릭 가져오기
metrics = manager.get_component_metrics("email_notification")
print(f"가동 시간: {metrics.uptime}")
print(f"요청 수: {metrics.request_count}")
print(f"오류율: {metrics.error_rate}")

# 모든 컴포넌트 헬스체크
health_report = await manager.health_check_all()
for component_name, result in health_report.items():
    print(f"{component_name}: {result.status}")
```

## 고급 기능

### 1. 컴포넌트 의존성
```python
@component(
    name="report_generator",
    dependencies=["database", "email_notification", "pdf_generator"]
)
class ReportGeneratorComponent(IComponent):
    # 의존성이 자동으로 주입됨
    pass
```

### 2. 컴포넌트 이벤트
```python
# 컴포넌트 이벤트 구독
manager.on("component_initialized", handle_component_initialized)
manager.on("component_failed", handle_component_failure)
```

### 3. 핫 리로딩
```python
# 개발 환경에서 핫 리로딩 활성화
manager.enable_hot_reload()
# 파일이 변경되면 컴포넌트가 자동으로 리로드됨
```

## 다른 미들웨어와의 통합

ComponentMiddleware는 다른 미들웨어와 원활하게 통합됩니다:

1. **AuthMiddleware**: 컴포넌트가 사용자 컨텍스트에 접근 가능
2. **RateLimitingMiddleware**: 컴포넌트가 자체 요청 제한 설정 가능
3. **AuditLogMiddleware**: 컴포넌트 작업이 자동으로 기록됨
4. **CircuitBreakerMiddleware**: 실패한 컴포넌트가 서킷 브레이커를 트리거

## 문제 해결

### 일반적인 문제

1. **컴포넌트를 찾을 수 없음**
   - 컴포넌트가 등록되었는지 확인
   - 컴포넌트 이름 철자 확인
   - 컴포넌트 파일이 올바른 위치에 있는지 확인

2. **순환 의존성**
   - 컴포넌트 의존성 그래프 검토
   - 순환 의존성 제거를 위한 리팩토링
   - 필요시 지연 로딩 사용

3. **컴포넌트 초기화 실패**
   - 컴포넌트 로그 확인
   - 모든 의존성이 사용 가능한지 확인
   - 설정이 올바른지 확인

### 디버그 모드
```python
# 상세 로깅을 위한 디버그 모드 활성화
manager.set_debug_mode(True)
```

## 향후 개선 사항

1. **컴포넌트 마켓플레이스**: 프로젝트 간 컴포넌트 공유
2. **비주얼 컴포넌트 디자이너**: 컴포넌트 생성 및 연결을 위한 GUI
3. **컴포넌트 버전 관리**: 동일 컴포넌트의 여러 버전 지원
4. **분산 컴포넌트**: 다른 서버에서 실행되는 컴포넌트

## 결론

ComponentMiddleware는 OMS를 모놀리식 애플리케이션에서 유연하고 확장 가능한 플랫폼으로 변환합니다. 컴포넌트 모델을 따름으로써 팀은:
- 독립적으로 기능 개발
- 다른 컴포넌트에 영향을 주지 않고 업데이트 배포
- 필요에 따라 특정 기능 확장
- 시스템의 서로 다른 부분 간 명확한 경계 유지

이 아키텍처 패턴은 협업 개발과 OMS 플랫폼의 장기적인 유지보수성을 위해 필수적입니다.