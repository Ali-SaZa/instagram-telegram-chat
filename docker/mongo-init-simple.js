// MongoDB initialization script for simple setup
// This script runs after MongoDB starts up

print('Starting MongoDB initialization...');

// Switch to the application database first
db = db.getSiblingDB('instagram_telegram_chat');

// Create the instaSaZa user with the specified password in the application database
try {
    db.createUser({
        user: "instaSaZa",
        pwd: "instaSaZa1234567",
        roles: [
            { role: "readWrite", db: "instagram_telegram_chat" },
            { role: "dbAdmin", db: "instagram_telegram_chat" }
        ]
    });
    print('✓ User instaSaZa created successfully in instagram_telegram_chat database');
} catch (error) {
    print('User instaSaZa already exists or error occurred:', error.message);
}

// Create collections
const collections = [
    'instagram_users',
    'instagram_threads', 
    'instagram_messages',
    'telegram_users',
    'telegram_chats',
    'sync_logs'
];

collections.forEach(collectionName => {
    if (!db.getCollectionNames().includes(collectionName)) {
        db.createCollection(collectionName);
        print(`✓ Collection '${collectionName}' created`);
    } else {
        print(`- Collection '${collectionName}' already exists`);
    }
});

// Create indexes for better performance
try {
    // Index for instagram_users
    db.instagram_users.createIndex({ "instagram_id": 1 }, { unique: true });
    db.instagram_users.createIndex({ "username": 1 });
    
    // Index for instagram_threads
    db.instagram_threads.createIndex({ "thread_id": 1 }, { unique: true });
    db.instagram_threads.createIndex({ "instagram_user_id": 1 });
    
    // Index for instagram_messages
    db.instagram_messages.createIndex({ "message_id": 1 }, { unique: true });
    db.instagram_threads.createIndex({ "thread_id": 1 });
    db.instagram_messages.createIndex({ "timestamp": 1 });
    
    // Index for telegram_users
    db.telegram_users.createIndex({ "telegram_id": 1 }, { unique: true });
    
    // Index for telegram_chats
    db.telegram_chats.createIndex({ "chat_id": 1 }, { unique: true });
    
    // Index for sync_logs
    db.sync_logs.createIndex({ "timestamp": 1 });
    db.sync_logs.createIndex({ "status": 1 });
    
    print('✓ Database indexes created successfully');
} catch (error) {
    print('Error creating indexes:', error.message);
}

print('MongoDB initialization completed!'); 