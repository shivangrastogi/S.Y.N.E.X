package com.shivang.aeris.ui.workbook

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.shivang.aeris.data.db.entity.ExpenseEntity
import com.shivang.aeris.data.db.entity.ReminderEntity
import com.shivang.aeris.data.db.entity.TaskEntity
import java.text.DateFormat
import java.util.Date

@Composable
fun WorkbookScreen(vm: WorkbookViewModel = hiltViewModel()) {
    val state by vm.ui.collectAsStateWithLifecycle()
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { Text("Workbook", style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary) }
        item { KpiRow(state) }
        item { Section("Recent expenses") }
        items(state.recentExpenses) { ExpenseRow(it) }
        if (state.recentExpenses.isEmpty()) item { Empty("Koi expense add nahi hua abhi.") }

        item { Section("Open tasks") }
        items(state.tasks) { TaskRow(it) }
        if (state.tasks.isEmpty()) item { Empty("All clear sir.") }

        item { Section("Pending reminders") }
        items(state.reminders) { ReminderRow(it) }
        if (state.reminders.isEmpty()) item { Empty("No pending reminders.") }
    }
}

@Composable
private fun KpiRow(s: WorkbookUiState) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Kpi("This month", "₹${s.monthSpend}", Modifier.weight(1f))
        Kpi("Open tasks", s.openTasks.toString(), Modifier.weight(1f))
        Kpi("Cache", s.cachedSearches.toString(), Modifier.weight(1f))
    }
}

@Composable
private fun Kpi(label: String, value: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Section(title: String) =
    Text(title, style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.onBackground)

@Composable
private fun Empty(text: String) =
    Text(text, style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant)

@Composable
private fun ExpenseRow(e: ExpenseEntity) {
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(12.dp)) {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(e.category, style = MaterialTheme.typography.bodyLarge)
                Text(formatTime(e.createdAt),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("₹${e.amount}", style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
private fun TaskRow(t: TaskEntity) {
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.padding(12.dp)) {
            Text(t.title, style = MaterialTheme.typography.bodyLarge)
            Text("priority: ${t.priority}", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ReminderRow(r: ReminderEntity) {
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.padding(12.dp)) {
            Text(r.text, style = MaterialTheme.typography.bodyLarge)
            Text(formatTime(r.triggerAt), style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun formatTime(millis: Long): String =
    DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(millis))
