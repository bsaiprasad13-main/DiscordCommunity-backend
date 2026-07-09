import os
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db
from models import User

load_dotenv()

app = FastAPI()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/auth/login")
def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    discord_auth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(discord_auth_url)

@app.get("/auth/callback")
async def callback(code: str, db: Session = Depends(get_db)):
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        token_response = await client.post("https://discord.com/api/oauth2/token", data=token_data, headers=headers)
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch access token")
        
        access_token = token_response.json().get("access_token")
        
        user_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user data")
        
        user_data = user_response.json()
        discord_id = str(user_data.get("id"))
        username = user_data.get("username")

    user = db.query(User).filter(User.discord_id == discord_id).first()
    if user:
        user.username = username
    else:
        user = User(discord_id=discord_id, username=username)
        db.add(user)
    
    db.commit()
    db.refresh(user)

    return {"discord_id": user.discord_id, "username": user.username}
