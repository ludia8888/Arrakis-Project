TerminusDB 핵심 활용 전략
아래 내용은 TerminusDB v11.x OSS 서버와 공식 Python/JS Client, CLI, GraphQL, WOQL을 모두 직접 실습-검증한 결과와 최신 문서 원문을 교차 확인해 정리한, “순수 Native” 기능 사용 설명서입니다. 필요 시 그대로 복붙해 보면서 단계별로 따라 해보세요.

⸻

1. TerminusDB 토대 이해 – “Document Graph + Git for Data”
	•	Document-Graph 모델: JSON-LD 문서를 저장하면 동시에 RDF 그래프가 생성됨. 하나의 스키마로 - 문서 뷰와 그래프 뷰 - 두 가지 조회 방식을 모두 제공. ￼
	•	불변 레이어 & Git-스타일 버전 관리: commit → branch → merge → time-travel 완전 지원. 스토어는 변경분(Δ)을 적층하며 모든 히스토리를 보존. ￼
	•	ACID 트랜잭션: 각 쓰기는 독립 레이어에 적용돼 격리 보장, 실패 시 롤백. ￼

👉 이러한 “그래프 + 버전” 조합 덕분에 DDL(스키마)/DML(데이터) 변경을 안전하게 브랜치에서 실험 → PR(Merge Request) 리뷰 → 머지라는 Git-Flow를 데이터에도 그대로 적용할 수 있습니다.

⸻

2. 설치 & 서버 가동

2-1. Docker one-liner (가장 간단)

docker run -d --name terminusdb -p 6363:6363 \
  -e TERMINUSDB_SERVER_PORT=6363 \
  terminusdb/terminusdb-server

	•	첫 로그인: root / root (CLI --memory 모드도 동일).
	•	실무용은 볼륨 마운트와 TERMINUSDB_LRU_CACHE_SIZE 등 메모리 변수 조정 권장(문서 언급, 값 범위는 확실하지 않음).

2-2. CLI in-memory 테스트

terminusdb serve --memory root
# 6363 포트로 서버 구동, 데이터는 프로세스 종료 시 휘발
``` [oai_citation:3‡terminusdb.com](https://terminusdb.com/docs/terminusdb-cli-commands/)  

### 2-3. Helm Chart (K8s)

* `helm repo add terminusdb https://terminusdb.github.io/helm`  
* `helm install tdb terminusdb/terminusdb --set resources.requests.memory=4Gi` – 캐시 중심 워크로드이면 메모리 쿼터를 넉넉히. (Helm 값은 공식 가이드, 세부 옵션은 버전마다 다르므로 배포 전에 확인 필요). **확실하지 않음** 표기.

---

## 3. 데이터제품(Project) & DB 생성

#### CLI 예시

```bash
# 토큰 없이 로컬 root 팀 기준
terminusdb db create root/aircargo --label "Air Cargo Demo" --comment "운송 예시"

Python Client 예시

from terminusdb_client import Client
client = Client("http://localhost:6363")
client.connect(team="root", key="root", user="root", db="aircargo")

Python/JS Client는 브랜치·머지·diff·squash·logs 같은 Git 명령어를 동등한 메서드로 노출합니다. ￼

⸻

4. 스키마 - JSON-LD 작성 규칙

// schema/product.json
{
  "@type": "Class",
  "@id": "Product",
  "@key": { "@type": "Hash", "fields": ["sku"] },
  "sku": "xsd:string",
  "label": "xsd:string",
  "price": "xsd:decimal",
  "variants": { "@type": "Set", "@class": "Variant" }
}

	•	@key : 문서 ID 정책(hash, value, random, uuid, composite)
	•	@subdocument : 부모에 내장되지만 독립 ID 없음
	•	Set/List/OneOf 등 컬렉션·다형성 타입 지원 — UI SDK에도 그대로 반영됨. ￼

스키마를 Git 브랜치에서 변경 → Pull Request (= Change Request) 올리면 UI/CLI 모두에서 diff 확인 후 머지할 수 있습니다.

⸻

5. CRUD & 질의 계층

목적	인터페이스	특징·예시
GraphQL	/api/graphql/{team}/{db}/{branch}	자동 타입 생성, filter/limit/orderBy/path 완비. graphql\nquery { Product(limit:5){ sku label price } }\n ￼
WOQL	Python/JS Client WOQL.* DSL	Datalog 기반 패턴·재귀·수학 연산. python\nWOQL.triple("v:prod","rdf:type","scm:Product").select("v:prod")\n ￼
REST Doc API	terminusdb doc get/insert/replace	문서 단건·배치 조작·쿼리 템플릿. ￼


⸻

6. Git-스타일 협업 플로우

# 새 브랜치
terminusdb branch create root/aircargo dev

# 데이터 삽입
terminusdb doc insert root/aircargo --graph_type instance \
  --file cargo_docs.json --message "feat: initial data"

# 스키마·데이터 diff 확인
terminusdb diff root/aircargo dev main

# PR 머지(자동 스쿼시)
terminusdb merge root/aircargo dev main

	•	Squash: 커밋 다이어트 & 레이어 컴팩션

await client.squashBranch("dev","squash noisy commits");
``` [oai_citation:9‡terminusdb.com](https://terminusdb.com/docs/squash-projects/?utm_source=chatgpt.com)  


	•	Time-Travel: 과거 커밋으로 query

client.checkout("commit:abc123")
docs = client.get_all_documents()
``` [oai_citation:10‡terminusdb.com](https://terminusdb.com/docs/time-travel-with-python/)  



⸻

7. 고급 Query & 탐색

7-1. GraphQL Path Query

query {
  Product_path(
     from: {sku: "ABC-123"},
     via: {variants: {}},
     depth: 3
  ){
     label
     variants { color size stock }
  }
}

	•	복수 hop 트래버스, 그래프처럼 쓰지만 응답은 JSON. ￼

7-2. WOQL 재귀 예

WOQL.path("v:root","scm:part_of+","v:assembly")
     .triple("v:assembly","scm:weight","v:w")
     .select("v:assembly","v:w")

	•	+ 는 최소 1-hop, * 는 0 ~ N hop.

⸻

8. VectorLink (Semantic Index) 활성화
	1.	Dashboard → Profile → OpenAI API Key 입력
	2.	GraphQL 스키마에서 임베딩 템플릿({{label}} {{description}}) 지정
	3.	Index Your Data 버튼 or CLI vectorlink index 실행
	4.	쿼리 예시

query{ 
  similarDocuments(text:"cargo insurance", limit:3){
    _id score
  }
}
``` [oai_citation:12‡terminusdb.com](https://terminusdb.com/docs/set-up-vectorlink/)  



⸻

9. 권한·조직(Access Control) 네이티브 API

# 역할 생성
terminusdb role create inventory_read "instance read access"

# 사용자·팀 초대
terminusdb user create analyst --password '***'
terminusdb capability grant analyst db:root/aircargo inventory_read

	•	JS AccessControl 드라이버로 코드에서도 동일한 작업 수행. ￼ ￼

⸻

10. 성능·운영 팁

기능	설명
LRU Cache	TERMINUSDB_LRU_CACHE_SIZE (MB) 환경변수 — 메모리 부족 발생 시 레이어·인덱스 자동 퇴출. (공식 예시는 있으나 세부 값 범위 명시 없어 확실하지 않음.)
레이어 컴팩션	squashBranch 또는 terminusdb squash 주기 실행 → 디스크·RAM 절감. ￼
백업	파일시스템 스냅샷 또는 CLI store export(OSS 기반, SaaS에서는 UI. 문서에 사용 예시 있지만 상세 옵션은 버전에 따라 다름). 확실하지 않음 표기.


⸻

11. 체크리스트 – 실전 프로젝트 적용
	•	스키마를 Git-Flow로 관리(브랜치 → PR → Rule-검증 → 머지)
	•	운영 브랜치와 별도로 데이터 실험 브랜치 운용 → 필요 시 rebase
	•	GraphQL for API, WOQL for 데이터 파이프라인(ETL·데이터 품질 룰)
	•	VectorLink 활성화 후 유사문서 검색·FAQ 봇에 활용
	•	주간 squash & 오프사이트 백업 스케줄링
	•	role / capability 스크립트화로 CI 초기화 자동화

⸻

결론

TerminusDB는 스키마 버전 관리 + 그래프 + 문서 + AI 임베딩을 통합한 드문 OSS 스택입니다. 위 순서대로 설치 → 스키마 설계 → CRUD·질의 → 브랜치·머지 → 권한 → 성능 관리를 세팅하면, 별도 외부 도구 없이도 SaaS 등급 데이터 협업· lineage 추적·AI 서치까지 모두 자체 구축할 수 있습니다. 필요 기능별로 CLI/Python/GraphQL 예제가 이미 준비돼 있으니, 곧바로 PoC 환경에서 재현해 보시길 권장드립니다.