package com.flexweek.app.update

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

// The rules themselves (versions, digest text, release choice, daily timing) are Rust and are tested in
// engine/engine/tests/desk_update.rs and engine/ffi/src/update.rs. The JVM cannot load the Rust library, so
// these tests run the view model against fakes and check the glue: what it asks, what it never does.
@OptIn(ExperimentalCoroutinesApi::class)
class UpdateViewModelTest {
    @get:Rule val files = TemporaryFolder()
    private val dispatcher = UnconfinedTestDispatcher()

    private fun main(block: () -> Unit) {
        Dispatchers.setMain(dispatcher)
        try { block() } finally { Dispatchers.resetMain() }
    }

    // Daily check wiring

    @Test fun dailyCheckIsOnByDefault() = main {
        val vm = viewModel(FakeSource(), FakeInstaller(), FakePrefs())
        assertTrue(vm.checkDaily)
    }

    @Test fun startAsksTheRustScheduleWithTheSettingTheLastCheckAndTheClock() = main {
        val rules = FakeRules()
        val prefs = FakePrefs().also { it.checkDaily = false; it.lastChecked = 42L }
        viewModel(FakeSource(), FakeInstaller(), prefs, rules = rules).start()
        assertEquals(Triple(false, 42L, NOW), rules.lastDueArguments)
    }

    @Test fun startChecksWhenTheScheduleSaysDue() = main {
        val source = FakeSource()
        viewModel(source, FakeInstaller(), FakePrefs(), rules = FakeRules().also { it.isDue = true }).start()
        assertEquals(1, source.latestCalls)
    }

    @Test fun startDoesNotCheckWhenTheScheduleSaysNotDue() = main {
        val source = FakeSource()
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), rules = FakeRules().also { it.isDue = false })
        vm.start()
        assertEquals(0, source.latestCalls)
        assertEquals(UpdateState.Idle, vm.state.value)
    }

    @Test fun resumeRunsTheSameDailyRule() = main {
        val source = FakeSource()
        val rules = FakeRules().also { it.isDue = false }
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), rules = rules)
        vm.onResumeCheck()
        assertEquals(1, rules.dueCalls)
        assertEquals(0, source.latestCalls)
        rules.isDue = true
        vm.onResumeCheck()
        assertEquals(1, source.latestCalls)
    }

    @Test fun togglingDailyCheckOffIsRememberedByANewViewModel() = main {
        val prefs = FakePrefs()
        viewModel(FakeSource(), FakeInstaller(), prefs).setDailyCheck(false)
        assertFalse(prefs.checkDaily)
        val later = viewModel(FakeSource(), FakeInstaller(), prefs)
        assertFalse(later.checkDaily)
        val rules = FakeRules()
        viewModel(FakeSource(), FakeInstaller(), prefs, rules = rules).start()
        assertEquals(false, rules.lastDueArguments?.first)
    }

    @Test fun togglingDailyCheckBackOnIsRemembered() = main {
        val prefs = FakePrefs().also { it.checkDaily = false }
        viewModel(FakeSource(), FakeInstaller(), prefs).setDailyCheck(true)
        assertTrue(prefs.checkDaily)
    }

    @Test fun everyCheckRecordsItsTimeEvenWhenItFails() = main {
        val prefs = FakePrefs()
        viewModel(FakeSource(), FakeInstaller(), prefs).start()
        assertEquals(NOW, prefs.lastChecked)
        val manualPrefs = FakePrefs()
        viewModel(FakeSource(), FakeInstaller(), manualPrefs).checkNow()
        assertEquals(NOW, manualPrefs.lastChecked)
    }

    @Test fun dailyCheckWithoutNetworkStaysSilent() = main {
        val source = FakeSource()
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        vm.start()
        assertEquals(1, source.latestCalls)
        assertEquals(UpdateState.Idle, vm.state.value)
        assertEquals(0, source.downloadCalls)
    }

    @Test fun dailyCheckThatFindsAnUpdateOffersItButDownloadsNothing() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller()
        val dir = files.newFolder("daily-offer")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.start()
        assertTrue(vm.state.value is UpdateState.Available)
        assertEquals(0, source.downloadCalls)
        assertEquals(0, source.checksumCalls)
        assertEquals(0, installer.installCalls)
        assertEquals(0, dir.listFiles()?.size ?: 0)
    }

    // Check now

    @Test fun checkNowShowsCheckingUntilTheRequestCompletes() = main {
        val source = FakeSource().also { it.pendingLatest = CompletableDeferred() }
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        vm.checkNow()
        assertEquals(UpdateState.Checking, vm.state.value)
        source.pendingLatest!!.complete("current")
        assertEquals(UpdateState.UpToDate, vm.state.value)
    }

    @Test fun checkNowWithoutNetworkSaysItCouldNotCheck() = main {
        val vm = viewModel(FakeSource(), FakeInstaller(), FakePrefs())
        vm.checkNow()
        assertTrue("manual offline check was ${vm.state.value}", vm.state.value is UpdateState.Failed)
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("could not check", ignoreCase = true))
    }

    @Test fun checkNowFallsBackToTheReleasePageWhenTheApiRefuses() = main {
        val source = FakeSource().also { it.apiRefuses = true; it.release = "available" }
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        vm.checkNow()
        assertTrue(vm.state.value is UpdateState.Available)
        assertEquals(1, source.pageCalls)
    }

    @Test fun availableOfferCarriesSizeAndTwoNotesLines() = main {
        val vm = viewModel(FakeSource().also { it.release = "available" }, FakeInstaller(), FakePrefs())
        vm.checkNow()
        val offer = (vm.state.value as UpdateState.Available).offer
        assertEquals("1.1.0", offer.version)
        assertEquals(68123456L, offer.size)
        assertEquals(listOf("Month and Day", "Widgets"), offer.notes)
    }

    @Test fun availableOfferWithoutSizeIsStillOffered() = main {
        val rules = FakeRules().also { it.size = null }
        val vm = viewModel(FakeSource().also { it.release = "available" }, FakeInstaller(), FakePrefs(), rules = rules)
        vm.checkNow()
        assertNull((vm.state.value as UpdateState.Available).offer.size)
    }

    // Nothing runs before the button

    @Test fun nothingDownloadsOrInstallsBeforeTheButton() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller()
        val dir = files.newFolder("before-button")
        val vm = viewModel(source, installer, FakePrefs(), dir, rules = FakeRules().also { it.isDue = true })
        val steps = listOf<() -> Unit>(vm::start, vm::onResumed, vm::onResumeCheck, vm::checkNow, { vm.setDailyCheck(true) }, vm::later)
        for (step in steps) {
            step()
            assertEquals(0, source.downloadCalls)
            assertEquals(0, source.checksumCalls)
            assertEquals(0, installer.installCalls)
            assertEquals(0, dir.listFiles()?.size ?: 0)
        }
    }

    @Test fun pressingDownloadTwiceDownloadsOnce() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller()
        val vm = viewModel(source, installer, FakePrefs())
        vm.checkNow()
        vm.downloadAndInstall()
        vm.downloadAndInstall()
        assertEquals(1, source.downloadCalls)
        assertEquals(1, installer.installCalls)
        assertTrue(vm.state.value is UpdateState.Installing)
    }

    @Test fun downloadFromAnythingButAnOfferDoesNothing() = main {
        val source = FakeSource()
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        vm.downloadAndInstall()
        assertEquals(UpdateState.Idle, vm.state.value)
        assertEquals(0, source.downloadCalls)
        assertEquals(0, source.checksumCalls)
    }

    // Download, verify, install

    @Test fun progressReportsReceivedOfTotal() = main {
        val source = FakeSource().also { it.release = "available"; it.progressEvents = listOf(10L to 100L, 50L to 100L) }
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        val seen = mutableListOf<Pair<Long, Long>>()
        source.onProgress = { (vm.state.value as? UpdateState.Downloading)?.let { seen += it.received to it.total } }
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals(listOf(10L to 100L, 50L to 100L), seen)
    }

    @Test fun unknownTotalIsKeptAsMinusOne() = main {
        val source = FakeSource().also { it.release = "available"; it.progressEvents = listOf(10L to -1L) }
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        val seen = mutableListOf<Pair<Long, Long>>()
        source.onProgress = { (vm.state.value as? UpdateState.Downloading)?.let { seen += it.received to it.total } }
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals(listOf(10L to -1L), seen)
    }

    @Test fun theFileIsCheckedWhileTheStateSaysVerifying() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller()
        val vm = viewModel(source, installer, FakePrefs())
        var stateWhenChecked: UpdateState? = null
        installer.onValidate = { stateWhenChecked = vm.state.value }
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue("was $stateWhenChecked", stateWhenChecked is UpdateState.Verifying)
    }

    @Test fun missingChecksumRefusesBeforeAnyDownload() = main {
        val source = FakeSource().also { it.release = "available"; it.digest = null }
        val dir = files.newFolder("no-checksum")
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("checksum", ignoreCase = true))
        assertEquals(0, source.downloadCalls)
        assertEquals(0, dir.listFiles()?.size ?: 0)
    }

    @Test fun checksumTextWithoutTheApkLineRefusesBeforeAnyDownload() = main {
        val source = FakeSource().also { it.release = "available"; it.digest = "not a digest line" }
        val vm = viewModel(source, FakeInstaller(), FakePrefs())
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("checksum", ignoreCase = true))
        assertEquals(0, source.downloadCalls)
    }

    @Test fun digestMismatchDeletesTheFileAndSaysSo() = main {
        val source = FakeSource().also { it.release = "available"; it.digest = "0".repeat(64) }
        val installer = FakeInstaller()
        val dir = files.newFolder("mismatch")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        val reason = (vm.state.value as UpdateState.Failed).reason
        assertTrue(reason, reason.contains("did not match"))
        assertTrue(reason, reason.contains("discarded"))
        assertEquals(0, dir.listFiles()?.size ?: 0)
        assertEquals(0, installer.installCalls)
    }

    @Test fun anUpperCaseDigestInTheChecksumFileStillPasses() = main {
        val source = FakeSource().also { it.release = "available"; it.digest = FakeSource.ABC_DIGEST.uppercase() }
        val installer = FakeInstaller()
        val vm = viewModel(source, installer, FakePrefs())
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals(1, installer.installCalls)
    }

    @Test fun failedTransferDeletesThePartialFileAndSaysItStopped() = main {
        val source = FakeSource().also { it.release = "available"; it.transferOk = false }
        val dir = files.newFolder("partial")
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("stopped"))
        assertEquals(0, dir.listFiles()?.size ?: 0)
    }

    @Test fun downloadWrittenToAPartFileAndOnlyRenamedAfterTheDigestMatches() = main {
        val source = FakeSource().also { it.release = "available" }
        val dir = files.newFolder("part-name")
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals(listOf("FlexWeek-Android-1.1.0.apk.part"), source.targetNames)
        assertEquals(listOf("FlexWeek-Android-1.1.0.apk"), dir.listFiles()!!.map { it.name })
    }

    @Test fun wrongSignerPackageOrVersionDeletesTheApkAndInstallsNothing() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller().also { it.valid = false }
        val dir = files.newFolder("identity")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue("invalid APK must be refused; was ${vm.state.value}", vm.state.value is UpdateState.Failed)
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("Nothing was installed"))
        assertEquals(0, installer.installCalls)
        assertEquals(0, dir.listFiles()?.size ?: 0)
        assertEquals(listOf("1.1.0"), installer.validatedVersions)
    }

    @Test fun pressingDownloadWhileTheChecksumIsStillLoadingDownloadsOnce() = main {
        val source = FakeSource().also { it.release = "available"; it.pendingChecksum = CompletableDeferred() }
        val installer = FakeInstaller()
        val vm = viewModel(source, installer, FakePrefs())
        vm.checkNow()
        vm.downloadAndInstall()
        vm.downloadAndInstall()
        source.pendingChecksum!!.complete(FakeSource.ABC_DIGEST)
        assertEquals(1, source.checksumCalls)
        assertEquals(1, source.downloadCalls)
        assertEquals(1, installer.installCalls)
    }

    @Test fun aFileLargerThanTheCapIsRefusedAndDeletedEvenIfTheSourceSaidItWorked() = main {
        val source = FakeSource().also { it.release = "available"; it.sparseBytes = 200L * 1024 * 1024 + 1 }
        val installer = FakeInstaller()
        val dir = files.newFolder("too-large")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals("The download is too large.", (vm.state.value as UpdateState.Failed).reason)
        assertEquals(0, dir.listFiles()?.size ?: 0)
        assertEquals(0, installer.installCalls)
    }

    @Test fun anOversizeTransferThatReportsFailureSaysTooLargeNotStopped() = main {
        val source = FakeSource().also { it.release = "available"; it.sparseBytes = 200L * 1024 * 1024 + 1; it.transferOk = false }
        val dir = files.newFolder("too-large-stopped")
        val vm = viewModel(source, FakeInstaller(), FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals("The download is too large.", (vm.state.value as UpdateState.Failed).reason)
        assertEquals(0, dir.listFiles()?.size ?: 0)
    }

    @Test fun aSourceThatStopsTheStreamForSizeLeavesNoPartFileBehind() = main {
        val source = FakeSource().also { it.release = "available"; it.throwAfterWrite = IllegalStateException("The download is too large.") }
        val installer = FakeInstaller()
        val dir = files.newFolder("stream-stopped")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertEquals("The download is too large.", (vm.state.value as UpdateState.Failed).reason)
        assertEquals(0, dir.listFiles()?.size ?: 0)
        assertEquals(0, installer.installCalls)
    }

    // Debug build (Q14)

    @Test fun debugBuildRefusesWithTheExactSentenceBeforeAnyDownload() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller()
        val dir = files.newFolder("debug")
        val vm = viewModel(source, installer, FakePrefs(), dir, debug = true)
        vm.checkNow()
        val callsBeforePress = source.allCalls.toList()
        vm.downloadAndInstall()
        assertTrue("debug refusal was ${vm.state.value}", vm.state.value is UpdateState.Failed)
        assertEquals("This test build can't update itself. Install FlexWeek from the release page.", (vm.state.value as UpdateState.Failed).reason)
        assertEquals(callsBeforePress, source.allCalls)
        assertEquals(0, source.downloadCalls)
        assertEquals(0, source.checksumCalls)
        assertEquals(0, installer.installCalls)
        assertEquals(0, dir.listFiles()?.size ?: 0)
    }

    // Permission and the system dialog

    @Test fun noInstallPermissionKeepsTheVerifiedApkAndInstallsNothing() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller().also { it.allowed = false }
        val dir = files.newFolder("permission")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue(vm.state.value is UpdateState.NeedsPermission)
        assertEquals(0, installer.installCalls)
        assertTrue(File(dir, "FlexWeek-Android-1.1.0.apk").exists())
    }

    @Test fun returningWithoutPermissionStaysOnTheSteps() = main {
        val installer = FakeInstaller().also { it.allowed = false }
        val vm = viewModel(FakeSource().also { it.release = "available" }, installer, FakePrefs())
        vm.checkNow(); vm.downloadAndInstall()
        vm.onResumed()
        assertTrue(vm.state.value is UpdateState.NeedsPermission)
        assertEquals(0, installer.installCalls)
    }

    @Test fun permissionGrantedOnReturnInstallsTheVerifiedFileOnceWithoutDownloadingAgain() = main {
        val source = FakeSource().also { it.release = "available" }
        val installer = FakeInstaller().also { it.allowed = false }
        val dir = files.newFolder("granted")
        val vm = viewModel(source, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        installer.allowed = true
        vm.onResumed()
        vm.onResumed()
        assertTrue(vm.state.value is UpdateState.Installing)
        assertEquals(listOf(File(dir, "FlexWeek-Android-1.1.0.apk")), installer.installedFiles)
        assertEquals(1, source.downloadCalls)
    }

    @Test fun laterReturnsToTheOfferAndInstallsNothing() = main {
        val installer = FakeInstaller().also { it.allowed = false }
        val vm = viewModel(FakeSource().also { it.release = "available" }, installer, FakePrefs())
        vm.checkNow(); vm.downloadAndInstall()
        vm.later()
        assertTrue(vm.state.value is UpdateState.Available)
        assertEquals(0, installer.installCalls)
    }

    @Test fun installerThatWillNotStartSaysSoAndKeepsTheApk() = main {
        val installer = FakeInstaller().also { it.startInstall = false }
        val dir = files.newFolder("wont-start")
        val vm = viewModel(FakeSource().also { it.release = "available" }, installer, FakePrefs(), dir)
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue((vm.state.value as UpdateState.Failed).reason.contains("installer could not start"))
        assertTrue(File(dir, "FlexWeek-Android-1.1.0.apk").exists())
    }

    @Test fun cancellingAndroidsDialogReturnsToTheOfferWithoutFailing() = main {
        val installer = FakeInstaller()
        val vm = viewModel(FakeSource().also { it.release = "available" }, installer, FakePrefs())
        vm.checkNow(); vm.downloadAndInstall()
        assertTrue(vm.state.value is UpdateState.Installing)
        vm.onInstallResult(false, "cancelled")
        val state = vm.state.value as UpdateState.Available
        assertEquals("Not installed. Your week is as it was.", state.message)
        assertEquals("1.1.0", state.offer.version)
    }

    @Test fun anInstallResultWithNothingInstallingChangesNothing() = main {
        val vm = viewModel(FakeSource().also { it.release = "available" }, FakeInstaller(), FakePrefs())
        vm.checkNow()
        val before = vm.state.value
        vm.onInstallResult(false, "cancelled")
        assertEquals(before, vm.state.value)
    }

    private fun viewModel(source: FakeSource, installer: FakeInstaller, prefs: FakePrefs, dir: File = files.root, debug: Boolean = false, rules: FakeRules = FakeRules()) =
        UpdateViewModel("1.0.0", source, installer, prefs, dir, { NOW }, debug, dispatcher, rules)

    private class FakeSource : UpdateSource {
        var release: String? = null
        var apiRefuses = false
        var pendingLatest: CompletableDeferred<String?>? = null
        var digest: String? = ABC_DIGEST
        var latestCalls = 0
        var pageCalls = 0
        var checksumCalls = 0
        var downloadCalls = 0
        val allCalls = mutableListOf<String>()
        val targetNames = mutableListOf<String>()
        var progressEvents: List<Pair<Long, Long>> = emptyList()
        var onProgress: (() -> Unit)? = null
        var transferOk = true
        var pendingChecksum: CompletableDeferred<String?>? = null
        var sparseBytes: Long? = null
        var throwAfterWrite: Exception? = null
        override suspend fun get(url: String): String? {
            allCalls += "get $url"
            if (url.startsWith("https://api.github.com/") && url.endsWith("/releases/latest")) {
                latestCalls++
                if (apiRefuses) return null
                return pendingLatest?.await() ?: release
            }
            if (url.startsWith("https://github.com/") && url.endsWith("/releases/latest")) { pageCalls++; return release }
            if (url.endsWith(".sha256")) { checksumCalls++; return pendingChecksum?.await() ?: digest }
            return null
        }
        override suspend fun download(url: String, file: File, progress: (Long, Long) -> Unit): Boolean {
            allCalls += "download $url"
            downloadCalls++; targetNames += file.name; file.writeBytes("abc".toByteArray())
            sparseBytes?.let { java.io.RandomAccessFile(file, "rw").use { raf -> raf.setLength(it) } }
            throwAfterWrite?.let { throw it }
            (if (progressEvents.isEmpty()) listOf(3L to 3L) else progressEvents).forEach { (got, total) -> progress(got, total); onProgress?.invoke() }
            return transferOk
        }
        companion object { const val ABC_DIGEST = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" }
    }

    private class FakeInstaller : UpdateInstaller {
        var installCalls = 0
        var allowed = true
        var valid = true
        var startInstall = true
        var onValidate: (() -> Unit)? = null
        val validatedVersions = mutableListOf<String>()
        val installedFiles = mutableListOf<File>()
        override fun canInstall() = allowed
        override fun validApk(file: File, version: String): Boolean { validatedVersions += version; onValidate?.invoke(); return valid }
        override fun install(file: File): Boolean { installCalls++; installedFiles += file; return startInstall }
    }

    private class FakePrefs : UpdatePrefs { override var checkDaily = true; override var lastChecked: Long? = null }

    // The real rules are Rust. This fake only returns what the test says and records what it was asked.
    private class FakeRules : UpdateRules {
        var size: Long? = 68123456L
        var isDue = true
        var dueCalls = 0
        var lastDueArguments: Triple<Boolean, Long?, Long>? = null
        override fun due(enabled: Boolean, lastChecked: Long?, now: Long): Boolean { dueCalls++; lastDueArguments = Triple(enabled, lastChecked, now); return isDue }
        override fun offered(json: String, installed: String) = if (json == "available") OfferedUpdate("1.1.0", "FlexWeek-Android-1.1.0.apk", "https://github.com/a.apk", "https://github.com/a.sha256", size, listOf("Month and Day", "Widgets")) else null
        override fun digest(text: String, apkName: String) = text.takeIf { it.length == 64 }
    }

    private companion object { const val NOW = 100L }
}
