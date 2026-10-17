package com.flexweek.app.model

import org.junit.Assert.assertEquals
import org.junit.Test

// The right-hand words of picture 5 B (Mon 19 to Sun 25 Oct).
class WeekRowWordsTest {
    @Test fun aHeavyDaySaysItsTotalAndHeavy() = assertEquals("4 h 30 · heavy", WeekRowWords.right(270, true, 870))

    @Test fun wholeHoursHaveNoMinutes() = assertEquals("2 h", WeekRowWords.right(120, false, 870))

    @Test fun underAnHourIsMinutes() = assertEquals("45 min", WeekRowWords.right(45, false, 870))

    @Test fun noHomeworkAfterSchoolIsFreeAfterItsEnd() = assertEquals("free after 2:30", WeekRowWords.right(0, false, 870))

    @Test fun onTheHourHasNoMinutes() = assertEquals("free after 3", WeekRowWords.right(0, false, 900))

    @Test fun noHomeworkAndNoSchoolIsFree() = assertEquals("free", WeekRowWords.right(0, false, null))
}
