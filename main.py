import os
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from datetime import datetime, timezone, timedelta
from database import get_db
from models import User, OTPCode
from otp_utils import generate_otp, hash_otp, verify_otp_hash, send_otp_email
from discord_utils import assign_verified_role
load_dotenv()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
templates = Jinja2Templates(directory="templates")

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
async def callback(request: Request, code: str, db: Session = Depends(get_db)):
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

    return templates.TemplateResponse(request, "email.html", {
        "discord_id": user.discord_id,
        "username": user.username
    })

@app.post("/auth/email")
@limiter.limit("3/10minutes")
def submit_email(request: Request, email: str = Form(...), discord_id: str = Form(...), username: str = Form(...), db: Session = Depends(get_db)):
    if not email.lower().endswith("@smail.iitm.ac.in"):
        return templates.TemplateResponse(request, "email.html", {
            "discord_id": discord_id,
            "username": username,
            "error": "Please use your IITM email address ending in @smail.iitm.ac.in"
        })

    # Check for duplicate verified email before sending OTP
    conflict_user = db.query(User).filter(
        User.email == email,
        User.verified == True,
        User.discord_id != discord_id
    ).first()

    if conflict_user:
        return templates.TemplateResponse(request, "email.html", {
            "discord_id": discord_id,
            "username": username,
            "error": "This email is already linked to another verified Discord account."
        })

    otp = generate_otp()
    otp_code = OTPCode(
        email=email,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    db.add(otp_code)
    db.commit()

    email_sent = send_otp_email(email, otp)
    
    if not email_sent:
        return templates.TemplateResponse(request, "email.html", {
            "discord_id": discord_id,
            "username": username,
            "error": "We couldn't send the verification email right now. Please try again in a moment."
        })

    # Render OTP page, passing discord_id along
    return templates.TemplateResponse(request, "otp.html", {
        "discord_id": discord_id,
        "email": email
    })

@app.post("/auth/verify-otp")
@limiter.limit("5/10minutes")
async def verify_otp(request: Request, otp: str = Form(...), discord_id: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    otp_record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.used == False
    ).order_by(OTPCode.created_at.desc()).first()

    now = datetime.now(timezone.utc)

    if not otp_record or otp_record.expires_at < now or not verify_otp_hash(otp, otp_record.otp_hash):
        return templates.TemplateResponse(request, "otp.html", {
            "discord_id": discord_id,
            "email": email,
            "error": "Invalid or expired code, please try again"
        })

    # Check for duplicate verified email
    conflict_user = db.query(User).filter(
        User.email == email,
        User.verified == True,
        User.discord_id != discord_id
    ).first()

    if conflict_user:
        return templates.TemplateResponse(request, "otp.html", {
            "discord_id": discord_id,
            "email": email,
            "error": "This email is already linked to another verified Discord account. Please contact support if you believe this is an error."
        })

    otp_record.used = True
    
    user = db.query(User).filter(User.discord_id == discord_id).first()
    if user:
        user.email = email
        user.verified = True
        user.verified_at = now

    db.commit()

    success = await assign_verified_role(discord_id)
    if not success:
        print(f"WARNING: Failed to assign verified role to Discord user {discord_id}.")
    return templates.TemplateResponse(request, "success.html", {
        "discord_id": discord_id
    })
