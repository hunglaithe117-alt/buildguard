from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.services.github_token_service import GitHubTokenService
from app.middleware.auth import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])
token_service = GitHubTokenService()


class TokenCreate(BaseModel):
    token: str
    type: str = "pat"


class TokenResponse(BaseModel):
    id: str
    token: str
    type: str
    remaining: int
    reset_time: float
    disabled: bool
    added_at: float
    last_used: float = 0.0


@router.get("/", response_model=List[TokenResponse])
def list_tokens() -> Any:
    """
    List all GitHub tokens.
    """
    tokens = token_service.list_tokens()
    # Mask tokens for security
    for t in tokens:
        if len(t["token"]) > 8:
            t["token"] = f"{t['token'][:4]}...{t['token'][-4:]}"
    return tokens


@router.post("/", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
def add_token(token_in: TokenCreate) -> Any:
    """
    Add a new GitHub token.
    """
    success = token_service.add_token(token_in.token, token_in.type)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add token",
        )
    return {"message": "Token added successfully"}


@router.delete("/{token_id}", response_model=Dict[str, str])
def remove_token(token_id: str) -> Any:
    """
    Remove a GitHub token by ID.
    """
    token_doc = token_service.get_token(token_id)
    if not token_doc:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    
    success = token_service.remove_token(token_doc["token"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove token",
        )
    return {"message": "Token removed successfully"}
