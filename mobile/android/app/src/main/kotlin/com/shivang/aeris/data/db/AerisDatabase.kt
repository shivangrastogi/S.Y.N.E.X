package com.shivang.aeris.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.shivang.aeris.data.db.dao.ExpenseDao
import com.shivang.aeris.data.db.dao.MeetingDao
import com.shivang.aeris.data.db.dao.MessageDao
import com.shivang.aeris.data.db.dao.ReminderDao
import com.shivang.aeris.data.db.dao.SearchCacheDao
import com.shivang.aeris.data.db.dao.TaskDao
import com.shivang.aeris.data.db.entity.ExpenseEntity
import com.shivang.aeris.data.db.entity.MeetingEntity
import com.shivang.aeris.data.db.entity.MessageEntity
import com.shivang.aeris.data.db.entity.ReminderEntity
import com.shivang.aeris.data.db.entity.SearchCacheEntity
import com.shivang.aeris.data.db.entity.TaskEntity

@Database(
    entities = [
        ExpenseEntity::class,
        TaskEntity::class,
        ReminderEntity::class,
        MeetingEntity::class,
        MessageEntity::class,
        SearchCacheEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AerisDatabase : RoomDatabase() {
    abstract fun expenseDao(): ExpenseDao
    abstract fun taskDao(): TaskDao
    abstract fun reminderDao(): ReminderDao
    abstract fun meetingDao(): MeetingDao
    abstract fun messageDao(): MessageDao
    abstract fun searchCacheDao(): SearchCacheDao
}
