package com.shivang.aeris.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val AerisCyan = Color(0xFF00E5FF)
private val AerisCyanDim = Color(0xFF0091EA)
private val AerisBg = Color(0xFF070B12)
private val AerisSurface = Color(0xFF0F1623)
private val AerisText = Color(0xFFE6F4FF)
private val AerisMuted = Color(0xFF7A8CA3)

private val Dark = darkColorScheme(
    primary = AerisCyan,
    onPrimary = AerisBg,
    secondary = AerisCyanDim,
    background = AerisBg,
    onBackground = AerisText,
    surface = AerisSurface,
    onSurface = AerisText,
    surfaceVariant = AerisSurface,
    onSurfaceVariant = AerisMuted,
    outline = AerisCyanDim,
)

private val Light = lightColorScheme(
    primary = AerisCyanDim,
    background = Color(0xFFF5FAFF),
    surface = Color.White,
)

private val AerisTypography = Typography(
    titleLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 22.sp, letterSpacing = 0.5.sp),
    titleMedium = TextStyle(fontWeight = FontWeight.Medium, fontSize = 18.sp),
    bodyLarge = TextStyle(fontWeight = FontWeight.Normal, fontSize = 15.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 13.sp, letterSpacing = 0.8.sp),
)

@Composable
fun AerisTheme(content: @Composable () -> Unit) {
    val scheme = if (isSystemInDarkTheme()) Dark else Dark // force dark — A.E.R.I.S. is a dark-mode app
    MaterialTheme(
        colorScheme = scheme,
        typography = AerisTypography,
        content = content,
    )
}
