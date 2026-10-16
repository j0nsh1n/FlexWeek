package com.flexweek.app.update

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

@OptIn(ExperimentalCoroutinesApi::class)
class UpdateViewModelTest {
    @get:Rule val files = TemporaryFolder()
    private val dispatcher = UnconfinedTestDispatcher()

    @Test fun silentDailyCheckDoesNotReportOfflineAndNeverDownloads() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource()
            val prefs = FakePrefs()
            val installer = FakeInstaller()
            val vm = viewModel(source, installer, prefs)
            vm.start()
            assertEquals(UpdateState.Idle, vm.state.value)
            assertEquals(1, source.latestCalls)
            assertEquals(0, source.downloadCalls)
            assertEquals(0, installer.installCalls)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun checkNowReportsOfflineWithoutDownloading() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource()
            val vm = viewModel(source, FakeInstaller(), FakePrefs())
            vm.checkNow()
            assertTrue((vm.state.value as UpdateState.Failed).reason.contains("could not check", true))
            assertEquals(0, source.downloadCalls)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun offerDoesNotDownloadUntilPressedAndRepeatedPressDownloadsOnce() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource().also { it.release = "available" }
            val installer = FakeInstaller()
            val vm = viewModel(source, installer, FakePrefs())
            vm.checkNow()
            assertTrue(vm.state.value is UpdateState.Available)
            assertEquals(0, source.downloadCalls)
            vm.downloadAndInstall()
            vm.downloadAndInstall()
            assertEquals(1, source.downloadCalls)
            assertTrue(vm.state.value is UpdateState.Installing)
            assertEquals(1, installer.installCalls)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun digestMismatchDiscardsPartialFileAndDoesNotInstall() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource().also { it.release = "available"; it.digest = "0".repeat(64) }
            val installer = FakeInstaller()
            val dir = files.newFolder("updates")
            val vm = viewModel(source, installer, FakePrefs(), dir)
            vm.checkNow()
            vm.downloadAndInstall()
            assertTrue((vm.state.value as UpdateState.Failed).reason.contains("did not match"))
            assertEquals(0, dir.listFiles()?.size ?: 0)
            assertEquals(0, installer.installCalls)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun missingPermissionKeepsVerifiedApkAndReturnInstallsItOnce() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource().also { it.release = "available" }
            val installer = FakeInstaller().also { it.allowed = false }
            val vm = viewModel(source, installer, FakePrefs())
            vm.checkNow()
            vm.downloadAndInstall()
            assertTrue(vm.state.value is UpdateState.NeedsPermission)
            assertEquals(0, installer.installCalls)
            installer.allowed = true
            vm.onResumed()
            assertTrue(vm.state.value is UpdateState.Installing)
            assertEquals(1, installer.installCalls)
            assertEquals(1, source.downloadCalls)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun laterAndCancelledInstallerReturnToOfferWithoutChangingWeek() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource().also { it.release = "available" }
            val installer = FakeInstaller().also { it.allowed = false }
            val vm = viewModel(source, installer, FakePrefs())
            vm.checkNow(); vm.downloadAndInstall(); vm.later()
            assertTrue(vm.state.value is UpdateState.Available)
            assertEquals(0, installer.installCalls)
            installer.allowed = true
            vm.downloadAndInstall()
            vm.onInstallResult(false, "cancelled")
            val state = vm.state.value as UpdateState.Available
            assertEquals("Not installed. Your week is as it was.", state.message)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun debugBuildRefusesBeforeFetchingOrDownloadingTheApk() {
        Dispatchers.setMain(dispatcher)
        try {
            val source = FakeSource().also { it.release = "available" }
            val vm = viewModel(source, FakeInstaller(), FakePrefs(), debug = true)
            vm.checkNow(); vm.downloadAndInstall()
            assertEquals(0, source.downloadCalls)
            assertTrue((vm.state.value as UpdateState.Failed).reason.contains("can't update itself"))
        } finally { Dispatchers.resetMain() }
    }

    private fun viewModel(source: FakeSource, installer: FakeInstaller, prefs: FakePrefs, dir: File = files.root, debug: Boolean = false) =
        UpdateViewModel("1.0.0", source, installer, prefs, dir, { 100L }, debug, dispatcher, FakeRules())

    private class FakeSource : UpdateSource {
        var release: String? = null
        var digest: String = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        var latestCalls = 0
        var downloadCalls = 0
        override suspend fun get(url: String): String? { if (url.startsWith("https://api.github.com/")) latestCalls++; return if (url.endsWith(".sha256")) digest else release }
        override suspend fun download(url: String, file: File, progress: (Long, Long) -> Unit): Boolean { downloadCalls++; file.writeBytes("abc".toByteArray()); progress(3, 3); return true }
    }
    private class FakeInstaller : UpdateInstaller {
        var installCalls = 0
        var allowed = true
        override fun canInstall() = allowed
        override fun validApk(file: File, version: String) = true
        override fun install(file: File): Boolean { installCalls++; return true }
    }
    private class FakePrefs : UpdatePrefs { override var checkDaily = true; override var lastChecked: Long? = null }
    private class FakeRules : UpdateRules {
        override fun due(enabled: Boolean, lastChecked: Long?, now: Long) = enabled && (lastChecked == null || now - lastChecked >= UpdateSchedule.CHECK_EVERY_MS || now < lastChecked)
        override fun offered(json: String, installed: String) = if (json == "available") OfferedUpdate("1.1.0", "FlexWeek-Android-1.1.0.apk", "https://github.com/a.apk", "https://github.com/a.sha256", null, emptyList()) else null
        override fun digest(text: String, apkName: String) = text.takeIf { it.length == 64 }
    }
}
