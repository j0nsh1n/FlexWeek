package com.flexweek.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val AccentLight = Color(0xFF3D6FC4)
private val AccentDark = Color(0xFF7FA8FF)
private val ErrorLight = Color(0xFFB42318)
private val ErrorDark = Color(0xFFFF8A7A)
private val OkLight = Color(0xFF2F7D4A)
private val OkDark = Color(0xFF7ED39A)

private val LightColors =
    lightColorScheme(
        primary = AccentLight,
        onPrimary = Color.White,
        background = Color(0xFFEEF1F5),
        surface = Color.White,
        onSurface = Color(0xFF0F172A),
        onSurfaceVariant = Color(0xFF475569),
        error = ErrorLight,
        outline = Color(0xFFC3CCD9),
    )

private val DarkColors =
    darkColorScheme(
        primary = AccentDark,
        onPrimary = Color(0xFF0B1220),
        background = Color(0xFF111315),
        surface = Color(0xFF1A1D21),
        onSurface = Color(0xFFE8EAED),
        onSurfaceVariant = Color(0xFF9AA1AB),
        error = ErrorDark,
        outline = Color(0xFF3A3F46),
    )

@Composable
fun FlexWeekTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    largeText: Boolean = false,
    content: @Composable () -> Unit,
) {
    val body = if (largeText) 18.sp else 16.sp
    val title = if (largeText) 24.sp else 22.sp
    val small = if (largeText) 16.sp else 14.sp
    val caption = if (largeText) 13.sp else 12.sp
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography =
            MaterialTheme.typography.copy(
                bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = body, fontWeight = FontWeight.Normal),
                titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = title, fontWeight = FontWeight.SemiBold),
                bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = small),
                labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = caption),
            ),
        content = content,
    )
}

@Composable
fun syncOkColor(): Color = if (isSystemInDarkTheme()) OkDark else OkLight

@Composable
fun categoryColor(category: String): Color {
    val dark = isSystemInDarkTheme()
    return when (category) {
        "school" -> if (dark) AccentDark else AccentLight
        "sports" -> if (dark) OkDark else OkLight
        "hw" -> if (dark) ErrorDark else ErrorLight
        else -> MaterialTheme.colorScheme.outline
    }
}
