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
