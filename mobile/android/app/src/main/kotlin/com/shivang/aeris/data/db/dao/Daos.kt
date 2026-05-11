package com.shivang.aeris.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shivang.aeris.data.db.entity.ExpenseEntity
import com.shivang.aeris.data.db.entity.MeetingEntity
import com.shivang.aeris.data.db.entity.MessageEntity
import com.shivang.aeris.data.db.entity.ReminderEntity
import com.shivang.aeris.data.db.entity.SearchCacheEntity
import com.shivang.aeris.data.db.entity.TaskEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ExpenseDao {
    @Insert suspend fun insert(e: ExpenseEntity): Long

    @Query("SELECT * FROM expenses ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<ExpenseEntity>>

    @Query("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE createdAt >= :sinceMillis")
    fun observeTotalSince(sinceMillis: Long): Flow<Int>

    @Query("""SELECT category as cat, SUM(amount) as total FROM expenses
              WHERE createdAt >= :sinceMillis GROUP BY category ORDER BY total DESC""")
    suspend fun categoryBreakdown(sinceMillis: Long): List<CategoryTotal>

    data class CategoryTotal(val cat: String, val total: Int)
}

@Dao
interface TaskDao {
    @Insert suspend fun insert(t: TaskEntity): Long
    @Update suspend fun update(t: TaskEntity)

    @Query("SELECT * FROM tasks WHERE done = 0 ORDER BY priority DESC, createdAt DESC")
    fun observeOpen(): Flow<List<TaskEntity>>

    @Query("SELECT COUNT(*) FROM tasks WHERE done = 0")
    fun observeOpenCount(): Flow<Int>
}

@Dao
interface ReminderDao {
    @Insert suspend fun insert(r: ReminderEntity): Long
    @Query("UPDATE reminders SET fired = 1 WHERE id = :id") suspend fun markFired(id: Long)

    @Query("SELECT * FROM reminders WHERE fired = 0 ORDER BY triggerAt ASC")
    fun observePending(): Flow<List<ReminderEntity>>
}

@Dao
interface MeetingDao {
    @Insert suspend fun insert(m: MeetingEntity): Long
    @Query("SELECT * FROM meetings WHERE startAt >= :sinceMillis ORDER BY startAt ASC")
    fun observeUpcoming(sinceMillis: Long): Flow<List<MeetingEntity>>
}

@Dao
interface MessageDao {
    @Insert suspend fun insert(m: MessageEntity): Long
    @Query("SELECT * FROM messages ORDER BY createdAt ASC LIMIT :limit")
    fun observeRecent(limit: Int): Flow<List<MessageEntity>>
    @Query("DELETE FROM messages") suspend fun clear()
}

@Dao
interface SearchCacheDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun put(c: SearchCacheEntity)

    @Query("SELECT * FROM search_cache WHERE query = :q AND cachedAt >= :freshAfter LIMIT 1")
    suspend fun get(q: String, freshAfter: Long): SearchCacheEntity?

    @Query("SELECT COUNT(*) FROM search_cache") fun observeCount(): Flow<Int>
    @Query("DELETE FROM search_cache") suspend fun clear()
}
