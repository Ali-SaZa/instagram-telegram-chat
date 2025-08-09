// MongoDB initialization script for Instagram-Telegram Chat
// This script runs when the MongoDB container starts

// Create the database and user
db = db.getSiblingDB('instagram_telegram_chat');

// Create collections
db.createCollection('instagram_users');
db.createCollection('instagram_threads');
db.createCollection('instagram_messages');
db.createCollection('chat_sessions');
db.createCollection('sync_status');

// Create indexes for better performance
db.instagram_users.createIndex({ "username": 1 }, { unique: true });
db.instagram_threads.createIndex({ "thread_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "message_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "thread_id": 1 });
db.instagram_messages.createIndex({ "timestamp": 1 });
db.chat_sessions.createIndex({ "telegram_user_id": 1 }, { unique: true });

// Create user in the instagram_telegram_chat database
db.createUser({
  user: "instaSaZa",
  pwd: "instaSaZa1234567",
  roles: [
    { role: "readWrite", db: "instagram_telegram_chat" },
    { role: "dbAdmin", db: "instagram_telegram_chat" }
  ]
});

print('MongoDB initialized successfully for Instagram-Telegram Chat');
print('User instaSaZa created in instagram_telegram_chat database'); 