package com.shivang.aeris.data.repo

import com.shivang.aeris.data.db.dao.ExpenseDao
import com.shivang.aeris.data.db.dao.MessageDao
import com.shivang.aeris.data.db.dao.ReminderDao
import com.shivang.aeris.data.db.dao.SearchCacheDao
import com.shivang.aeris.data.db.dao.TaskDao
import com.shivang.aeris.data.db.entity.ExpenseEntity
import com.shivang.aeris.data.db.entity.MessageEntity
import com.shivang.aeris.data.db.entity.ReminderEntity
import com.shivang.aeris.data.db.entity.SearchCacheEntity
import com.shivang.aeris.data.db.entity.TaskEntity
import kotlinx.coroutines.flow.Flow
import java.util.Calendar
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class WorkbookRepo @Inject constructor(
    private val expenseDao: ExpenseDao,
    private val taskDao: TaskDao,
    private val reminderDao: ReminderDao,
) {
    suspend fun addExpense(amount: Int, category: String, note: String? = null): Long =
        expenseDao.insert(ExpenseEntity(amount = amount, category = category, note = note))

    suspend fun addTask(title: String, priority: String = "normal", dueAt: Long? = null): Long =
        taskDao.insert(TaskEntity(title = title, priority = priority, dueAt = dueAt))

    suspend fun addReminder(text: String, triggerAt: Long): Long =
        reminderDao.insert(ReminderEntity(text = text, triggerAt = triggerAt))

    fun observeExpenses(): Flow<List<ExpenseEntity>> = expenseDao.observeAll()
    fun observeOpenTasks(): Flow<List<TaskEntity>> = taskDao.observeOpen()
    fun observeOpenTaskCount(): Flow<Int> = taskDao.observeOpenCount()
    fun observePendingReminders(): Flow<List<ReminderEntity>> = reminderDao.observePending()

    fun observeMonthSpend(): Flow<Int> = expenseDao.observeTotalSince(startOfMonthMillis())
    suspend fun monthBreakdown() = expenseDao.categoryBreakdown(startOfMonthMillis())

    private fun startOfMonthMillis(): Long {
        val c = Calendar.getInstance()
        c.set(Calendar.DAY_OF_MONTH, 1)
        c.set(Calendar.HOUR_OF_DAY, 0); c.set(Calendar.MINUTE, 0)
        c.set(Calendar.SECOND, 0); c.set(Calendar.MILLISECOND, 0)
        return c.timeInMillis
    }
}

@Singleton
class ChatRepo @Inject constructor(
    private val messageDao: MessageDao,
) {
    suspend fun appendUser(text: String) =
        messageDao.insert(MessageEntity(role = "user", text = text))
    suspend fun appendAeris(text: String) =
        messageDao.insert(MessageEntity(role = "aeris", text = text))
    fun observeRecent(limit: Int = 200): Flow<List<MessageEntity>> = messageDao.observeRecent(limit)
    suspend fun clear() = messageDao.clear()
}

@Singleton
class SearchCacheRepo @Inject constructor(
    private val dao: SearchCacheDao,
) {
    suspend fun get(query: String, ttlDays: Int = 30): SearchCacheEntity? {
        val freshAfter = System.currentTimeMillis() - ttlDays * 24L * 3600L * 1000L
        return dao.get(query.lowercase().trim(), freshAfter)
    }
    suspend fun put(query: String, summary: String, source: String) =
        dao.put(SearchCacheEntity(query.lowercase().trim(), summary, source))
    fun observeCount(): Flow<Int> = dao.observeCount()
    suspend fun clear() = dao.clear()
}
