// MongoDB initialization script for testing environment
// This script sets up the test database with sample data

print('Starting MongoDB test initialization...');

// Switch to test database
db = db.getSiblingDB('instagram_telegram_chat_test');

// Create collections
db.createCollection('instagram_users');
db.createCollection('instagram_threads');
db.createCollection('instagram_messages');
db.createCollection('chat_sessions');
db.createCollection('sync_status');

// Create indexes for performance
db.instagram_users.createIndex({ "user_id": 1 }, { unique: true });
db.instagram_users.createIndex({ "username": 1 });
db.instagram_threads.createIndex({ "thread_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "message_id": 1 }, { unique: true });
db.instagram_messages.createIndex({ "thread_id": 1 });
db.instagram_messages.createIndex({ "user_id": 1 });
db.instagram_messages.createIndex({ "timestamp": -1 });
db.chat_sessions.createIndex({ "user_id": 1 }, { unique: true });
db.sync_status.createIndex({ "sync_id": 1 }, { unique: true });

// Insert sample test data
print('Inserting sample test data...');

// Sample Instagram users
db.instagram_users.insertMany([
    {
        user_id: "test_user_1",
        username: "test_user_1",
        full_name: "Test User One",
        profile_picture_url: "https://example.com/pic1.jpg",
        is_private: false,
        is_verified: false,
        follower_count: 100,
        following_count: 50,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        user_id: "test_user_2", 
        username: "test_user_2",
        full_name: "Test User Two",
        profile_picture_url: "https://example.com/pic2.jpg",
        is_private: false,
        is_verified: false,
        follower_count: 200,
        following_count: 100,
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// Sample Instagram threads
db.instagram_threads.insertMany([
    {
        thread_id: "test_thread_1",
        title: "Test Thread One",
        users: ["test_user_1", "test_user_2"],
        thread_type: "direct",
        is_group: false,
        last_activity: new Date(),
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        thread_id: "test_thread_2",
        title: "Test Thread Two", 
        users: ["test_user_1"],
        thread_type: "direct",
        is_group: false,
        last_activity: new Date(),
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// Sample Instagram messages
db.instagram_messages.insertMany([
    {
        message_id: "test_msg_1",
        thread_id: "test_thread_1",
        user_id: "test_user_1",
        text: "Hello! This is a test message.",
        item_type: "text",
        timestamp: new Date(),
        created_at: new Date()
    },
    {
        message_id: "test_msg_2",
        thread_id: "test_thread_1", 
        user_id: "test_user_2",
        text: "Hi there! Nice to meet you.",
        item_type: "text",
        timestamp: new Date(),
        created_at: new Date()
    },
    {
        message_id: "test_msg_3",
        thread_id: "test_thread_2",
        user_id: "test_user_1",
        text: "Another test message in thread 2.",
        item_type: "text",
        timestamp: new Date(),
        created_at: new Date()
    }
]);

// Sample chat sessions
db.chat_sessions.insertMany([
    {
        user_id: 12345,
        telegram_user_id: 12345,
        telegram_username: "test_telegram_user",
        current_thread_id: "test_thread_1",
        preferences: {
            language: "en",
            timezone: "UTC",
            notifications: true
        },
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// Sample sync status
db.sync_status.insertMany([
    {
        sync_id: "test_sync_1",
        sync_type: "full",
        status: "completed",
        start_time: new Date(),
        end_time: new Date(),
        items_processed: 3,
        items_created: 3,
        items_updated: 0,
        errors: [],
        created_at: new Date()
    }
]);

print('Sample test data inserted successfully!');

// Verify data
print('Verifying data...');
print('Users count:', db.instagram_users.countDocuments());
print('Threads count:', db.instagram_threads.countDocuments());
print('Messages count:', db.instagram_messages.countDocuments());
print('Chat sessions count:', db.chat_sessions.countDocuments());
print('Sync status count:', db.sync_status.countDocuments());

print('MongoDB test initialization completed successfully!'); 