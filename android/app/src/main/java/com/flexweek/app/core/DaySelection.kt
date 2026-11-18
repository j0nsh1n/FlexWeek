package com.flexweek.app.core

import java.time.LocalDate

/**
 * The day Today shows. A tapped day holds only for the real day it was tapped on: when midnight passes with the
 * app still in memory, Today goes back to following the real date instead of showing yesterday.
 */
internal class DaySelection(private val realToday: () -> LocalDate) {
    private var chosen: LocalDate? = null
    private var chosenOn: LocalDate? = null

    fun select(date: LocalDate) {
        chosen = date
        chosenOn = realToday()
    }

    fun date(): LocalDate {
        val today = realToday()
        if (chosenOn != today) {
            chosen = null
            chosenOn = null
        }
        return chosen ?: today
    }
}
