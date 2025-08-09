// MongoDB initialization script for Instagram-Telegram Chat project

// Switch to the project database
db = db.getSiblingDB('instagram_telegram_chat');

// Create a dedicated user for the application
db.createUser({
  user: 'instagram_telegram_user',
  pwd: 'instagram_telegram_pass',
  roles: [
    {
      role: 'readWrite',
      db: 'instagram_telegram_chat'
    }
  ]
});

// Create collections with initial structure
db.createCollection('instagram_users');
db.createCollection('instagram_threads');
db.createCollection('instagram_messages');
db.createCollection('chat_sessions');
db.createCollection('sync_status');
db.createCollection('user_preferences');

// Create indexes for better performance
db.instagram_users.createIndex({ "instagram_id": 1 }, { unique: true });
db.instagram_users.createIndex({ "username": 1 }, { unique: true });

db.instagram_threads.createIndex({ "thread_id": 1 }, { unique: true });
db.instagram_threads.createIndex({ "participants": 1 });

db.instagram_messages.createIndex({ "message_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "thread_id": 1 });
db.instagram_messages.createIndex({ "sender_id": 1 });
db.instagram_messages.createIndex({ "created_at": 1 });

db.chat_sessions.createIndex({ "telegram_user_id": 1, "instagram_user_id": 1 }, { unique: true });

db.sync_status.createIndex({ "created_at": 1 });

db.user_preferences.createIndex({ "user_id": 1 }, { unique: true });

print('Instagram-Telegram Chat database initialized successfully!');
print('Collections created: instagram_users, instagram_threads, instagram_messages, chat_sessions, sync_status, user_preferences');
print('Indexes created for optimal performance');
print('Application user created: instagram_telegram_user'); 