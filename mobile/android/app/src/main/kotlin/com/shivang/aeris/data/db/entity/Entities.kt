package com.shivang.aeris.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "expenses")
data class ExpenseEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val amount: Int,
    val category: String,
    val note: String?,
    val createdAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "tasks")
data class TaskEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String,
    val priority: String = "normal", // low | normal | urgent
    val dueAt: Long? = null,
    val done: Boolean = false,
    val createdAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "reminders")
data class ReminderEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val text: String,
    val triggerAt: Long,
    val fired: Boolean = false,
)

@Entity(tableName = "meetings")
data class MeetingEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String,
    val withWho: String?,
    val startAt: Long,
    val createdAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val role: String, // user | aeris
    val text: String,
    val createdAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "search_cache")
data class SearchCacheEntity(
    @PrimaryKey val query: String,
    val summary: String,
    val source: String,
    val cachedAt: Long = System.currentTimeMillis(),
)
