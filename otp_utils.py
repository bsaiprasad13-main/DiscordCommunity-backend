import os
import random
import hashlib
import smtplib
import socket
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# --- Force IPv4 for all socket connections (fixes Railway IPv6 DNS hang) ---
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Force family to AF_INET so the DNS resolver never queries for IPv6 (AAAA) addresses
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_only_getaddrinfo
# ----------------------------------------------------------------------------

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()

def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    return hash_otp(otp) == otp_hash

def send_otp_email(to_email: str, otp: str) -> bool:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Warning: GMAIL credentials not set. Cannot send OTP.")
        return False

    msg = EmailMessage()
    msg.set_content(f"Your verification code is: {otp}\n\nNote: This code expires in 10 minutes.")
    msg["Subject"] = "Your CampusGuide Verification Code"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False