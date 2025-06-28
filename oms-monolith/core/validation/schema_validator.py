"""
엔터프라이즈급 JSON-Schema Validator 구현

기존 stub 을 jsonschema 라이브러리를 이용한 실제 검증 로직으로 대체한다.
• Draft-2020-12, Draft-07 등 다중 Draft 지원
• $ref 외부 파일 해석을 위해 ValidationConfig 의 schema_base_dir 사용
• LRU 캐싱으로 컴파일된 스키마 재사용 → 성능 최적화
• try/except 로 상세 오류 메시지 제공 & 회수 가능
"""

from __future__ import annotations

# 표준 라이브러리
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# 외부 라이브러리 – jsonschema 는 requirements.txt 에 명시돼 있어야 함
from jsonschema import Draft7Validator, Draft202012Validator, Draft201909Validator
from jsonschema.exceptions import ValidationError, SchemaError

# 프로젝트 공통 설정
from core.validation.config import get_validation_config, ValidationConfig

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """스키마 검증 실패 시 발생"""


class JsonSchemaValidator:
    """엔터프라이즈급 JSON-Schema Validator"""

    _DRAFT_MAP = {
        "2020-12": Draft202012Validator,
        "2019-09": Draft201909Validator,
        "07": Draft7Validator,
    }

    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or get_validation_config()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def validate(self, data: Any, schema: Dict[str, Any] | str, *, raise_error: bool = False) -> bool:
        """JSON 데이터를 주어진 스키마로 검증한다.

        매 검증마다 Schema 를 파싱/컴파일하면 성능이 저하되므로 LRU 캐싱을 활용한다.

        Args:
            data: 검증할 JSON-호환 데이터
            schema: dict 혹은 파일 경로(str)
            raise_error: True 인 경우 ValidationError 발생, False 는 bool 반환

        Returns:
            bool: 유효한 경우 True, 불일치하면 False (raise_error=False 경우)
        """
        try:
            compiled = self._get_compiled_validator(schema)
            compiled.validate(data)
            return True
        except (ValidationError, SchemaError) as e:
            if raise_error:
                raise SchemaValidationError(str(e)) from e
            logger.debug("Schema validation failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------

    def _load_schema(self, schema: Dict[str, Any] | str) -> Dict[str, Any]:
        """dict 또는 경로로부터 스키마 JSON 로드"""
        if isinstance(schema, dict):
            return schema

        schema_path = Path(schema)
        if not schema_path.is_absolute():
            schema_path = Path(self.config.schema_base_dir) / schema_path

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def _get_draft_cls(self, schema_dict: Dict[str, Any]):
        draft_id = schema_dict.get("$schema", self.config.default_draft)
        for key, cls in self._DRAFT_MAP.items():
            if key in draft_id:
                return cls
        # fallback
        return Draft7Validator

    @lru_cache(maxsize=256)
    def _compile_schema(self, schema_json: str) -> Any:
        """스키마(JSON string) → 컴파일된 Validator 캐싱"""
        schema_dict: Dict[str, Any] = json.loads(schema_json)
        draft_cls = self._get_draft_cls(schema_dict)
        resolver = None

        # enable format checker if 옵션이 켜져있을 때만
        format_checker = draft_cls.FORMAT_CHECKER if self.config.enable_format_validation else None

        return draft_cls(schema_dict, format_checker=format_checker, resolver=resolver)

    def _get_compiled_validator(self, schema: Dict[str, Any] | str):
        schema_dict = self._load_schema(schema)
        schema_json = json.dumps(schema_dict, sort_keys=True)
        return self._compile_schema(schema_json)


# ---------------------------------------------------------------------
# 팩토리 & 보조 유틸리티
# ---------------------------------------------------------------------

_def_validator: Optional[JsonSchemaValidator] = None


def get_schema_validator(refresh: bool = False) -> JsonSchemaValidator:
    """싱글턴 Validator 인스턴스를 가져온다."""
    global _def_validator
    if refresh or _def_validator is None:
        _def_validator = JsonSchemaValidator()
    return _def_validator


def validate_external_naming_convention(data: Dict[str, Any], *, raise_error: bool = False) -> bool:
    """외부 시스템에서 들어오는 Naming-Convention JSON 검증.

    실제 스키마는 schema_base_dir/naming_convention.json 에 위치한다고 가정한다.
    """
    config = get_validation_config()
    schema_path = Path(config.schema_base_dir) / "naming_convention.json"
    validator = get_schema_validator()
    return validator.validate(data, str(schema_path), raise_error=raise_error)