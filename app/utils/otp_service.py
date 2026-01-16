"""
Crisis Command Center - OTP Service
Using pyotp for TOTP generation and Twilio for SMS delivery
"""
import pyotp
import redis
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from config import settings


class OTPService:
    """
    OTP generation, storage (Redis), and verification service
    """
    
    def __init__(self):
        self.redis_client = None
        self.twilio_client = None
        self._init_redis()
        self._init_twilio()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}")
            # Fallback to in-memory storage for development
            self.redis_client = None
            self._memory_store = {}
    
    def _init_twilio(self):
        """Initialize Twilio client"""
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.twilio_client = TwilioClient(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
            except Exception as e:
                print(f"Twilio init failed: {e}")
                self.twilio_client = None
    
    def _generate_otp(self, length: int = 6) -> str:
        """Generate numeric OTP"""
        totp = pyotp.TOTP(pyotp.random_base32(), digits=length)
        return totp.now()
    
    def _hash_otp(self, otp: str) -> str:
        """Hash OTP for storage"""
        return hashlib.sha256(otp.encode()).hexdigest()
    
    def _get_redis_key(self, mobile: str, purpose: str) -> str:
        """Generate Redis key for OTP storage"""
        return f"otp:{mobile}:{purpose}"
    
    def _store_otp(self, mobile: str, otp_hash: str, purpose: str, ttl: int = None):
        """Store OTP hash in Redis or memory"""
        ttl = ttl or settings.OTP_EXPIRE_SECONDS
        key = self._get_redis_key(mobile, purpose)
        
        if self.redis_client:
            self.redis_client.setex(key, ttl, otp_hash)
        else:
            # Memory fallback
            self._memory_store[key] = {
                'hash': otp_hash,
                'expires': datetime.utcnow() + timedelta(seconds=ttl)
            }
    
    def _get_stored_otp(self, mobile: str, purpose: str) -> Optional[str]:
        """Retrieve stored OTP hash"""
        key = self._get_redis_key(mobile, purpose)
        
        if self.redis_client:
            return self.redis_client.get(key)
        else:
            # Memory fallback
            data = self._memory_store.get(key)
            if data and data['expires'] > datetime.utcnow():
                return data['hash']
            return None
    
    def _delete_otp(self, mobile: str, purpose: str):
        """Delete OTP after verification"""
        key = self._get_redis_key(mobile, purpose)
        
        if self.redis_client:
            self.redis_client.delete(key)
        else:
            self._memory_store.pop(key, None)
    
    def send_otp(self, mobile: str, purpose: str = "verification") -> Tuple[bool, str]:
        """
        Generate and send OTP via SMS
        Returns (success, message)
        """
        # Normalize mobile number
        if not mobile.startswith('+'):
            mobile = f"+91{mobile}"  # Default to India
        
        # Generate OTP
        otp = self._generate_otp()
        otp_hash = self._hash_otp(otp)
        
        # Store OTP
        self._store_otp(mobile, otp_hash, purpose)
        
        # Send SMS via Twilio
        if self.twilio_client and settings.TWILIO_PHONE_NUMBER:
            try:
                message = self.twilio_client.messages.create(
                    body=f"Your Crisis Command Center verification code is: {otp}. Valid for 5 minutes.",
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=mobile
                )
                return True, f"OTP sent to {mobile[-4:]}"
            except TwilioRestException as e:
                return False, f"SMS failed: {str(e)}"
        else:
            # Development mode - log OTP
            print(f"[DEV] OTP for {mobile}: {otp}")
            return True, f"OTP generated (dev mode): {otp}"
    
    def verify_otp(self, mobile: str, otp: str, purpose: str = "verification") -> Tuple[bool, str]:
        """
        Verify OTP
        Returns (success, message)
        """
        if not mobile.startswith('+'):
            mobile = f"+91{mobile}"
        
        stored_hash = self._get_stored_otp(mobile, purpose)
        
        if not stored_hash:
            return False, "OTP expired or not found"
        
        provided_hash = self._hash_otp(otp)
        
        if stored_hash == provided_hash:
            self._delete_otp(mobile, purpose)
            return True, "OTP verified successfully"
        else:
            return False, "Invalid OTP"
    
    def resend_otp(self, mobile: str, purpose: str = "verification") -> Tuple[bool, str]:
        """Resend OTP (invalidates previous)"""
        self._delete_otp(mobile, purpose)
        return self.send_otp(mobile, purpose)


# Singleton instance
otp_service = OTPService()
