package com.flexweek.app.ui.v2

import kotlin.math.roundToInt

object LateSlider {
    private const val DEFAULT_STEP = 5
    private const val DEFAULT_MAX = 60

    fun minutesAt(
        fraction: Float,
        step: Int = DEFAULT_STEP,
        max: Int = DEFAULT_MAX,
    ): Int {
        val clamped = fraction.coerceIn(0f, 1f)
        val stops = max / step
        if (stops < 2) return max
        val index = (clamped * (stops - 1)).roundToInt().coerceIn(0, stops - 1)
        return step * (index + 1)
    }
}
