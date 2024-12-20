from fastapi import FastAPI, Depends, HTTPException, Form, File, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import os
import magic
import uuid
from io import BytesIO
import base64
from datetime import datetime
from db import get_db_connection, hash_password, check_password
from models import UserCreate, UserLogin, PostCreate, Post
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware



app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="very-and-truly-secret-key122")
templates = Jinja2Templates(directory="templates")



def get_user_id(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=403, detail="You must be logged in")
    return user_id

def get_user_login(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=403, detail="You must be logged in")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT login FROM users WHERE id = ?', (user_id,))
    user_login = cursor.fetchone()
    conn.close()

    if not user_login:
        raise HTTPException(status_code=403, detail="User login not found")
    
    return user_login[0]

def check_file_type(file: UploadFile, allowed_type: str):
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension != allowed_type:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Expected {allowed_type} but got {file_extension}")

def process_posts(posts):
    processed_posts = []
    for post in posts:
        post_dict = {
            'id': post[0],
            'user_id': post[1],
            'post_name': post[2],
            'likes': post[3],
            'favorites': post[4],
            'views': post[5],
            'audio': None,
            'video': None,
            'text': None,
            'text_name': post[9],
            'img': None,
            'created_at': post[11],
            'login': post[12]
        }

        if post[10]:
            image_data = post[10]
            encoded_img = base64.b64encode(image_data).decode('utf-8')
            post_dict['img'] = f"data:image/png;base64,{encoded_img}"

        if post[7]:
            video_data = post[7]
            encoded_video = base64.b64encode(video_data).decode('utf-8')
            post_dict['video'] = f"data:video/mp4;base64,{encoded_video}"

        if post[6]:
            audio_data = post[6]
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            post_dict['audio'] = f"data:audio/mp3;base64,{encoded_audio}"

        if post[8]:
            pdf_data = post[8]
            encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
            post_dict['text'] = f"data:application/pdf;base64,{encoded_pdf}"

        processed_posts.append(post_dict)
    return processed_posts



@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/posts", response_class=HTMLResponse)
async def posts(request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts')
    posts = cursor.fetchall()

    processed_posts = process_posts(posts)

    conn.close()
    return templates.TemplateResponse("posts.html", {"request": request, "posts": processed_posts})


@app.get("/posts/{id}", response_class=HTMLResponse)
async def posts_detail(request: Request, id: int):
    user_id = request.session.get("user_id")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?', (user_id, id))
    is_liked = cursor.fetchone() is not None

    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND post_id = ?', (user_id, id))
    is_favorite = cursor.fetchone() is not None

    cursor.execute('SELECT * FROM posts WHERE id = ?', (id,))
    post = cursor.fetchone()

    post_data = process_posts([post])[0]
    post_data['is_liked'] = is_liked
    post_data['is_favorite'] = is_favorite

    conn.close()

    return templates.TemplateResponse("post_detail.html", {"request": request, "post": post_data})



@app.get("/post-create", response_class=HTMLResponse)
async def post_create(request: Request):
    return templates.TemplateResponse("post_create.html", {"request": request})



@app.post("/register")
async def register(user: UserCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE login = ?", (user.login,))
    existing_user = cursor.fetchone()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed_password = hash_password(user.password)
    cursor.execute("INSERT INTO users (login, password, registered_at) VALUES (?, ?, ?)",
                   (user.login, hashed_password, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/login", status_code=303)

@app.post("/login")
async def login(user: UserLogin, request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE login = ?", (user.login,))
    db_user = cursor.fetchone()
    conn.close()
    if db_user and check_password(db_user['password'], user.password):
        request.session['user_id'] = db_user['id']
        return RedirectResponse(url="/posts", status_code=303)
    raise HTTPException(status_code=400, detail="Invalid credentials")

@app.post("/post-create")
async def post_create_action(
    post_name: str = Form(...),
    login: str = Depends(get_user_login),
    audio: UploadFile = File(None),
    video: UploadFile = File(None),
    text: UploadFile = File(None),
    img: UploadFile = File(None),
    user_id: int = Depends(get_user_id)
):
    audio_data = await audio.read() if audio else None
    video_data = await video.read() if video else None
    text_data = await text.read() if text else None
    img_data = await img.read() if img else None

    if not (audio_data or video_data or text_data or img_data):
        return JSONResponse(status_code=400, content={"detail": "At least one file (audio, video, text, or image) must be uploaded"})

    if audio and audio_data:
        check_file_type(audio, '.mp3')
    if video and video_data:
        check_file_type(video, '.mp4')
    if text and text_data:
        check_file_type(text, '.pdf')
    if img and img_data:
        check_file_type(img, '.png')

    created_at = datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    print(text.filename)
    cursor.execute('''
        INSERT INTO posts (user_id, post_name, likes, favorites, views, audio, video, text, text_name, img, created_at, login) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, 
        post_name, 
        0, 0, 0, 
        audio_data, 
        video_data, 
        text_data,
        text.filename,
        img_data, 
        created_at,
        login
    ))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/posts", status_code=303)

@app.post("/like/{post_id}")
async def like_post(post_id: int, request: Request, user_id: int = Depends(get_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
    already_liked = cursor.fetchone()

    if already_liked:
        cursor.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        cursor.execute('UPDATE posts SET likes = likes - 1 WHERE id = ?', (post_id,))
    else:
        cursor.execute('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
        cursor.execute('UPDATE posts SET likes = likes + 1 WHERE id = ?', (post_id,))

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

@app.post("/favorite/{post_id}")
async def favorite_post(post_id: int, request: Request, user_id: int = Depends(get_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND post_id = ?', (user_id, post_id))
    already_favorite = cursor.fetchone()

    if already_favorite:
        cursor.execute('DELETE FROM favorites WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        cursor.execute('UPDATE posts SET favorites = favorites - 1 WHERE id = ?', (post_id,))
    else:
        cursor.execute('INSERT INTO favorites (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
        cursor.execute('UPDATE posts SET favorites = favorites + 1 WHERE id = ?', (post_id,))

    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)




import uvicorn
uvicorn.run(app=app)