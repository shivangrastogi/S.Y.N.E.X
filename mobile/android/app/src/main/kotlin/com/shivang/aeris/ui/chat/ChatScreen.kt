package com.shivang.aeris.ui.chat

import android.Manifest
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberPermissionState
import com.shivang.aeris.core.llm.LlmEngine

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun ChatScreen(
    onSwitchToVision: () -> Unit = {},
    vm: ChatViewModel = hiltViewModel(),
) {
    val state by vm.ui.collectAsStateWithLifecycle()
    val visionTrigger by vm.visionTrigger.collectAsStateWithLifecycle()
    val micPerm = rememberPermissionState(Manifest.permission.RECORD_AUDIO)
    val listState = rememberLazyListState()

    LaunchedEffect(visionTrigger) { if (visionTrigger > 0) onSwitchToVision() }
    LaunchedEffect(state.bubbles.size) {
        if (state.bubbles.isNotEmpty()) listState.animateScrollToItem(state.bubbles.lastIndex)
    }

    Column(Modifier.fillMaxSize()) {
        Header(state.brainStatus)
        if (state.brainStatus is LlmEngine.Status.Loading) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.bubbles) { b -> Bubble(b) }
            if (state.partialTranscript.isNotBlank()) {
                item { Bubble(ChatBubble("user", state.partialTranscript, streaming = true)) }
            }
        }
        Composer(
            isListening = state.isListening,
            hasMic = micPerm.status.isGranted(),
            onMic = {
                if (!micPerm.status.isGranted()) micPerm.launchPermissionRequest()
                else vm.toggleListen()
            },
            onSend = vm::submit,
        )
    }
}

@Composable
private fun Header(brain: LlmEngine.Status) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text("A.E.R.I.S.", style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary)
            val sub = when (brain) {
                LlmEngine.Status.Idle -> "Brain not loaded — open Settings"
                LlmEngine.Status.Loading -> "Loading brain…"
                LlmEngine.Status.Ready -> "Online · on-device brain ready"
                is LlmEngine.Status.Error -> "Brain error: ${brain.message}"
            }
            Text(sub, style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun Bubble(b: ChatBubble) {
    val isUser = b.role == "user"
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            color = if (isUser) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                    else MaterialTheme.colorScheme.surface,
            shape = RoundedCornerShape(
                topStart = 16.dp, topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp,
            ),
            modifier = Modifier.widthIn(max = 320.dp).padding(vertical = 2.dp),
        ) {
            Text(
                b.text,
                style = MaterialTheme.typography.bodyLarge,
                color = if (isUser) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            )
        }
    }
}

@Composable
private fun Composer(
    isListening: Boolean,
    hasMic: Boolean,
    onMic: () -> Unit,
    onSend: (String) -> Unit,
) {
    var draft by remember { mutableStateOf("") }
    Surface(color = MaterialTheme.colorScheme.surface) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilledTonalIconButton(onClick = onMic) {
                Icon(
                    imageVector = if (isListening) Icons.Filled.Stop else Icons.Filled.Mic,
                    contentDescription = if (isListening) "Stop" else "Speak",
                    tint = if (isListening) MaterialTheme.colorScheme.primary else Color.Unspecified,
                )
            }
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                placeholder = { Text("Type or tap mic…") },
                singleLine = true,
                keyboardActions = KeyboardActions(onSend = {
                    if (draft.isNotBlank()) { onSend(draft); draft = "" }
                }),
            )
            IconButton(onClick = { if (draft.isNotBlank()) { onSend(draft); draft = "" } }) {
                Icon(Icons.Filled.Send, contentDescription = "Send",
                    tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@OptIn(ExperimentalPermissionsApi::class)
private fun com.google.accompanist.permissions.PermissionStatus.isGranted(): Boolean =
    this is com.google.accompanist.permissions.PermissionStatus.Granted
