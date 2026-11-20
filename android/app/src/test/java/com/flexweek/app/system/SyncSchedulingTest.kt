package com.flexweek.app.system

import androidx.work.ExistingWorkPolicy
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class SyncSchedulingTest {
    @Test fun aLocalEditsSyncNeverReplacesOneThatIsRunning() {
        assertNotEquals(ExistingWorkPolicy.REPLACE, SyncScheduler.EDIT_SYNC_POLICY)
        assertEquals(ExistingWorkPolicy.KEEP, SyncScheduler.EDIT_SYNC_POLICY)
    }

    @Test fun aBackgroundSyncGetsTheDesktopsFortyFiveSeconds() {
        assertEquals(45_000L, SyncWorker.SYNC_DEADLINE_MS)
    }

    @Test fun theBackoffGrowsWhileTheComputerIsOffAndResetsOnSuccess() {
        var pause = SyncBackoff.BASE_MS
        val seen = mutableListOf<Long>()
        repeat(6) { pause = SyncBackoff.next(pause, ok = false); seen += pause }
        assertEquals(listOf(10_000L, 20_000L, 40_000L, 60_000L, 60_000L, 60_000L), seen)
        assertEquals(SyncBackoff.BASE_MS, SyncBackoff.next(pause, ok = true))
    }

    // The worker and the manifest cannot run on the JVM; the manifest entry that lets Android 11 and older start the
    // foreground service, and the override that feeds it, are checked in the source.
    @Test fun theWorkerCanRunAsAForegroundServiceOnAndroid11AndOlder() {
        val worker = File("src/main/java/com/flexweek/app/system/SyncWorker.kt").readText()
        assertTrue("SyncWorker must override getForegroundInfo", "override suspend fun getForegroundInfo" in worker)
        assertTrue("it uses the existing sync channel", "FlexWeekApp.CHANNEL_SYNC" in worker)
        val manifest = File("src/main/AndroidManifest.xml").readText()
        assertTrue("WorkManager's foreground service needs a data-sync type", "foregroundServiceType=\"dataSync\"" in manifest)
    }
}
