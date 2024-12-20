from pydantic import BaseModel
from fastapi import UploadFile
from typing import Optional

class UserCreate(BaseModel):
    login: str
    password: str

class UserLogin(BaseModel):
    login: str
    password: str

class PostCreate(BaseModel):
    post_name: str
    login: str
    audio: Optional[UploadFile] = None
    video: Optional[UploadFile] = None
    text: Optional[UploadFile] = None
    text_name: str
    img: Optional[UploadFile] = None

class Post(BaseModel):
    id: int
    user_id: int
    post_name: str
    likes: int
    favorites: int
    views: int
    created_at: str
    login: str