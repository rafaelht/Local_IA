from typing import Optional

from pydantic import BaseModel, Field


class UserPreferenceRead(BaseModel):
    theme: str
    dev_mode: bool
    default_provider: str
    default_model: Optional[str] = None
    ollama_api_url: Optional[str] = None
    litert_api_url: Optional[str] = None
    temperature: float
    context_length: int

    model_config = {'from_attributes': True}


class UserPreferenceUpdate(BaseModel):
    theme: Optional[str] = None
    dev_mode: Optional[bool] = None
    default_provider: Optional[str] = None
    default_model: Optional[str] = None
    ollama_api_url: Optional[str] = None
    litert_api_url: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    context_length: Optional[int] = Field(default=None, ge=512, le=131072)


class FavoriteModelRead(BaseModel):
    id: int
    provider_name: str
    model_name: str
    temperature: float
    context_length: int

    model_config = {'from_attributes': True}


class FavoriteModelCreate(BaseModel):
    provider_name: str
    model_name: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    context_length: int = Field(default=2048, ge=512, le=131072)
