#!/usr/bin/env python3
"""
Instagram Direct Message Collector

This program uses the instagrapi library to collect direct messages
from Instagram and store them in a text file.

Requirements:
- instagrapi library
- Valid Instagram credentials
- Internet connection

Usage:
1. Set up your credentials in a .env file
2. Run: python instagram_dm_collector.py
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

class InstagramDMCollector:
    def __init__(self, limit: int = None):
        """
        Initialize the Instagram DM collector.
        
        Args:
            limit: Maximum number of users/threads to collect (default: from env var or 50)
        """
        self.client = Client()
        self.messages_file = "instagram_messages.txt"
        self.messages_json_file = "instagram_messages.json"
        
        # Load environment variables
        load_dotenv()
        
        # Get credentials from environment variables
        self.username = os.getenv('INSTAGRAM_USERNAME')
        self.password = os.getenv('INSTAGRAM_PASSWORD')
        self.two_fa_code = os.getenv('INSTAGRAM_2FA_CODE')
        
        # Get limit from parameter, environment variable, or default to 50
        if limit is not None:
            self.limit = limit
        else:
            env_limit = os.getenv('INSTAGRAM_DM_LIMIT')
            if env_limit:
                try:
                    self.limit = int(env_limit)
                    if self.limit <= 0:
                        print(f"⚠️  Invalid limit value '{env_limit}', using default of 50")
                        self.limit = 50
                except ValueError:
                    print(f"⚠️  Invalid limit value '{env_limit}', using default of 50")
                    self.limit = 50
            else:
                self.limit = 50
        
        if not self.username or not self.password:
            raise ValueError("Please set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in your .env file")
    
    def login(self) -> bool:
        """
        Login to Instagram using the provided credentials.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            print("Attempting to login to Instagram...")
            
            # Login with username and password
            self.client.login(self.username, self.password)
            
            # Handle 2FA if provided
            if self.two_fa_code:
                print("Handling two-factor authentication...")
                self.client.two_factor_login(self.two_fa_code)
            
            print("✅ Successfully logged in to Instagram!")
            return True
            
        except LoginRequired as e:
            print(f"❌ Login failed: {e}")
            return False
        except ClientError as e:
            print(f"❌ Client error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during login: {e}")
            return False
    
    def get_direct_messages(self) -> List[Dict[str, Any]]:
        """
        Collect direct messages from Instagram, limited to the last N users.
        Saves data progressively to files during collection.
        
        Returns:
            List[Dict]: List of message dictionaries
        """
        try:
            print(f"Collecting direct messages from the last {self.limit} users...")
            
            # Get all direct threads (remove the default limit of 20)
            threads = self.client.direct_threads(amount=1000)  # Get up to 1000 threads
            
            # Limit to the last N threads (most recent)
            total_threads = len(threads)
            if total_threads > self.limit:
                threads = threads[:self.limit]
                print(f"Limited collection to the last {self.limit} threads out of {total_threads} total threads")
            
            all_messages = []
            total_messages_collected = 0
            
            for thread_index, thread in enumerate(threads, 1):
                try:
                    # Handle different thread title attributes for different versions
                    thread_title = getattr(thread, 'title', None) or getattr(thread, 'thread_title', None) or 'Unknown'
                    print(f"Processing thread {thread_index}/{len(threads)}: {thread_title}")
                    
                    # Get messages from this thread (remove the default limit of 20)
                    messages = self.client.direct_messages(thread.id, amount=1000)  # Get up to 1000 messages per thread
                    
                    thread_messages = []
                    
                    for message in messages:
                        try:
                            # Handle different message attributes for different versions
                            username = 'Unknown'
                            if hasattr(message, 'user') and message.user:
                                username = getattr(message.user, 'username', 'Unknown')
                            elif hasattr(message, 'username'):
                                username = message.username
                            
                            text = getattr(message, 'text', '') or ''
                            timestamp = getattr(message, 'timestamp', None)
                            if timestamp:
                                timestamp = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
                            else:
                                timestamp = ''
                            
                            message_data = {
                                'thread_id': thread.id,
                                'thread_title': thread_title,
                                'message_id': message.id,
                                'user_id': getattr(message, 'user_id', 'Unknown'),
                                'username': username,
                                'text': text,
                                'timestamp': timestamp,
                                'message_type': getattr(message, 'item_type', 'text'),
                                'is_from_me': str(getattr(message, 'user_id', None)) == str(self.client.user_id)
                            }
                            
                            thread_messages.append(message_data)
                            all_messages.append(message_data)
                            
                        except Exception as e:
                            print(f"⚠️  Skipping message due to error: {e}")
                            continue
                    
                    # Save thread data progressively
                    if thread_messages:
                        # Sort messages by timestamp
                        thread_messages.sort(key=lambda x: x['timestamp'])
                        
                        # Append to text file
                        self.append_messages_to_text(thread_messages, thread_title, thread.id)
                        
                        # Append to JSON file
                        user_id = thread_messages[0].get('user_id', 'Unknown')
                        self.append_thread_to_json(thread_messages, thread_title, thread.id, user_id)
                        
                        total_messages_collected += len(thread_messages)
                        print(f"✅ Saved {len(thread_messages)} messages from thread: {thread_title}")
                            
                except Exception as e:
                    print(f"⚠️  Error processing thread {thread.id}: {e}")
                    continue
            
            print(f"✅ Collected {len(all_messages)} messages from {len(threads)} threads")
            return all_messages
            
        except Exception as e:
            print(f"❌ Error collecting messages: {e}")
            # Try to get a more detailed error message
            import traceback
            print(f"Full error details: {traceback.format_exc()}")
            return []
    
    def save_messages_to_text(self, messages: List[Dict[str, Any]]) -> None:
        """
        DEPRECATED: Use progressive saving instead.
        Save messages to a human-readable text file.
        
        Args:
            messages: List of message dictionaries
        """
        print("⚠️  This method is deprecated. Use progressive saving instead.")
        try:
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                f.write("Instagram Direct Messages Collection\n")
                f.write("=" * 50 + "\n")
                f.write(f"Collected on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total messages: {len(messages)}\n\n")
                
                # Group messages by thread
                threads = {}
                for message in messages:
                    thread_id = message['thread_id']
                    if thread_id not in threads:
                        threads[thread_id] = []
                    threads[thread_id].append(message)
                
                # Sort messages in each thread by timestamp
                for thread_id, thread_messages in threads.items():
                    thread_messages.sort(key=lambda x: x['timestamp'])
                
                # Write messages grouped by thread
                for thread_id, thread_messages in threads.items():
                    if thread_messages:
                        thread_title = thread_messages[0]['thread_title']
                        f.write(f"\nThread: {thread_title} (ID: {thread_id})\n")
                        f.write("-" * 40 + "\n")
                        
                        for message in thread_messages:
                            timestamp = message['timestamp']
                            username = message['username']
                            text = message['text']
                            is_from_me = message['is_from_me']
                            
                            f.write(f"[{timestamp}] {'You' if is_from_me else username}: {text}\n")
                
            print(f"✅ Messages saved to {self.messages_file}")
            
        except Exception as e:
            print(f"❌ Error saving messages to text file: {e}")
    
    def save_messages_to_json(self, messages: List[Dict[str, Any]]) -> None:
        """
        DEPRECATED: Use progressive saving instead.
        Save messages to a JSON file for programmatic access.
        
        Args:
            messages: List of message dictionaries
        """
        print("⚠️  This method is deprecated. Use progressive saving instead.")
        try:
            # Group messages by thread
            threads = {}
            for message in messages:
                thread_id = message['thread_id']
                if thread_id not in threads:
                    threads[thread_id] = {
                        'messages': [],
                        'thread_title': message['thread_title'],
                        'user_id': message.get('user_id', 'Unknown')
                    }
                threads[thread_id]['messages'].append({
                    'thread_id': message['thread_id'],
                    'text': message['text'],
                    'timestamp': message['timestamp'],
                    'message_type': message['message_type'],
                    'is_from_me': message['is_from_me']
                })
            
            # Convert to the required format
            threads_list = []
            for i, (thread_id, thread_data) in enumerate(threads.items(), 1):
                thread_obj = {
                    'id': i,
                    'thread_title': thread_data['thread_title'],
                    'user_id': thread_data['user_id'],
                    'messages': sorted(thread_data['messages'], key=lambda x: x['timestamp'])
                }
                threads_list.append(thread_obj)
            
            data = {
                'collection_date': datetime.now().isoformat(),
                'total_threads': len(threads_list),
                'total_messages': len(messages),
                'threads': threads_list
            }
            
            with open(self.messages_json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Messages saved to {self.messages_json_file}")
            
        except Exception as e:
            print(f"❌ Error saving messages to JSON file: {e}")
    
    def initialize_text_file(self) -> None:
        """
        Initialize the text file with headers.
        """
        try:
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                f.write("Instagram Direct Messages Collection\n")
                f.write("=" * 50 + "\n")
                f.write(f"Collected on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("Total messages: 0 (updating...)\n\n")
            print(f"📄 Initialized text file: {self.messages_file}")
        except Exception as e:
            print(f"❌ Error initializing text file: {e}")
    
    def initialize_json_file(self) -> None:
        """
        Initialize the JSON file with basic structure.
        """
        try:
            data = {
                'collection_date': datetime.now().isoformat(),
                'total_threads': 0,
                'total_messages': 0,
                'threads': []
            }
            with open(self.messages_json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"📄 Initialized JSON file: {self.messages_json_file}")
        except Exception as e:
            print(f"❌ Error initializing JSON file: {e}")
    
    def append_messages_to_text(self, thread_messages: List[Dict[str, Any]], thread_title: str, thread_id: str) -> None:
        """
        Append messages from a thread to the text file.
        
        Args:
            thread_messages: List of messages from the thread
            thread_title: Title of the thread
            thread_id: ID of the thread
        """
        try:
            with open(self.messages_file, 'a', encoding='utf-8') as f:
                f.write(f"\nThread: {thread_title} (ID: {thread_id})\n")
                f.write("-" * 40 + "\n")
                
                for message in thread_messages:
                    timestamp = message['timestamp']
                    username = message['username']
                    text = message['text']
                    is_from_me = message['is_from_me']
                    
                    f.write(f"[{timestamp}] {'You' if is_from_me else username}: {text}\n")
        except Exception as e:
            print(f"❌ Error appending to text file: {e}")
    
    def append_thread_to_json(self, thread_messages: List[Dict[str, Any]], thread_title: str, thread_id: str, user_id: str) -> None:
        """
        Append a thread to the JSON file.
        
        Args:
            thread_messages: List of messages from the thread
            thread_title: Title of the thread
            thread_id: ID of the thread
            user_id: User ID of the thread
        """
        try:
            # Read existing data or create new structure if file doesn't exist
            try:
                with open(self.messages_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                # If file doesn't exist or is corrupted, create new structure
                data = {
                    'collection_date': datetime.now().isoformat(),
                    'total_threads': 0,
                    'total_messages': 0,
                    'threads': []
                }
            
            # Create thread object
            thread_obj = {
                'id': len(data['threads']) + 1,
                'thread_title': thread_title,
                'user_id': user_id,
                'messages': sorted(thread_messages, key=lambda x: x['timestamp'])
            }
            
            # Add thread to data
            data['threads'].append(thread_obj)
            data['total_threads'] = len(data['threads'])
            data['total_messages'] = sum(len(thread['messages']) for thread in data['threads'])
            
            # Write updated data
            with open(self.messages_json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Error appending to JSON file: {e}")
    
    def update_text_file_count(self, total_messages: int) -> None:
        """
        Update the total message count in the text file.
        
        Args:
            total_messages: Total number of messages collected
        """
        try:
            # Read the file content
            try:
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except FileNotFoundError:
                print(f"⚠️  Text file {self.messages_file} not found, skipping count update")
                return
            
            # Update the count line
            for i, line in enumerate(lines):
                if line.startswith("Total messages:"):
                    lines[i] = f"Total messages: {total_messages}\n"
                    break
            
            # Write back the updated content
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
        except Exception as e:
            print(f"❌ Error updating text file count: {e}")
    
    def run(self) -> None:
        """
        Main method to run the Instagram DM collection process.
        """
        print("🚀 Starting Instagram Direct Message Collector")
        print("=" * 50)
        
        # Login to Instagram
        if not self.login():
            print("❌ Failed to login. Exiting...")
            return
        
        # Initialize files for progressive saving
        self.initialize_text_file()
        self.initialize_json_file()
        
        # Collect messages (using configured limit) - saves progressively during collection
        messages = self.get_direct_messages()
        
        if not messages:
            print("❌ No messages collected. Exiting...")
            return
        
        # Update final count in text file
        self.update_text_file_count(len(messages))
        
        print("\n🎉 Direct message collection completed successfully!")
        print(f"📄 Text file: {self.messages_file}")
        print(f"📄 JSON file: {self.messages_json_file}")


def main():
    """
    Main function to run the Instagram DM collector.
    
    The limit can be configured in several ways:
    1. Environment variable: INSTAGRAM_DM_LIMIT=100
    2. Constructor parameter: InstagramDMCollector(limit=100)
    3. Default: 50 users/threads
    """
    try:
        # You can specify a custom limit here if needed
        # collector = InstagramDMCollector(limit=100)
        collector = InstagramDMCollector()
        collector.run()
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main() 