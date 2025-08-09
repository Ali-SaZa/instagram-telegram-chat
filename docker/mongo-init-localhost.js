// MongoDB initialization script for localhost setup
print('Starting MongoDB initialization...');

// Switch to the target database
db = db.getSiblingDB('instagram_telegram_chat');

// Create collections
db.createCollection('instagram_users');
db.createCollection('instagram_threads');
db.createCollection('instagram_messages');
db.createCollection('chat_sessions');
db.createCollection('sync_status');
db.createCollection('user_preferences');

print('Collections created successfully');

// Create indexes for better performance
db.instagram_users.createIndex({ "instagram_id": 1 }, { unique: true });
db.instagram_users.createIndex({ "username": 1 });
db.instagram_threads.createIndex({ "thread_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "message_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "thread_id": 1 });
db.instagram_messages.createIndex({ "sender_id": 1 });
db.chat_sessions.createIndex({ "session_id": 1 }, { unique: true });
db.sync_status.createIndex({ "user_id": 1 }, { unique: true });

print('Indexes created successfully');
print('MongoDB initialization completed!'); 