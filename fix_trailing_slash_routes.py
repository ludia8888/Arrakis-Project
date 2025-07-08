#!/usr/bin/env python3
"""
Script to demonstrate the trailing slash issue and the fix
"""

# The issue is in the route definitions:
# In organization_routes.py and property_routes.py

# CURRENT (causes 307 redirects):
# @router.get("/")  # This creates /api/v1/organizations/
# async def list_organizations(...):

# FIX:
# @router.get("")  # This creates /api/v1/organizations (no trailing slash)
# async def list_organizations(...):

# The fix is to change:
# - @router.get("/") → @router.get("")
# - @router.post("/") → @router.post("")

# This applies to both organization_routes.py and property_routes.py

print("""
The 307 redirects are caused by FastAPI's automatic trailing slash handling.

Current route definitions:
- @router.get("/") creates /api/v1/organizations/ (with trailing slash)
- Requests to /api/v1/organizations get 307 redirect to /api/v1/organizations/

Fix:
- Change @router.get("/") to @router.get("")
- Change @router.post("/") to @router.post("")

This will create routes without trailing slashes:
- /api/v1/organizations
- /api/v1/properties

Files to update:
1. ontology-management-service/api/v1/organization_routes.py
   - Line 20: @router.get("/") → @router.get("")
   - Line 74: @router.post("/") → @router.post("")

2. ontology-management-service/api/v1/property_routes.py
   - Line 20: @router.get("/") → @router.get("")
   - Line 141: @router.post("/") → @router.post("")
""")