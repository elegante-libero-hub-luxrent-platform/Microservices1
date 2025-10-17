from __future__ import annotations

import os
import socket
from datetime import datetime

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi import Query, Path
from typing import Optional

from models.user import UserCreate, UserUpdate, UserRead
from models.profile import ProfileCreate, ProfileRead, ProfileUpdate

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# In-memory "databases"
#   - `users` holds public-safe user data (UserRead)
#   - `user_secrets` holds sensitive data (plaintext password for demo)
# -----------------------------------------------------------------------------
users: Dict[UUID, UserRead] = {}
user_secrets: Dict[UUID, dict] = {}  # { user_id: {"password": "<plaintext>"} }
profiles: Dict[UUID, ProfileRead] = {}            # primary store by profile_id
profiles_by_user: Dict[UUID, UUID] = {}           # ensure 1:1 (user_id -> profile_id)

app = FastAPI(
    title="Person/Address API",
    description="Demo FastAPI app using Pydantic v2 models for Person and Address",
    version="0.1.0",
)


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
def _email_exists(email: str, exclude_id: Optional[UUID] = None) -> bool:
    """
    Check whether an email already exists among users.
    `exclude_id` lets you ignore a specific user (useful during updates).
    """
    e = email.lower()
    for u in users.values():
        if u.email.lower() == e and (exclude_id is None or u.id != exclude_id):
            return True
    return False


def _phone_exists(phone: str, exclude_id: Optional[UUID] = None) -> bool:
    """
    Check whether a phone number already exists among users.
    `exclude_id` lets you ignore a specific user (useful during updates).
    """
    for u in users.values():
        if u.phone == phone and (exclude_id is None or u.id != exclude_id):
            return True
    return False


def _find_user_by_email(email: str) -> Optional[UserRead]:
    """
    Find a user object by email (case-insensitive).
    Returns the UserRead instance or None if not found.
    """
    e = email.lower()
    for u in users.values():
        if u.email.lower() == e:
            return u
    return None

def _username_exists(username: str, exclude_id: Optional[UUID] = None) -> bool:
    """
    Check case-insensitive uniqueness for username.
    """
    target = username.lower()
    for pid, prof in profiles.items():
        if prof.username.lower() == target and (exclude_id is None or pid != exclude_id):
            return True
    return False

def _assert_user_exists(user_id: UUID):
    """
    Ensure the referenced user exists in the in-memory users DB.
    """
    if user_id not in users:
        raise HTTPException(status_code=400, detail="User does not exist")

def _assert_user_has_no_profile(user_id: UUID):
    """
    Ensure 1:1 relationship: a user can have only one profile.
    """
    if user_id in profiles_by_user:
        raise HTTPException(status_code=400, detail="User already has a profile")
# -----------------------------------------------------------------------------
# Users CRUD
# -----------------------------------------------------------------------------
@app.post("/users", response_model=UserRead, status_code=201, tags=["users"])
def create_user(payload: UserCreate):
    """
    Create a new user.
    - Enforces email and phone uniqueness.
    - Persists public fields in `users` (UserRead).
    - Stores plaintext password in `user_secrets` (DEMO ONLY).
    """
    if _email_exists(payload.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    if _phone_exists(payload.phone):
        raise HTTPException(status_code=400, detail="Phone already exists")

    # Build the public-safe UserRead (no password inside)
    user = UserRead(**payload.model_dump(exclude={"password"}))
    users[user.id] = user

    # Store plaintext password for demo purposes
    user_secrets[user.id] = {"password": payload.password.get_secret_value()}

    return user


@app.get("/users", response_model=List[UserRead], tags=["users"])
def list_users(
    name: Optional[str] = Query(None, description="Filter by exact name"),
    email: Optional[str] = Query(None, description="Filter by exact email (case-insensitive)"),
    phone: Optional[str] = Query(None, description="Filter by exact phone"),
    membership_tier: Optional[str] = Query(None, description='Filter by tier: "FREE"|"PRO"|"PROMAX"'),
):
    """
    List users with optional exact-match filters.
    """
    results = list(users.values())

    if name is not None:
        results = [u for u in results if u.name == name]
    if email is not None:
        e = email.lower()
        results = [u for u in results if u.email.lower() == e]
    if phone is not None:
        results = [u for u in results if u.phone == phone]
    if membership_tier is not None:
        results = [u for u in results if u.membership_tier == membership_tier]

    return results


@app.get("/users/{user_id}", response_model=UserRead, tags=["users"])
def get_user(user_id: UUID = Path(..., description="User ID (UUID)")):
    """
    Retrieve a single user by ID.
    """
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return users[user_id]


@app.patch("/users/{user_id}", response_model=UserRead, tags=["users"])
def update_user(user_id: UUID, patch: UserUpdate):
    """
    Partially update a user.
    - Only applies fields present in the request body (PATCH semantics).
    - Enforces uniqueness if email/phone is being changed.
    - Updates plaintext password if `new_password` is provided.
    """
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    current = users[user_id].model_dump()
    changes = patch.model_dump(exclude_unset=True, exclude={"new_password"})

    # Uniqueness checks for fields that may change
    new_email = changes.get("email")
    if new_email and _email_exists(new_email, exclude_id=user_id):
        raise HTTPException(status_code=400, detail="Email already exists")

    new_phone = changes.get("phone")
    if new_phone and _phone_exists(new_phone, exclude_id=user_id):
        raise HTTPException(status_code=400, detail="Phone already exists")

    # Merge and rebuild UserRead
    current.update(changes)
    users[user_id] = UserRead(**current)

    # Update plaintext password if provided
    if patch.new_password is not None:
        user_secrets[user_id] = {"password": patch.new_password.get_secret_value()}

    return users[user_id]


@app.delete("/users/{user_id}", status_code=204, tags=["users"])
def delete_user(user_id: UUID):
    """
    Delete a user and its associated secret record.
    """
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    users.pop(user_id, None)
    user_secrets.pop(user_id, None)
    return None
# -----------------------------------------------------------------------------
# Users CRUD Endpoint
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Profile CRUD
# -----------------------------------------------------------------------------
@app.post("/profiles", response_model=ProfileRead, status_code=201, tags=["profiles"])
def create_profile(payload: ProfileCreate):
    """
    Create profile for a user.
    - Validates user existence.
    - Enforces 1:1 (a user can own only one profile).
    - Enforces case-insensitive unique username.
    """
    _assert_user_exists(payload.user_id)
    _assert_user_has_no_profile(payload.user_id)

    if _username_exists(payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    profile = ProfileRead(**payload.model_dump())
    profiles[profile.id] = profile
    profiles_by_user[profile.user_id] = profile.id
    return profile


@app.get("/profiles", response_model=List[ProfileRead], tags=["profiles"])
def list_profiles(
    user_id: Optional[UUID] = Query(None, description="Filter by owner user_id"),
    username: Optional[str] = Query(None, description="Filter by exact username (case-insensitive)")
):
    """
    List profiles with optional filters.
    """
    results = list(profiles.values())
    if user_id is not None:
        results = [p for p in results if p.user_id == user_id]
    if username is not None:
        u = username.lower()
        results = [p for p in results if p.username.lower() == u]
    return results


@app.get("/profiles/{profile_id}", response_model=ProfileRead, tags=["profiles"])
def get_profile(profile_id: UUID = Path(..., description="Profile ID (UUID)")):
    """
    Retrieve a single profile by ID.
    """
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profiles[profile_id]


@app.patch("/profiles/{profile_id}", response_model=ProfileRead, tags=["profiles"])
def update_profile(profile_id: UUID, patch: ProfileUpdate):
    """
    Partially update a profile.
    - Only applies provided fields (PATCH semantics).
    - If username is updated, enforce case-insensitive uniqueness.
    - If user_id were mutable (not recommended), we would re-enforce 1:1; but here user_id is immutable.
    """
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    current = profiles[profile_id].model_dump()
    changes = patch.model_dump(exclude_unset=True)

    # Enforce username uniqueness if it is being changed
    new_username = changes.get("username")
    if new_username and _username_exists(new_username, exclude_id=profile_id):
        raise HTTPException(status_code=400, detail="Username already exists")

    current.update(changes)
    updated = ProfileRead(**current)
    profiles[profile_id] = updated
    return updated


@app.delete("/profiles/{profile_id}", status_code=204, tags=["profiles"])
def delete_profile(profile_id: UUID):
    """
    Delete a profile and its user->profile mapping.
    """
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    prof = profiles.pop(profile_id)
    profiles_by_user.pop(prof.user_id, None)
    return None
# -----------------------------------------------------------------------------
# Profile CRUD Endpoint
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the User & Profile Service. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint for `python main.py`
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
