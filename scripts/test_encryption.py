#!/usr/bin/env python3
"""
Quick test script to verify encryption functionality.
"""

import os
import sys

# Add the trading_consumer module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_consumer.utils.crypto import SecretManager


def test_encryption():
    """Test basic encryption/decryption functionality."""
    print("🧪 Testing Secret Encryption/Decryption")
    print("=" * 40)
    
    # Test password
    password = "test_password_123"
    
    # Test data
    test_secrets = [
        "telegram_bot_token_12345",
        "0x1234567890abcdef1234567890abcdef12345678",
        "private_key_data_here"
    ]
    
    # Initialize secret manager
    secret_manager = SecretManager(password)
    
    print("✅ Secret manager initialized")
    
    # Test encryption/decryption
    for i, secret in enumerate(test_secrets, 1):
        print(f"\n📝 Test {i}: {secret[:20]}...")
        
        # Encrypt
        encrypted = secret_manager.encrypt_secret(secret)
        print(f"🔐 Encrypted: {encrypted[:50]}...")
        
        # Verify it's detected as encrypted
        is_encrypted = secret_manager.is_encrypted(encrypted)
        print(f"🔍 Is encrypted: {is_encrypted}")
        
        # Decrypt
        decrypted = secret_manager.decrypt_secret(encrypted)
        print(f"🔓 Decrypted: {decrypted[:20]}...")
        
        # Verify match
        if secret == decrypted:
            print("✅ Encryption/decryption successful!")
        else:
            print("❌ Encryption/decryption failed!")
            return False
    
    print("\n🎉 All encryption tests passed!")
    return True


def test_wrong_password():
    """Test that wrong password fails gracefully."""
    print("\n🧪 Testing Wrong Password Handling")
    print("=" * 40)
    
    # Encrypt with one password
    manager1 = SecretManager("correct_password")
    secret = "test_secret_data"
    encrypted = manager1.encrypt_secret(secret)
    print("🔐 Encrypted with correct password")
    
    # Try to decrypt with wrong password
    manager2 = SecretManager("wrong_password")
    try:
        manager2.decrypt_secret(encrypted)
        print("❌ Wrong password should have failed!")
        return False
    except ValueError as e:
        print(f"✅ Wrong password correctly rejected: {e}")
        return True


if __name__ == "__main__":
    print("🔐 Trading Consumer Encryption Test Suite")
    print("=" * 50)
    
    success = True
    
    try:
        success &= test_encryption()
        success &= test_wrong_password()
        
        if success:
            print("\n🎉 All tests passed! Encryption system is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        sys.exit(1) 