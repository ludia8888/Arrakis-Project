#!/usr/bin/env python3
"""
Fix User Service to simplify role handling
Remove database role operations from create_user for now
"""

# Simplified create_user without database role operations
simplified_create_user = '''
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role_names: List[str] = None,
        created_by: str = "system"
    ) -> User:
        """
        Create new user with race condition protection
        """
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_-]{3,32}$', username):
            raise ValueError("Username must be 3-32 characters, alphanumeric, underscore, or hyphen only")
        
        # Validate email format
        try:
            email_validator = EmailStr._validate(email)
        except Exception:
            raise ValueError("Invalid email format")
        
        # Validate password strength
        if not self._validate_password(password):
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters with uppercase, lowercase, number, and special character")
        
        # Hash password
        password_hash = get_password_hash(password)
        
        try:
            # Create user
            user = User(
                id=str(uuid.uuid4()),
                username=username,
                email=email,
                full_name=full_name,
                password_hash=password_hash,
                status=UserStatus.ACTIVE,
                password_changed_at=datetime.now(timezone.utc),
                created_by=created_by,
                created_at=datetime.now(timezone.utc)
            )
            
            self.db.add(user)
            
            # TODO: Implement proper role assignment when role management is ready
            # For now, just validate roles
            if role_names:
                role_service = RoleService()
                validated_roles = role_service.validate_roles(role_names)
                # Store validated roles in a JSON field or separate table later
                logger.info(f"User {username} would be assigned roles: {validated_roles}")
            
            # Force flush to trigger UNIQUE constraint check
            await self.db.flush()
            
            # Log user creation audit event
            try:
                await self.audit_service.log_event(
                    event_type=EventType.USER_CREATED,
                    status=EventStatus.SUCCESS,
                    user_id=user.id,
                    details={
                        "username": username,
                        "email": email,
                        "created_by": created_by,
                        "roles": role_names or []
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log user creation audit: {e}")
            
            await self.db.commit()
            await self.db.refresh(user)
            
            # Clear any cached user data
            await self._invalidate_user_cache(user.id)
            
            logger.info(f"User created successfully: {username}")
            return user
            
        except IntegrityError as e:
            await self.db.rollback()
            
            # Check which constraint was violated
            if "username" in str(e):
                existing_user = await self.get_user_by_username(username)
                if existing_user:
                    raise ValueError(f"User already exists with username: {username}")
            elif "email" in str(e):
                existing_user = await self.get_user_by_email(email)
                if existing_user:
                    raise ValueError(f"User already exists with email: {email}")
            
            # Generic integrity error
            raise ValueError("Failed to create user due to data conflict")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise ValueError(f"Failed to create user: {str(e)}")
'''

# Simplified create_default_user
simplified_create_default_user = '''
    async def create_default_user(self):
        """Create default test user if it doesn't exist with race condition protection"""
        existing_user = await self.get_user_by_username("testuser")
        if not existing_user:
            try:
                user = await self.create_user(
                    username="testuser",
                    email="test@example.com",
                    password="Test123!",
                    full_name="Test User",
                    role_names=["admin"],  # Just pass role names, actual assignment will be done later
                    created_by="system"
                )
                
                logger.info(f"Created default test user: {user.username}")
                return user
                
            except ValueError as e:
                # If user creation fails due to race condition, try to get the user again
                if "User already exists" in str(e):
                    existing_user = await self.get_user_by_username("testuser")
                    if existing_user:
                        return existing_user
                # Re-raise other ValueError types
                raise
        return existing_user
'''

print("Fixes prepared for User Service role handling.")
print("The service needs to be updated to remove database role operations until proper role management is implemented.")