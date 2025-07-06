#!/usr/bin/env python3
"""
Environment management script for trading consumer.
Copies environment files for different environments (dev/prod) and sets environment variables.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


def load_env_file(env_path):
    """Load environment variables from a file."""
    env_vars = {}
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print(f"❌ Error loading environment file: {e}")
        return None
    return env_vars


def set_env_variables(env_vars):
    """Set environment variables in the current process."""
    for key, value in env_vars.items():
        os.environ[key] = value
    print(f"✅ Set {len(env_vars)} environment variables")


def generate_shell_script(env_vars, env_name):
    """Generate a shell script to set environment variables."""
    script_content = f"#!/bin/bash\n# Environment variables for {env_name}\n\n"
    
    for key, value in env_vars.items():
        # Escape special characters in values
        escaped_value = value.replace('"', '\\"').replace('$', '\\$')
        script_content += f'export {key}="{escaped_value}"\n'
    
    script_content += f'\necho "✅ Loaded {env_name} environment variables"\n'
    
    script_path = Path(__file__).parent.parent / f"set_env_{env_name}.sh"
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        print(f"📝 Generated shell script: {script_path}")
        print(f"💡 To use: source {script_path}")
        
    except Exception as e:
        print(f"❌ Error generating shell script: {e}")


def main():
    """Main function to manage environment files."""
    parser = argparse.ArgumentParser(
        description="Manage environment files and variables for trading consumer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/switch_env.py dev            # Copy .env_dev to .env
  python scripts/switch_env.py prod --set     # Copy .env_prod to .env and set variables
  python scripts/switch_env.py dev --shell    # Generate shell script for dev environment
  python scripts/switch_env.py --list         # List available environment files
        """
    )
    
    parser.add_argument(
        "environment",
        nargs="?",
        choices=["dev", "prod"],
        help="Environment to switch to (dev or prod)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available environment files"
    )
    
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup of current .env file"
    )
    
    parser.add_argument(
        "--set",
        action="store_true",
        help="Set environment variables in current process"
    )
    
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Generate shell script to set environment variables"
    )
    
    args = parser.parse_args()
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    # Define environment files
    env_files = {
        "dev": project_root / ".env_dev",
        "prod": project_root / ".env_prod"
    }
    
    target_env = project_root / ".env"
    
    # List available environment files
    if args.list:
        print("📋 Available environment files:")
        for env_name, env_path in env_files.items():
            if env_path.exists():
                print(f"  ✅ {env_name}: {env_path}")
            else:
                print(f"  ❌ {env_name}: {env_path} (not found)")
        
        if target_env.exists():
            print(f"\n🎯 Current .env file: {target_env}")
        else:
            print(f"\n⚠️  No .env file found at: {target_env}")
        
        return
    
    # Validate environment argument
    if not args.environment:
        print("❌ Error: Please specify an environment (dev or prod)")
        parser.print_help()
        sys.exit(1)
    
    env_name = args.environment
    source_env = env_files[env_name]
    
    # Check if source environment file exists
    if not source_env.exists():
        print(f"❌ Error: Environment file not found: {source_env}")
        print(f"💡 Create the file first or use --list to see available files")
        sys.exit(1)
    
    # Load environment variables
    env_vars = load_env_file(source_env)
    if not env_vars:
        print(f"❌ Error: Could not load environment variables from {source_env}")
        sys.exit(1)
    
    # Create backup if requested
    if args.backup and target_env.exists():
        backup_path = target_env.with_suffix(".env.backup")
        shutil.copy2(target_env, backup_path)
        print(f"💾 Created backup: {backup_path}")
    
    # Copy environment file
    try:
        shutil.copy2(source_env, target_env)
        print(f"✅ Successfully switched to {env_name} environment")
        print(f"📁 Copied: {source_env} → {target_env}")
        
    except Exception as e:
        print(f"❌ Error copying environment file: {e}")
        sys.exit(1)
    
    # Set environment variables if requested
    if args.set:
        set_env_variables(env_vars)
    
    # Generate shell script if requested
    if args.shell:
        generate_shell_script(env_vars, env_name)
    
    # Show some key settings from the new environment
    print(f"\n🔍 Environment preview:")
    try:
        for key, value in env_vars.items():
            if any(env_key in key for env_key in ['TELEGRAM_', 'HYPERLIQUID_TESTNET', 'DEFAULT_']):
                # Hide sensitive values
                if 'TOKEN' in key or 'KEY' in key or 'ADDRESS' in key:
                    if value:
                        hidden_value = value[:10] + "..." if len(value) > 10 else "***"
                        print(f"  {key}={hidden_value}")
                else:
                    print(f"  {key}={value}")
    except Exception as e:
        print(f"⚠️  Could not preview environment: {e}")
    
    # Show usage hints
    if not args.set and not args.shell:
        print(f"\n💡 Next steps:")
        print(f"  • Set variables in current process: python scripts/switch_env.py {env_name} --set")
        print(f"  • Generate shell script: python scripts/switch_env.py {env_name} --shell")
        print(f"  • Restart your application to use the new .env file")


if __name__ == "__main__":
    main() 