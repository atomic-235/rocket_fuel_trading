"""
Cryptographic utilities for secure storage of sensitive configuration data.
"""

import os
import base64
import getpass
from typing import Optional, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger


class SecretManager:
    """Manages encryption and decryption of sensitive configuration data."""
    
    def __init__(self, master_password: Optional[str] = None, use_aes256: bool = True):
        """Initialize SecretManager with master password and encryption method."""
        self.master_password = master_password
        self.use_aes256 = use_aes256  # Use AES-256 for longer, stronger encryption
        self._fernet: Optional[Fernet] = None
    
    def _get_master_password(self) -> str:
        """Get master password from environment or prompt user."""
        if self.master_password:
            return self.master_password
        
        # Try environment variable first
        password = os.getenv("TRADING_MASTER_PASSWORD")
        if password:
            return password
        
        # Prompt user if not found
        return getpass.getpass("Enter master password for secret decryption: ")
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt with stronger settings."""
        password_bytes = password.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=500000,  # Increased from 100,000 to 500,000 for stronger security
        )
        return base64.urlsafe_b64encode(kdf.derive(password_bytes))
    
    def _get_fernet(self, salt: Optional[bytes] = None) -> Fernet:
        """Get or create Fernet cipher instance."""
        if self._fernet is None:
            password = self._get_master_password()
            
            if salt is None:
                # Generate new salt for encryption
                salt = os.urandom(16)
            
            key = self._derive_key(password, salt)
            self._fernet = Fernet(key)
        
        return self._fernet
    
    def encrypt_secret(self, secret: str, salt: Optional[bytes] = None) -> str:
        """
        Encrypt a secret string using AES-256 or Fernet.
        
        Returns: base64 encoded string in format: salt:encrypted_data
        """
        if salt is None:
            salt = os.urandom(16)
        
        if self.use_aes256:
            return self._encrypt_aes256(secret, salt)
        else:
            return self._encrypt_fernet(secret, salt)
    
    def _encrypt_aes256(self, secret: str, salt: bytes) -> str:
        """Encrypt using AES-256-CBC for longer, stronger encryption."""
        # Derive 32-byte key for AES-256
        password = self._get_master_password()
        password_bytes = password.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=500000,
        )
        key = kdf.derive(password_bytes)
        
        # Generate random IV
        iv = os.urandom(16)
        
        # Pad the secret to block size
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(secret.encode('utf-8'))
        padded_data += padder.finalize()
        
        # Encrypt with AES-256-CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine salt + iv + encrypted_data
        combined = salt + iv + encrypted_data
        return base64.b64encode(combined).decode('utf-8')
    
    def _encrypt_fernet(self, secret: str, salt: bytes) -> str:
        """Encrypt using Fernet (AES-128) - shorter output."""
        password = self._get_master_password()
        key = self._derive_key(password, salt)
        fernet = Fernet(key)
        
        encrypted_data = fernet.encrypt(secret.encode('utf-8'))
        
        # Combine salt and encrypted data
        combined = base64.b64encode(salt).decode('utf-8') + ':' + base64.b64encode(encrypted_data).decode('utf-8')
        return combined
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt an encrypted secret string (auto-detects format).
        
        Args:
            encrypted_secret: base64 encoded string (AES-256 or Fernet format)
        """
        try:
            # Check if it's Fernet format (has ':' separator)
            if ':' in encrypted_secret:
                return self._decrypt_fernet(encrypted_secret)
            else:
                return self._decrypt_aes256(encrypted_secret)
                
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            raise ValueError("Failed to decrypt secret - check master password")
    
    def _decrypt_aes256(self, encrypted_secret: str) -> str:
        """Decrypt AES-256-CBC encrypted data."""
        try:
            # Decode the combined data
            combined = base64.b64decode(encrypted_secret.encode('utf-8'))
            
            # Extract components
            salt = combined[:16]      # First 16 bytes
            iv = combined[16:32]      # Next 16 bytes  
            encrypted_data = combined[32:]  # Rest is encrypted data
            
            # Derive the same key
            password = self._get_master_password()
            password_bytes = password.encode('utf-8')
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=500000,
            )
            key = kdf.derive(password_bytes)
            
            # Decrypt
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Remove padding
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data)
            data += unpadder.finalize()
            
            return data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to decrypt AES-256 data: {e}")
            raise
    
    def _decrypt_fernet(self, encrypted_secret: str) -> str:
        """Decrypt Fernet encrypted data (legacy format)."""
        try:
            # Split salt and encrypted data
            salt_b64, data_b64 = encrypted_secret.split(':', 1)
            salt = base64.b64decode(salt_b64.encode('utf-8'))
            encrypted_data = base64.b64decode(data_b64.encode('utf-8'))
            
            # Create Fernet instance with the salt
            password = self._get_master_password()
            key = self._derive_key(password, salt)
            fernet = Fernet(key)
            
            # Decrypt the data
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to decrypt Fernet data: {e}")
            raise
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value is encrypted (detects both AES-256 and Fernet formats)."""
        if not value:
            return False
        
        try:
            # Check for Fernet format (has ':' separator)
            if ':' in value:
                parts = value.split(':', 1)
                if len(parts) != 2:
                    return False
                # Try to decode both parts as base64
                base64.b64decode(parts[0])
                base64.b64decode(parts[1])
                return True
            else:
                # Check for AES-256 format (single base64 string, minimum length)
                decoded = base64.b64decode(value)
                # AES-256 format: 16 bytes salt + 16 bytes IV + at least 16 bytes data = 48+ bytes
                return len(decoded) >= 48
        except:
            return False
    
    def encrypt_config_dict(self, config_dict: Dict[str, str], sensitive_keys: list) -> Dict[str, str]:
        """Encrypt sensitive keys in a configuration dictionary."""
        encrypted_config = config_dict.copy()
        
        for key in sensitive_keys:
            if key in encrypted_config and encrypted_config[key]:
                if not self.is_encrypted(encrypted_config[key]):
                    logger.info(f"🔐 Encrypting {key}")
                    encrypted_config[key] = self.encrypt_secret(encrypted_config[key])
                else:
                    logger.debug(f"🔓 {key} already encrypted")
        
        return encrypted_config
    
    def decrypt_config_dict(self, config_dict: Dict[str, str], sensitive_keys: list) -> Dict[str, str]:
        """Decrypt sensitive keys in a configuration dictionary."""
        decrypted_config = config_dict.copy()
        
        for key in sensitive_keys:
            if key in decrypted_config and decrypted_config[key]:
                if self.is_encrypted(decrypted_config[key]):
                    logger.debug(f"🔓 Decrypting {key}")
                    decrypted_config[key] = self.decrypt_secret(decrypted_config[key])
        
        return decrypted_config


# Global instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager(master_password: Optional[str] = None, use_aes256: bool = True) -> SecretManager:
    """Get the global SecretManager instance with AES-256 encryption."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager(master_password, use_aes256)
    return _secret_manager


def encrypt_value(value: str, master_password: Optional[str] = None, use_aes256: bool = True) -> str:
    """Convenience function to encrypt a single value with AES-256."""
    manager = get_secret_manager(master_password, use_aes256)
    return manager.encrypt_secret(value)


def decrypt_value(encrypted_value: str, master_password: Optional[str] = None) -> str:
    """Convenience function to decrypt a single value."""
    manager = get_secret_manager()
    return manager.decrypt_secret(encrypted_value)


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    manager = get_secret_manager()
    return manager.is_encrypted(value) 