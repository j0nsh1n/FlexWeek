package com.flexweek.app.update

import org.junit.Assert.assertEquals
import org.junit.Test

class UpdateWordsTest {
    private val mb = 1024L * 1024

    @Test fun downloadingSaysMegabytesOfTheTotal() {
        assertEquals("Downloading 12 of 65 MB", UpdateWords.downloading(12 * mb + 5, 65 * mb + 300))
    }

    @Test fun downloadingWithoutATotalSaysOnlyWhatArrived() {
        assertEquals("Downloading, 12 MB so far", UpdateWords.downloading(12 * mb, -1))
    }

    @Test fun upToDateNamesTheInstalledVersionLikeTheComputer() {
        assertEquals("FlexWeek 1.1.0 is the latest version.", UpdateWords.latest("1.1.0"))
    }
}
