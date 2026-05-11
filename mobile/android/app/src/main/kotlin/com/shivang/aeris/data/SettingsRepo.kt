package com.shivang.aeris.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore by preferencesDataStore(name = "aeris_settings")

@Singleton
class SettingsRepo @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val keyModelPath = stringPreferencesKey("brain_model_path")
    private val keyVoice = stringPreferencesKey("voice_lang")

    val modelPath: Flow<String?> = context.settingsDataStore.data
        .map { it[keyModelPath] }

    val voiceLang: Flow<String> = context.settingsDataStore.data
        .map { it[keyVoice] ?: "auto" }

    suspend fun setModelPath(path: String) {
        context.settingsDataStore.edit { it[keyModelPath] = path }
    }

    suspend fun setVoiceLang(lang: String) {
        context.settingsDataStore.edit { it[keyVoice] = lang }
    }
}
