#!/usr/bin/env python3
"""
Analysis of Enterprise Validation Issues
"""

print("DEEP ANALYSIS: Enterprise Validation Not Working")
print("=" * 80)

print("\n1. MIDDLEWARE EXECUTION ORDER (from main.py):")
print("-" * 80)
print("""
The middleware stack in main.py (LIFO for requests, FIFO for responses):

1. AuthMiddleware (runs FIRST for requests)
2. RBACMiddleware  
3. ScopeRBACMiddleware
4. SchemaFreezeMiddleware
5. IssueTrackingMiddleware
6. EnterpriseValidationMiddleware  <-- This should validate requests
7. ETagMiddleware
8. CORSMiddleware (runs LAST for requests)
""")

print("\n2. THE CORE PROBLEM:")
print("-" * 80)
print("""
FastAPI's request processing flow:

1. Request arrives
2. Middleware stack processes request (top to bottom)
3. FastAPI route matching
4. **Pydantic model parsing/validation** <-- THIS HAPPENS HERE!
5. If Pydantic validation fails -> 422 response (middleware never sees it)
6. If Pydantic validation passes -> endpoint function runs
7. Response goes back through middleware (bottom to top)

The Enterprise Validation Middleware runs at step 2, but Pydantic validation 
happens at step 4. If Pydantic fails, it short-circuits the entire flow!
""")

print("\n3. SPECIFIC ISSUES FOUND:")
print("-" * 80)

print("\nA. Information Disclosure:")
print("""
- When Pydantic validation fails, it returns detailed error messages
- Example: "value is not a valid dict (type=type_error.dict)"
- These errors bypass EnterpriseValidationMiddleware.prevent_info_disclosure
- The middleware's _sanitize_error_message() is never called
""")

print("\nB. Inconsistent Endpoint Protection:")
print("""
Look at schema_routes.py:

1. Some endpoints use Pydantic models with validators:
   - SemanticTypeCreateRequest has @validator('baseType')
   - PropertyCreateRequest has pattern="^[a-zA-Z][a-zA-Z0-9_]*$"
   
2. Others use manual validation inside the endpoint:
   - create_link_type() manually checks cardinality
   - create_action_type() manually validates operations
   
Only the manual validations can be caught by Enterprise Validation!
""")

print("\nC. Metrics Collection Failure:")
print("""
In EnterpriseValidationMiddleware._track_metrics():
- Only called if middleware processes the request
- Pydantic 422 errors never reach this code
- Result: No metrics for validation failures!
""")

print("\n4. PROOF FROM CODE:")
print("-" * 80)

print("\nFrom schema_routes.py line 141-161:")
print("""
class PropertyCreateRequest(BaseModel):
    name: str = Field(..., pattern="^[a-zA-Z][a-zA-Z0-9_]*$")  # <-- Pydantic validation!
    ...
    @validator('dataType')
    def validate_data_type(cls, v):
        allowed_types = [...]
        if v not in allowed_types:
            raise ValueError(f"Invalid dataType...")  # <-- Returns 422, bypasses middleware!
""")

print("\nFrom EnterpriseValidationMiddleware line 119-124:")
print("""
async def dispatch(self, request: Request, call_next):
    # Skip validation for excluded endpoints
    if self._should_skip_validation(request):
        return await call_next(request)  # <-- Never reaches here for 422 errors!
""")

print("\n5. WHY ENTERPRISE VALIDATION ISN'T WORKING:")
print("-" * 80)
print("""
1. **Wrong validation point**: Middleware runs too early in the request flow
2. **No access to parsed data**: Middleware gets raw request body, not parsed models
3. **Can't override Pydantic**: FastAPI's exception handlers take precedence
4. **Metrics blind spot**: Failed validations aren't tracked
5. **Information leakage**: Pydantic errors expose internal details
""")

print("\n6. EVIDENCE OF THE ISSUE:")
print("-" * 80)
print("""
Test these endpoints with bad data:

POST /api/v1/schemas/main/semantic-types
Body: {"name": "Test", "displayName": "Test", "baseType": "invalid"}
Result: 422 with Pydantic error details (not sanitized)

POST /api/v1/schemas/main/properties  
Body: {"name": "123invalid", "displayName": "Test", "dataType": "string"}
Result: 422 with pattern match error (reveals regex pattern)

The Enterprise Validation Service with all its rules (NamingConventionRule,
DataTypeValidationRule, etc.) is NEVER invoked for these requests!
""")

print("\n7. SOLUTION APPROACHES:")
print("-" * 80)
print("""
To fix this, you need to:

1. **Custom exception handler**: Override FastAPI's RequestValidationError handler
2. **Move validation**: Use Dict/Any in endpoints, validate manually  
3. **Disable Pydantic validation**: Set models to skip validation
4. **Pre-parse middleware**: Intercept and validate before FastAPI
5. **Dependency injection**: Use Depends() to run validation

The current architecture fundamentally conflicts with FastAPI's design!
""")