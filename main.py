import os
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from datetime import datetime, timezone, timedelta
from database import get_db
from models import User, OTPCode, LinkClick
from otp_utils import generate_otp, hash_otp, verify_otp_hash, send_otp_email
from discord_utils import assign_verified_role, remove_verified_role, send_dm
load_dotenv()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
templates = Jinja2Templates(directory="templates")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
serializer = URLSafeTimedSerializer(SECRET_KEY)

DISCORD_INVITE_URL = "https://discord.gg/eJqYwt7be3"

FUNNEL_STAGES = [
    ("invite_clicked", "Clicked invite link"),
    ("member_joined", "Joined server (@everyone assigned)"),
    ("verify_link_clicked", "Clicked verify link"),
    ("email_page_reached", "Reached email page"),
    ("otp_page_reached", "Reached OTP page"),
    ("verified_page_reached", "Reached success page"),
    ("role_assigned", "Verified student role assigned"),
]


def log_event(db: Session, stage: str):
    db.add(LinkClick(stage=stage))
    db.commit()


def require_admin(request: Request):
    cookie = request.cookies.get("admin_session")
    if not cookie:
        return False
    try:
        serializer.loads(cookie, max_age=60 * 60 * 24 * 7)  # 7 days
        return True
    except (BadSignature, SignatureExpired):
        return False


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/join")
def join_redirect(db: Session = Depends(get_db)):
    log_event(db, "invite_clicked")
    return RedirectResponse(DISCORD_INVITE_URL, status_code=302)


@app.get("/admin/login")
def admin_login_form(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {})


@app.post("/admin/login")
def admin_login_submit(request: Request, password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin_login.html", {
            "error": "Incorrect password"
        })
    response = RedirectResponse("/admin/dashboard", status_code=303)
    session_token = serializer.dumps("admin_authenticated")
    response.set_cookie(
        "admin_session",
        session_token,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return response


@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


@app.get("/admin/dashboard")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if not require_admin(request):
        return RedirectResponse("/admin/login", status_code=303)

    counts_by_stage = dict(
        db.query(LinkClick.stage, func.count(LinkClick.id))
        .group_by(LinkClick.stage)
        .all()
    )

    funnel = []
    previous_count = None
    for key, label in FUNNEL_STAGES:
        count = counts_by_stage.get(key, 0)
        drop_off = None
        if previous_count is not None and previous_count > 0:
            drop_off = round(100 * (previous_count - count) / previous_count, 1)
        funnel.append({"key": key, "label": label, "count": count, "drop_off": drop_off})
        previous_count = count if count > 0 else previous_count

    return templates.TemplateResponse(request, "admin_dashboard.html", {
        "funnel": funnel
    })


@app.get("/auth/login")
def login(db: Session = Depends(get_db)):
    log_event(db, "verify_link_clicked")
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

    if user.verified:
        success = await assign_verified_role(discord_id)
        return templates.TemplateResponse(request, "already_verified.html", {
            "username": user.username,
            "role_assigned": success
        })

    discord_token = serializer.dumps(user.discord_id)

    log_event(db, "email_page_reached")
    return templates.TemplateResponse(request, "email.html", {
        "discord_token": discord_token,
        "username": user.username
    })

@app.post("/auth/email")
@limiter.limit("3/10minutes")
def submit_email(request: Request, email: str = Form(...), discord_token: str = Form(...), db: Session = Depends(get_db)):
    try:
        discord_id = serializer.loads(discord_token, max_age=1800)
    except (BadSignature, SignatureExpired):
        return RedirectResponse("/auth/login", status_code=303)

    user = db.query(User).filter(User.discord_id == discord_id).first()
    username = user.username if user else ""

    if not email.lower().endswith("@smail.iitm.ac.in"):
        return templates.TemplateResponse(request, "email.html", {
            "discord_token": discord_token,
            "username": username,
            "error": "Please use your IITM email address ending in @smail.iitm.ac.in"
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
            "discord_token": discord_token,
            "username": username,
            "error": "We couldn't send the verification email right now. Please try again in a moment."
        })

    log_event(db, "otp_page_reached")
    # Render OTP page, passing signed token along
    return templates.TemplateResponse(request, "otp.html", {
        "discord_token": discord_token,
        "email": email
    })

@app.post("/auth/verify-otp")
@limiter.limit("5/10minutes")
async def verify_otp(request: Request, otp: str = Form(...), discord_token: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    try:
        discord_id = serializer.loads(discord_token, max_age=1800)
    except (BadSignature, SignatureExpired):
        return RedirectResponse("/auth/login", status_code=303)

    otp_record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.used == False
    ).order_by(OTPCode.created_at.desc()).first()

    now = datetime.now(timezone.utc)

    if not otp_record or otp_record.expires_at < now or not verify_otp_hash(otp, otp_record.otp_hash):
        return templates.TemplateResponse(request, "otp.html", {
            "discord_token": discord_token,
            "email": email,
            "error": "Invalid or expired code, please try again"
        })

    # Check for duplicate verified email — transfer verification if found
    conflict_user = db.query(User).filter(
        User.email == email,
        User.verified == True,
        User.discord_id != discord_id
    ).first()

    if conflict_user:
        old_discord_id = conflict_user.discord_id
        await remove_verified_role(old_discord_id)
        conflict_user.verified = False
        conflict_user.email = None
        conflict_user.verified_at = None
        db.commit()

        await send_dm(
            old_discord_id,
            f"Your CampusGuide verification for {email} has just been transferred to a different Discord account. "
            f"If this wasn't you, please reply to this message right away."
        )

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
    else:
        log_event(db, "role_assigned")

    log_event(db, "verified_page_reached")
    return templates.TemplateResponse(request, "success.html", {
        "discord_id": discord_id,
        "guild_id": DISCORD_GUILD_ID
    })