import os
import random
import hashlib
import httpx
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = "CampusGuide <verify@mail.campusguide.site>"

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()

def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    return hash_otp(otp) == otp_hash

def send_otp_email(to_email: str, otp: str) -> bool:
    if not RESEND_API_KEY:
        print("Warning: RESEND_API_KEY not set. Cannot send OTP.")
        return False

    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": "Your CampusGuide Verification Code",
                "text": f"Your verification code is: {otp}\n\nNote: This code expires in 10 minutes.",
            },
            timeout=10,
        )
        if response.status_code >= 400:
            print(f"Error sending email: {response.status_code} - {response.text}")
            return False
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False