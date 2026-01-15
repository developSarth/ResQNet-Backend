"""
Crisis Command Center - Encryption Utilities
HS256 / Fernet encryption for sensitive documents
"""
import os
import hashlib
import hmac
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Tuple, Optional
from app.config import settings


class DocumentEncryption:
    """
    Encryption utility for government documents using Fernet (symmetric encryption)
    with HS256 for key derivation and verification
    """
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or settings.SECRET_KEY
        self._fernet = None
    
    def _get_fernet(self, salt: bytes = None) -> Tuple[Fernet, bytes]:
        """Generate Fernet instance with derived key"""
        if salt is None:
            salt = os.urandom(16)
        
        # Derive key using PBKDF2 with HS256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key), salt
    
    def encrypt(self, data: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt data and return (encrypted_data, salt)
        Salt is needed for decryption
        """
        fernet, salt = self._get_fernet()
        encrypted = fernet.encrypt(data)
        return encrypted, salt
    
    def decrypt(self, encrypted_data: bytes, salt: bytes) -> bytes:
        """Decrypt data using the stored salt"""
        fernet, _ = self._get_fernet(salt)
        return fernet.decrypt(encrypted_data)
    
    def encrypt_file(self, file_path: str) -> Tuple[bytes, bytes]:
        """Encrypt file contents"""
        with open(file_path, 'rb') as f:
            data = f.read()
        return self.encrypt(data)
    
    def decrypt_file(self, encrypted_data: bytes, salt: bytes, output_path: str) -> str:
        """Decrypt and save to file"""
        decrypted = self.decrypt(encrypted_data, salt)
        with open(output_path, 'wb') as f:
            f.write(decrypted)
        return output_path


class HS256Signer:
    """HS256 signing for document verification"""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or settings.SECRET_KEY).encode()
    
    def sign(self, data: bytes) -> str:
        """Create HS256 signature for data"""
        signature = hmac.new(self.secret_key, data, hashlib.sha256)
        return base64.urlsafe_b64encode(signature.digest()).decode()
    
    def verify(self, data: bytes, signature: str) -> bool:
        """Verify HS256 signature"""
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)
    
    def sign_document_metadata(self, doc_id: str, doc_type: str, issued_by: str) -> str:
        """Sign document metadata for tamper detection"""
        metadata = f"{doc_id}:{doc_type}:{issued_by}".encode()
        return self.sign(metadata)


def encrypt_gov_id(gov_id: str) -> bytes:
    """Encrypt government ID for storage"""
    encryptor = DocumentEncryption()
    encrypted, salt = encryptor.encrypt(gov_id.encode())
    # Combine salt and encrypted data
    return salt + encrypted


def decrypt_gov_id(encrypted_data: bytes) -> str:
    """Decrypt government ID"""
    encryptor = DocumentEncryption()
    salt = encrypted_data[:16]
    encrypted = encrypted_data[16:]
    return encryptor.decrypt(encrypted, salt).decode()


# Singleton instances
document_encryption = DocumentEncryption()
hs256_signer = HS256Signer()
