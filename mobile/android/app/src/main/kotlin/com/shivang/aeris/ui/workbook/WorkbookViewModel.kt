package com.shivang.aeris.ui.workbook

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shivang.aeris.data.db.entity.ExpenseEntity
import com.shivang.aeris.data.db.entity.ReminderEntity
import com.shivang.aeris.data.db.entity.TaskEntity
import com.shivang.aeris.data.repo.SearchCacheRepo
import com.shivang.aeris.data.repo.WorkbookRepo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

data class WorkbookUiState(
    val monthSpend: Int = 0,
    val openTasks: Int = 0,
    val cachedSearches: Int = 0,
    val recentExpenses: List<ExpenseEntity> = emptyList(),
    val tasks: List<TaskEntity> = emptyList(),
    val reminders: List<ReminderEntity> = emptyList(),
)

@HiltViewModel
class WorkbookViewModel @Inject constructor(
    repo: WorkbookRepo,
    cache: SearchCacheRepo,
) : ViewModel() {
    val ui: StateFlow<WorkbookUiState> = combine(
        repo.observeMonthSpend(),
        repo.observeOpenTaskCount(),
        cache.observeCount(),
        repo.observeExpenses(),
        repo.observeOpenTasks(),
        repo.observePendingReminders(),
    ) { arr ->
        WorkbookUiState(
            monthSpend = arr[0] as Int,
            openTasks = arr[1] as Int,
            cachedSearches = arr[2] as Int,
            @Suppress("UNCHECKED_CAST")
            recentExpenses = (arr[3] as List<ExpenseEntity>).take(15),
            @Suppress("UNCHECKED_CAST")
            tasks = arr[4] as List<TaskEntity>,
            @Suppress("UNCHECKED_CAST")
            reminders = arr[5] as List<ReminderEntity>,
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, WorkbookUiState())
}
