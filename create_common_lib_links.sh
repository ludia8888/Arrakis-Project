#!/bin/bash
# 공통 라이브러리를 각 서비스에서 사용할 수 있도록 심볼릭 링크 생성

echo "🔗 공통 라이브러리 심볼릭 링크 생성 중..."

# 각 서비스 디렉토리에 arrakis_common 심볼릭 링크 생성
for service in user-service audit-service ontology-management-service; do
    if [ -d "$service" ]; then
        echo "  $service에 arrakis_common 링크 생성"
        rm -f "$service/arrakis_common"
        ln -sf "../arrakis-common/arrakis_common" "$service/arrakis_common"
    fi
done

echo "✅ 공통 라이브러리 링크 생성 완료"