package com.flexweek.app.system

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ForegroundSyncTest {
    @Test fun syncPausesInTheBackgroundAndResumesOnOpen() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            lateinit var registry: LifecycleRegistry
            val owner = object : LifecycleOwner {
                override val lifecycle: Lifecycle get() = registry
            }
            registry = LifecycleRegistry.createUnsafe(owner)
            registry.currentState = Lifecycle.State.CREATED
            var calls = 0
            var refreshed = 0
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun syncOnce(deadlineMs: Long): String {
                    assertEquals(10_000L, deadlineMs)
                    calls += 1
                    return "{\"ok\":true}"
                }
            }
            val job = backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
                syncWhileForeground(core, registry, dispatcher) { refreshed += 1 }
            }
            runCurrent()
            assertEquals(0, calls)
            registry.currentState = Lifecycle.State.STARTED
            runCurrent()
            assertEquals(1, calls)
            advanceTimeBy(5_000)
            runCurrent()
            assertEquals(2, calls)
            registry.currentState = Lifecycle.State.CREATED
            runCurrent()
            advanceTimeBy(15_000)
            runCurrent()
            assertEquals(2, calls)
            assertEquals(2, refreshed)
            registry.currentState = Lifecycle.State.STARTED
            runCurrent()
            assertEquals(3, calls)
            registry.currentState = Lifecycle.State.DESTROYED
            job.join()
        } finally {
            Dispatchers.resetMain()
        }
    }
}
