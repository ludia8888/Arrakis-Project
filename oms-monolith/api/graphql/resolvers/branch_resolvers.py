"""
Branch Query Resolvers
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    Branch,
    BranchStatusEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class BranchQueryResolvers:
    """Branch Query Resolvers"""

    @strawberry.field
    async def branches(
        self,
        info: strawberry.Info,
        include_system: bool = False,
        status: Optional[BranchStatusEnum] = None
    ) -> List[Branch]:
        """Branch 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.branch_service_url}/api/v1/branches"
        params = {}
        if status:
            params['status'] = status.value
        if not include_system:
            params['exclude_system'] = True

        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        branches = []
        for branch_data in result.get('data', []):
            branch = Branch(
                name=branch_data.get('name', ''),
                fromBranch=branch_data.get('fromBranch'),
                headHash=branch_data.get('headHash', ''),
                description=branch_data.get('description'),
                status=BranchStatusEnum(branch_data.get('status', 'active')),
                isProtected=branch_data.get('isProtected', False),
                createdBy=branch_data.get('createdBy', ''),
                createdAt=branch_data.get('createdAt'),
                lastModified=branch_data.get('lastModified'),
                commitsAhead=branch_data.get('commitsAhead', 0),
                commitsBehind=branch_data.get('commitsBehind', 0),
                hasPendingChanges=branch_data.get('hasPendingChanges', False)
            )
            branches.append(branch)

        return branches

    @strawberry.field
    async def branch(
        self,
        info: strawberry.Info,
        name: str
    ) -> Optional[Branch]:
        """Branch 상세 조회"""
        user = info.context.get("user")

        url = f"{service_client.branch_service_url}/api/v1/branches/{name}"
        try:
            result = await service_client.call_service(url, "GET", None, user)

            # 데이터 변환
            return Branch(
                name=result.get('name', ''),
                fromBranch=result.get('fromBranch'),
                headHash=result.get('headHash', ''),
                description=result.get('description'),
                status=BranchStatusEnum(result.get('status', 'active')),
                isProtected=result.get('isProtected', False),
                createdBy=result.get('createdBy', ''),
                createdAt=result.get('createdAt'),
                lastModified=result.get('lastModified'),
                commitsAhead=result.get('commitsAhead', 0),
                commitsBehind=result.get('commitsBehind', 0),
                hasPendingChanges=result.get('hasPendingChanges', False)
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise