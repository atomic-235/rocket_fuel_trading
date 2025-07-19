#!/usr/bin/env python3
"""
Script to encrypt sensitive secrets in .env files for secure storage.

Usage:
    python scripts/encrypt_secrets.py [.env file path]

This script will:
1. Read your existing .env file
2. Identify sensitive variables
3. Encrypt their values using a master password
4. Save the encrypted version to .env.encrypted
5. Optionally update the original .env file
"""

import os
import sys
import shutil
import getpass
from typing import Tuple

# Add the trading_consumer module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_consumer.utils.crypto import SecretManager
from trading_consumer.config import SENSITIVE_ENV_VARS


def read_env_file(file_path: str) -> Tuple[dict, list]:
    """Read an .env file and return key-value pairs plus original lines."""
    env_vars = {}
    original_lines = []
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return env_vars, original_lines
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            original_lines.append(line.rstrip())
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key] = value
            else:
                print(f"⚠️ Warning: Invalid line format at line {line_num}: {line}")
    
    return env_vars, original_lines


def write_env_file(file_path: str, env_vars: dict, original_lines: list = None):
    """Write environment variables to a .env file preserving original format."""
    with open(file_path, 'w') as f:
        # If we have original lines, preserve the structure
        if original_lines:
            for line in original_lines:
                line = line.rstrip()
                
                # Skip empty lines and comments - write as-is
                if not line or line.startswith('#'):
                    f.write(line + '\n')
                    continue
                
                # Parse KEY=VALUE format
                if '=' in line:
                    key, _ = line.split('=', 1)
                    key = key.strip()
                    
                    # Use updated value if available, otherwise keep original line
                    if key in env_vars:
                        value = env_vars[key]
                        f.write(f"{key}={value}\n")
                    else:
                        f.write(line + '\n')
                else:
                    f.write(line + '\n')
        else:
            # Fallback: write all variables without organization
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")


def main():
    """Main encryption script."""
    print("🔐 Trading Consumer Secret Encryption Tool")
    print("=" * 50)
    
    # Determine .env file path
    if len(sys.argv) > 1:
        env_file = sys.argv[1]
    else:
        env_file = ".env"
    
    if not os.path.exists(env_file):
        print(f"❌ Environment file not found: {env_file}")
        print("Please create a .env file or specify the correct path.")
        return 1
    
    print(f"📄 Reading environment file: {env_file}")
    
    # Read existing environment variables
    env_vars, original_lines = read_env_file(env_file)
    
    if not env_vars:
        print("❌ No environment variables found in file")
        return 1
    
    print(f"✅ Found {len(env_vars)} environment variables")
    
    # Identify sensitive variables
    sensitive_found = []
    for key in SENSITIVE_ENV_VARS:
        if key in env_vars and env_vars[key]:
            sensitive_found.append(key)
    
    if not sensitive_found:
        print("ℹ️ No sensitive variables found that need encryption")
        return 0
    
    print(f"🔍 Found {len(sensitive_found)} sensitive variables to encrypt:")
    for key in sensitive_found:
        value = env_vars[key]
        masked_value = value[:8] + "..." if len(value) > 8 else "***"
        print(f"   {key}: {masked_value}")
    
    # Get master password
    print("\n🔑 Master password setup:")
    print("This password will be used to encrypt/decrypt your secrets.")
    print("You can set TRADING_MASTER_PASSWORD environment variable to avoid prompts.")
    
    # Check for environment variable first
    master_password = os.getenv("TRADING_MASTER_PASSWORD")
    if master_password:
        print("✅ Using master password from TRADING_MASTER_PASSWORD environment variable")
    else:
        master_password = getpass.getpass("Enter master password: ")
        confirm_password = getpass.getpass("Confirm master password: ")
        
        if master_password != confirm_password:
            print("❌ Passwords don't match!")
            return 1
    
    if len(master_password) < 8:
        print("❌ Password must be at least 8 characters long!")
        return 1
    
    # Initialize secret manager
    secret_manager = SecretManager(master_password)
    
    # Encrypt sensitive variables
    print(f"\n🔐 Encrypting {len(sensitive_found)} sensitive variables...")
    encrypted_vars = env_vars.copy()
    
    for key in sensitive_found:
        try:
            print(f"   Encrypting {key}...")
            encrypted_value = secret_manager.encrypt_secret(env_vars[key])
            encrypted_vars[key] = encrypted_value
        except Exception as e:
            print(f"❌ Failed to encrypt {key}: {e}")
            return 1
    
    # Create backup
    backup_file = f"{env_file}.backup"
    shutil.copy2(env_file, backup_file)
    print(f"💾 Created backup: {backup_file}")
    
    # Write encrypted version
    encrypted_file = f"{env_file}.encrypted"
    write_env_file(encrypted_file, encrypted_vars, original_lines)
    print(f"✅ Created encrypted file: {encrypted_file}")
    
    # Ask if user wants to replace original
    print(f"\n❓ Replace original {env_file} with encrypted version?")
    print("   y/yes - Replace original file")
    print("   n/no  - Keep both files")
    
    choice = input("Choice [y/n]: ").lower().strip()
    
    if choice in ['y', 'yes']:
        write_env_file(env_file, encrypted_vars, original_lines)
        print(f"✅ Replaced {env_file} with encrypted version")
        print(f"💾 Original backed up as {backup_file}")
        # Remove the .encrypted file since we updated the original
        os.remove(encrypted_file)
    else:
        print(f"✅ Encrypted version saved as {encrypted_file}")
        print("💾 Original file unchanged")
    
    print("\n🎉 Encryption complete!")
    print("\n📋 Next steps:")
    print("1. Set TRADING_MASTER_PASSWORD environment variable, or")
    print("2. You'll be prompted for the master password when running the bot")
    print("3. Test the configuration with: python -m trading_consumer --test-config")
    print("\n🔒 Keep your master password safe - you cannot recover encrypted data without it!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 