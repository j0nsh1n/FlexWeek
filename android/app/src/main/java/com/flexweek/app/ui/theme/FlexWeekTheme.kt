package com.flexweek.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// Block colours as on the computer: school blue, homework amber, activities green.
private val SchoolLight = Color(0xFF4A6FB5)
private val SchoolDark = Color(0xFF9DB8F0)
private val HomeworkLight = Color(0xFF9A6A12)
private val HomeworkDark = Color(0xFFE3B65A)
private val ActivityLight = Color(0xFF2F7D55)
private val ActivityDark = Color(0xFF7FCF9F)

// Material 3 Blue, the same roles the computer's Material style uses (m3-tokens.json, Blue.light.std / Blue.dark.std).
private val LightColors =
    lightColorScheme(
        primary = Color(0xFF425E91),
        onPrimary = Color(0xFFFFFFFF),
        primaryContainer = Color(0xFFD7E2FF),
        onPrimaryContainer = Color(0xFF294677),
        secondary = Color(0xFF565E71),
        onSecondary = Color(0xFFFFFFFF),
        secondaryContainer = Color(0xFFDAE2F9),
        onSecondaryContainer = Color(0xFF3E4759),
        tertiary = Color(0xFF705574),
        onTertiary = Color(0xFFFFFFFF),
        tertiaryContainer = Color(0xFFFAD8FD),
        onTertiaryContainer = Color(0xFF573E5C),
        error = Color(0xFFBA1A1A),
        onError = Color(0xFFFFFFFF),
        errorContainer = Color(0xFFFFDAD6),
        onErrorContainer = Color(0xFF93000A),
        surface = Color(0xFFF9F9FF),
        onSurface = Color(0xFF1A1C20),
        onSurfaceVariant = Color(0xFF44474E),
        surfaceContainerLowest = Color(0xFFFFFFFF),
        surfaceContainerLow = Color(0xFFF3F3FA),
        surfaceContainer = Color(0xFFEDEDF4),
        surfaceContainerHigh = Color(0xFFE8E7EE),
        surfaceContainerHighest = Color(0xFFE2E2E9),
        outline = Color(0xFF74777F),
        outlineVariant = Color(0xFFC4C6D0),
        inverseSurface = Color(0xFF2E3036),
        inverseOnSurface = Color(0xFFF0F0F7),
        inversePrimary = Color(0xFFABC7FF),
        background = Color(0xFFF9F9FF),
        onBackground = Color(0xFF1A1C20),
        surfaceVariant = Color(0xFFE0E2EC),
        surfaceTint = Color(0xFF425E91),
    )

private val DarkColors =
    darkColorScheme(
        primary = Color(0xFFABC7FF),
        onPrimary = Color(0xFF0C305F),
        primaryContainer = Color(0xFF294677),
        onPrimaryContainer = Color(0xFFD7E2FF),
        secondary = Color(0xFFBEC6DC),
        onSecondary = Color(0xFF283041),
        secondaryContainer = Color(0xFF3E4759),
        onSecondaryContainer = Color(0xFFDAE2F9),
        tertiary = Color(0xFFDDBCE0),
        onTertiary = Color(0xFF3F2844),
        tertiaryContainer = Color(0xFF573E5C),
        onTertiaryContainer = Color(0xFFFAD8FD),
        error = Color(0xFFFFB4AB),
        onError = Color(0xFF690005),
        errorContainer = Color(0xFF93000A),
        onErrorContainer = Color(0xFFFFDAD6),
        surface = Color(0xFF111318),
        onSurface = Color(0xFFE2E2E9),
        onSurfaceVariant = Color(0xFFC4C6D0),
        surfaceContainerLowest = Color(0xFF0C0E13),
        surfaceContainerLow = Color(0xFF1A1C20),
        surfaceContainer = Color(0xFF1E2025),
        surfaceContainerHigh = Color(0xFF282A2F),
        surfaceContainerHighest = Color(0xFF33353A),
        outline = Color(0xFF8E9099),
        outlineVariant = Color(0xFF44474E),
        inverseSurface = Color(0xFFE2E2E9),
        inverseOnSurface = Color(0xFF2E3036),
        inversePrimary = Color(0xFF425E91),
        background = Color(0xFF111318),
        onBackground = Color(0xFFE2E2E9),
        surfaceVariant = Color(0xFF44474E),
        surfaceTint = Color(0xFFABC7FF),
    )

@Composable
fun FlexWeekTheme(
    darkTheme: Boolean? = null,
    largeText: Boolean = false,
    content: @Composable () -> Unit,
) {
    val body = if (largeText) 18.sp else 16.sp
    val title = if (largeText) 24.sp else 22.sp
    val small = if (largeText) 16.sp else 14.sp
    val caption = if (largeText) 13.sp else 12.sp
    val colors = if (darkTheme ?: isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        typography =
            MaterialTheme.typography.copy(
                bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = body, fontWeight = FontWeight.Normal),
                titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = title, fontWeight = FontWeight.SemiBold),
                bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = small),
                labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = caption),
            ),
    ) {
        // Every screen sits on the theme's page colour. A screen with no container of its own (Pair) otherwise
        // showed the window's light default under dark-mode colours.
        Surface(Modifier.fillMaxSize(), color = colors.surface, content = content)
    }
}

@Composable
fun syncOkColor(): Color = if (isSystemInDarkTheme()) ActivityDark else ActivityLight

/** What a block's category is drawn as. The real core says "homework"; the fake core said "hw". */
enum class CategoryKind { School, Sports, Homework }

fun categoryKind(category: String): CategoryKind? = when (category) {
    "school" -> CategoryKind.School
    "sports", "sport", "activity", "activities" -> CategoryKind.Sports
    "homework", "hw" -> CategoryKind.Homework
    else -> null
}

@Composable
fun categoryColor(category: String): Color {
    val dark = isSystemInDarkTheme()
    return when (categoryKind(category)) {
        CategoryKind.School -> if (dark) SchoolDark else SchoolLight
        CategoryKind.Sports -> if (dark) ActivityDark else ActivityLight
        CategoryKind.Homework -> if (dark) HomeworkDark else HomeworkLight
        null -> MaterialTheme.colorScheme.outline
    }
}
