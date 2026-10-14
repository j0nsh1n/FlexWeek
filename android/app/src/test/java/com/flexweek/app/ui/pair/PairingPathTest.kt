package com.flexweek.app.ui.pair

import org.junit.Assert.assertEquals
import org.junit.Test

class PairingPathTest {
    @Test fun desktopInstructionsNameTheCurrentPairingPath() {
        assertEquals("Settings > This computer > Devices > Pair a phone", DESKTOP_PAIR_PATH)
    }
}
