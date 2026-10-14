package com.flexweek.app.core

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicBoolean

class CoreStartupTest {
    @Test
    fun opensTheRustCoreOffTheCallingThread() = runBlocking {
        val callingThread = Thread.currentThread()
        val calledOffThread = AtomicBoolean(true)
        val delegate = FakeFlexWeekCore()
        val core = object : FlexWeekCore by delegate {
            override fun open(dbPath: String, deviceName: String) {
                calledOffThread.set(Thread.currentThread() !== callingThread)
                delegate.open(dbPath, deviceName)
            }

            override fun isPaired(): Boolean {
                calledOffThread.compareAndSet(true, Thread.currentThread() !== callingThread)
                return delegate.isPaired()
            }
        }

        core.openForPhone("test.db")

        assertTrue("Rust startup calls must leave the calling thread", calledOffThread.get())
    }
}
