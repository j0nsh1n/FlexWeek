package com.flexweek.app.update

import android.content.pm.PackageInstaller
import org.junit.Assert.assertEquals
import org.junit.Test

// An app that installs its own update is told first that the student must confirm (PENDING_USER_ACTION) and
// has to open Android's Install dialog itself; only the answer to that dialog is the result.
class UpdateInstallStatusTest {
    @Test fun pendingUserActionOpensAndroidsInstallDialog() {
        assertEquals(InstallStep.ShowAndroidsDialog, UpdateInstallStatus.step(PackageInstaller.STATUS_PENDING_USER_ACTION))
    }

    @Test fun successIsInstalled() {
        assertEquals(InstallStep.Finished(true), UpdateInstallStatus.step(PackageInstaller.STATUS_SUCCESS))
    }

    @Test fun cancellingTheDialogAndEveryFailureAreNotInstalled() {
        for (status in listOf(
            PackageInstaller.STATUS_FAILURE_ABORTED,
            PackageInstaller.STATUS_FAILURE,
            PackageInstaller.STATUS_FAILURE_BLOCKED,
            PackageInstaller.STATUS_FAILURE_CONFLICT,
            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE,
            PackageInstaller.STATUS_FAILURE_INVALID,
            PackageInstaller.STATUS_FAILURE_STORAGE,
        )) assertEquals("status $status", InstallStep.Finished(false), UpdateInstallStatus.step(status))
    }
}

class UpdateInstallerContextTest {
    // The installer cannot be built on the JVM (it needs a Context); the line that decides what it keeps is checked
    // in the source: an Activity kept by a ViewModel survives rotation as a leak.
    @Test fun theInstallerKeepsTheApplicationContextNotAnActivity() {
        val source = java.io.File("src/main/java/com/flexweek/app/update/UpdateRuntime.kt").readText()
        org.junit.Assert.assertTrue(
            "PackageUpdateInstaller must keep context.applicationContext",
            "class PackageUpdateInstaller(context: Context)" in source && "= context.applicationContext" in source,
        )
        val activity = java.io.File("src/main/java/com/flexweek/app/MainActivity.kt").readText()
        org.junit.Assert.assertFalse("MainActivity must not hand its Activity to the installer", "PackageUpdateInstaller(activity)" in activity)
    }
}
