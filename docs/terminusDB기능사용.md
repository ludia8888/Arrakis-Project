아래는 TerminusDB의 Python 클라이언트를 통해 사용할 수 있는 핵심 기능들을, 공식 문서와 샘플 코드 기반으로 정리한 내용입니다. 모두 팩트 기반이며, 시현님 시스템에 곧바로 적용 가능한 코드 예시입니다.

⸻

🛠 1. 설치 및 연결

pip install terminusdb-client

from terminusdb_client import Client

client = Client("http://localhost:6363/")
client.connect(user="admin", key="root", team="admin", db="mydb")  # 기본 브랜치는 main

￼

⸻

🌿 2. 브랜치 생성, 전환 및 조회

client.create_branch("feature/schema")  # main 브랜치에서 새 브랜치 생성
client.branch("feature/schema")         # 해당 브랜치로 전환
branches = client.get_all_branches()    # 브랜치 목록 조회

	•	create_branch(new_branch_id, empty=False) 함수는 현재 브랜치 기준 분기합니다  ￼
	•	get_all_branches()는 브랜치 정보(canonical 이름, HEAD 커밋 ID 등)를 리턴합니다  ￼

⸻

✍️ 3. 문서 삽입, 업데이트 및 삭제

client.insert_document({
  "@type": "Product",
  "sku": "ABC123",
  "name": "Red Hoodie",
  "price": 39.99
}, commit_msg="Add product")  # insert + 커밋

	•	insert_document() 자동 커밋 가능하며, commit 메시지 전달 기능 지원  ￼

client.delete_document("Product/ABC123", graph_type="instance", commit_msg="Remove product")

	•	delete_document()는 문서 삭제 후 commit 처리 가능  ￼

⸻

🧾 4. 커밋 로그 조회

commits = client.logs(count=10)  # 최신 10개 커밋
for c in commits:
    print(c["identifier"], c["message"], c["author"])

	•	logs() (or get_commit_log())를 통해 HEAD부터 과거 커밋 이력 확인 가능  ￼

⸻

🧩 5. 변경 내용 비교 (diff) 및 패치 적용

patch = client.diff_object(old_obj, new_obj)  # 두 객체의 변경점 추출
client.patch(before_obj, patch)               # 변경점만 적용, commit은 수동 처리

	•	diff_object()는 JSON 두 객체 간 변경점 리턴  ￼
	•	patch()는 변경 적용용 함수이며 DB 커밋은 별도 처리 필요 ()

branch_diff = client.diff(before_commit, after_commit)

	•	브랜치나 커밋 간 diff 계산도 가능  ￼

⸻

🔄 6. 브랜치 동기화 및 개발 흐름 관리

client.rebase(branch="feature/schema", rebase_source="main", message="sync with main")

	•	rebase()는 feature 브랜치를 기준 브랜치 기준 최신화하며 충돌 리포트 포함 ()

client.reset("commit_id")               # hard reset
client.reset("commit_id", soft=True)    # soft reset (HEAD만 이동)

	•	reset()을 통해 과거 커밋 상태로 hard 또는 soft rollback 가능 ()

squash_id = client.squash(message="squash fix commits", author="developer")

	•	여러 커밋을 하나로 합치고 squash 커밋 생성함 ()

⸻

🔗 7. 원격 협업: Push / Pull

client.push(remote="origin", remote_branch="main", message="Publish changes", author="dev")
client.pull(remote="origin", remote_branch="main", message="Sync main", author="dev")

	•	push() & pull() 명령으로 여러 인스턴스 간 브랜치 동기화 가능 ()

⸻

🔍 8. WOQL 쿼리 실행

from terminusdb_client.woqlquery import WOQLQuery as WQ

q = WQ().triple("v:Product", "name", "v:Name")
res = client.query(q)
print(res["bindings"])

	•	관계기반 쿼리를 WOQL로 직접 실행할 수 있습니다 ()

⸻

✅ 요약 정리

기능	메서드 예시
브랜치 생성/조회	create_branch(), branch(), get_all_branches()
문서 CRUD	insert_document(), delete_document()
커밋 히스토리 보기	logs()
diff / patch	diff_object(), patch()
리베이스 / 리셋	rebase(), reset()
Squash	squash()
Push / Pull	push(), pull()
쿼리 실행	query(WOQLQuery)


⸻

🔗 추가 자료
	•	Python 클라이언트 공식 레퍼런스  ￼
	•	브랜치·리베이스 등 워크플로우 예시 ()
	•	WOQL 및 document API 기능 참고  ￼
	•	커밋 reset 가이드  ￼

⸻

🧠 결론

위의 코드와 메서드는 모두 공식 문서 및 실제 Python 라이브러리 기반이며,
시현님처럼 온톨로지 기반 MSA 플랫폼 구축 시 다음 시나리오에 즉시 적용 가능합니다:
	•	브랜치 기반 스키마 제안 + diff 검토 워크플로우
	•	프로덕션 / 개발 데이터 분리
	•	데이터 버전 롤백 및 작업 충돌 해결
	•	구조화된 쿼리 + graph navigation

필요하시다면 이 코드들을 포함한 Demo 레포 + 파이프라인도 구성해드릴 수 있습니다. 언제든 말해주세요!