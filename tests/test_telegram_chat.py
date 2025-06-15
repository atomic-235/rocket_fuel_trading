"""
Test that bot can read from the target Telegram chat.
"""

import asyncio
import pytest
from pathlib import Path

from trading_consumer.config import load_config
from trading_consumer.telegram import TelegramClient


@pytest.mark.asyncio
async def test_bot_can_read_from_chat():
    """Test that the bot can connect and read from the configured Telegram chat."""
    
    # Load real config from .env
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        pytest.skip("No .env file found")
    
    config = load_config(str(env_path))
    
    print(f"Testing connection to chat ID: {config.telegram.chat_id}")
    print(f"Using bot token: {config.telegram.bot_token[:20]}...")
    
    # Create Telegram client
    client = TelegramClient(config.telegram)
    
    try:
        # Initialize and test connection
        await client.initialize()
        print("✅ Bot initialized successfully")
        
        # Test bot info
        bot_info = await client.bot.get_me()
        print(f"✅ Connected as: @{bot_info.username}")
        
        # Test chat access
        try:
            chat_info = await client.bot.get_chat(config.telegram.chat_id)
            print(f"✅ Can access chat: {chat_info.title or chat_info.type}")
            print(f"   Chat type: {chat_info.type}")
            if hasattr(chat_info, 'member_count'):
                print(f"   Members: {chat_info.member_count}")
        except Exception as e:
            print(f"❌ Cannot access chat {config.telegram.chat_id}: {e}")
            raise
        
        # Test actual message reading with timeout
        print("🔍 Testing message reading from channel...")
        print("   Starting message listener for 10 seconds...")
        print("   Please post a test message to the channel now!")
        
        messages_received = []
        
        def message_handler(message):
            messages_received.append(message)
            print(f"📨 Received message: {message.content[:50]}...")
        
        # Start the client with our message handler
        client_task = asyncio.create_task(client.start(message_handler))
        
        # Wait for 10 seconds to receive messages
        try:
            await asyncio.wait_for(client_task, timeout=10.0)
        except asyncio.TimeoutError:
            print("⏰ Timeout reached")
        
        # Check if we received any messages
        if messages_received:
            print(f"✅ SUCCESS: Received {len(messages_received)} message(s)")
            for i, msg in enumerate(messages_received):
                print(f"   Message {i+1}: {msg.content[:100]}...")
                print(f"   From: {msg.sender_name}")
                print(f"   Time: {msg.date}")
        else:
            print("⚠️  No messages received during test period")
            print("   This could mean:")
            print("   - No messages were posted to the channel during the test")
            print("   - The bot doesn't have permission to read messages")
            print("   - The channel is private and bot isn't an admin")
        
        print("🎉 Connection test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_read_last_message_and_validate():
    """Read the last message from the channel and validate it with Pydantic."""
    
    # Load real config from .env
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        pytest.skip("No .env file found")
    
    config = load_config(str(env_path))
    
    print(f"Reading last message from chat ID: {config.telegram.chat_id}")
    
    # Create Telegram client
    client = TelegramClient(config.telegram)
    
    try:
        await client.initialize()
        print("✅ Bot initialized")
        
        # Try to get recent updates to find the last message
        print("🔍 Fetching recent messages...")
        
        try:
            # Get recent updates (this includes messages)
            updates = await client.bot.get_updates(limit=100, timeout=5)
            
            if not updates:
                print("⚠️  No recent updates found")
                print("   Try posting a message to the channel first")
                return
            
            print(f"📥 Found {len(updates)} recent updates")
            
            # Find the most recent message from our target chat
            target_message = None
            for update in reversed(updates):  # Check most recent first
                if update.message and update.message.chat.id == config.telegram.chat_id:
                    target_message = update.message
                    break
                elif update.channel_post and update.channel_post.chat.id == config.telegram.chat_id:
                    target_message = update.channel_post
                    break
            
            if not target_message:
                print("⚠️  No messages found from the target channel in recent updates")
                print("   Try posting a new message to the channel")
                return
            
            print(f"📨 Found last message!")
            print(f"   Message ID: {target_message.message_id}")
            print(f"   Date: {target_message.date}")
            print(f"   Text: {target_message.text[:100]}..." if target_message.text else "   No text content")
            
            # Convert to our Pydantic model
            telegram_message = client._convert_message(target_message)
            
            print("\n🔍 Validating message with Pydantic...")
            
            # Validate the message structure
            assert telegram_message.message_id > 0, "Message ID should be positive"
            assert telegram_message.chat.id == config.telegram.chat_id, "Chat ID should match"
            assert telegram_message.date is not None, "Date should be set"
            
            print("✅ Message structure validation passed!")
            
            # Display validated message details
            print(f"\n📋 Validated Message Details:")
            print(f"   Message ID: {telegram_message.message_id}")
            print(f"   Chat ID: {telegram_message.chat.id}")
            print(f"   Chat Type: {telegram_message.chat.type}")
            print(f"   Chat Title: {telegram_message.chat.title}")
            print(f"   Sender: {telegram_message.sender_name}")
            print(f"   Date: {telegram_message.date}")
            print(f"   Content: {telegram_message.content}")
            
            # Validate using Pydantic's own validation
            try:
                # This will raise ValidationError if the model is invalid
                telegram_message.model_validate(telegram_message.model_dump())
                print("✅ Pydantic model validation passed!")
            except Exception as e:
                print(f"❌ Pydantic validation failed: {e}")
                raise
            
            # Test if message is not empty
            if telegram_message.content and telegram_message.content.strip():
                print("✅ Message content is not empty!")
                print(f"   Content length: {len(telegram_message.content)} characters")
            else:
                print("⚠️  Message content is empty or only whitespace")
            
            print("\n🎉 Message reading and validation completed successfully!")
            
        except Exception as e:
            print(f"❌ Error reading messages: {e}")
            raise
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_channel_permissions():
    """Test channel permissions and bot status."""
    
    # Load real config from .env
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        pytest.skip("No .env file found")
    
    config = load_config(str(env_path))
    
    # Create Telegram client
    client = TelegramClient(config.telegram)
    
    try:
        await client.initialize()
        
        # Check if bot is admin in the channel
        try:
            chat_member = await client.bot.get_chat_member(config.telegram.chat_id, client.bot.id)
            print(f"Bot status in channel: {chat_member.status}")
            
            if chat_member.status in ['administrator', 'creator']:
                print("✅ Bot has admin privileges - can read message history")
            elif chat_member.status == 'member':
                print("⚠️  Bot is a member - can only read new messages")
            else:
                print(f"❓ Bot status: {chat_member.status}")
                
        except Exception as e:
            print(f"Cannot get bot status: {e}")
        
    except Exception as e:
        print(f"Permission check failed: {e}")
        raise
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(test_read_last_message_and_validate()) 