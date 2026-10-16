package com.flexweek.app.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream

class UpdateParsingTest {
    @get:Rule val files = TemporaryFolder()

    // Notes: the first 2 non-empty lines (Q7).

    @Test fun notesShowOnlyTheFirstTwoNonEmptyLines() {
        assertEquals(listOf("Month and Day on the phone.", "Widgets."), UpdateNotes.head("Month and Day on the phone.\r\nWidgets.\n\nLong tail…"))
        assertEquals(listOf("One", "Two"), UpdateNotes.head("\n\n  One  \r\n\r\nTwo\nThree\nFour"))
    }

    @Test fun notesWithFewerLinesAreKeptAsTheyAre() {
        assertEquals(listOf("Only line"), UpdateNotes.head("Only line\n"))
        assertEquals(emptyList<String>(), UpdateNotes.head(""))
    }

    // What the Rust offer JSON becomes on the phone (the JSON itself is built and tested in Rust).

    @Test fun offerFromRustJsonKeepsEveryFieldAndTheFirstTwoNotesLines() {
        val encoded = """{"version":"1.1.0","apk_name":"FlexWeek-Android-1.1.0.apk","apk_url":"https://github.com/a.apk","checksum_url":"https://github.com/a.sha256","notes":"ignored","apk_size":68123456}"""
        val offer = UpdateParsing.fromEncoded(encoded, "Month and Day.\r\nWidgets.\nThird")
        assertEquals(OfferedUpdate("1.1.0", "FlexWeek-Android-1.1.0.apk", "https://github.com/a.apk", "https://github.com/a.sha256", 68123456L, listOf("Month and Day.", "Widgets.")), offer)
    }

    @Test fun offerFromRustJsonWithoutASizeHasNoSize() {
        val encoded = """{"version":"1.1.0","apk_name":"FlexWeek-Android-1.1.0.apk","apk_url":"https://github.com/a.apk","checksum_url":"https://github.com/a.sha256","notes":"","apk_size":null}"""
        assertEquals(null, UpdateParsing.fromEncoded(encoded, "").size)
    }

    // Digest comparison (Kotlin side): exact lowercase hex; the .sha256 text itself is read in Rust.

    @Test fun sha256OfKnownBytesIsStandard() {
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            UpdateDigest.sha256Hex(ByteArrayInputStream("abc".toByteArray())))
    }

    @Test fun digestMatchIsExactAndIgnoresCase() {
        val digest = "a".repeat(63) + "b"
        assertTrue(UpdateDigest.matches(digest, digest))
        assertTrue(UpdateDigest.matches(digest, digest.uppercase()))
        assertTrue(UpdateDigest.matches(digest.uppercase(), digest))
        assertFalse(UpdateDigest.matches(digest, "a".repeat(63) + "c"))
    }

    @Test fun digestNeverMatchesWithoutAValidExpectedValue() {
        val digest = "a".repeat(64)
        assertFalse(UpdateDigest.matches(digest, null))
        assertFalse(UpdateDigest.matches(digest, ""))
        assertFalse(UpdateDigest.matches("a".repeat(63), "a".repeat(63)))
        assertFalse(UpdateDigest.matches("g" + "a".repeat(63), "g" + "a".repeat(63)))
    }

    // Signer, package name and version name (Q13).

    @Test fun identicalCertificateBytesMatchWhateverTheArrayInstances() {
        assertTrue(UpdateSigner.matches(listOf(byteArrayOf(1, 2, 3)), listOf(byteArrayOf(1, 2, 3))))
        assertTrue(UpdateSigner.matches(listOf(byteArrayOf(1), byteArrayOf(2)), listOf(byteArrayOf(1), byteArrayOf(2))))
    }

    @Test fun oneDifferentCertificateByteIsRefused() {
        assertFalse(UpdateSigner.matches(listOf(byteArrayOf(1, 2, 3)), listOf(byteArrayOf(1, 2, 4))))
        assertFalse(UpdateSigner.matches(listOf(byteArrayOf(1)), listOf(byteArrayOf(1), byteArrayOf(2))))
    }

    @Test fun emptyCertificateListsNeverMatch() {
        val cert = listOf(byteArrayOf(1, 2, 3))
        assertFalse(UpdateSigner.matches(emptyList(), emptyList()))
        assertFalse(UpdateSigner.matches(cert, emptyList()))
        assertFalse(UpdateSigner.matches(emptyList(), cert))
    }

    @Test fun updateIsValidOnlyForFlexweekAtTheOfferedVersionWithTheInstalledSigner() {
        val cert = listOf(byteArrayOf(1, 2, 3))
        assertTrue(UpdateSigner.isValidUpdate("com.flexweek.app", "1.1.0", "1.1.0", cert, cert))
    }

    @Test fun anotherPackageNameIsRefused() {
        val cert = listOf(byteArrayOf(1, 2, 3))
        assertFalse(UpdateSigner.isValidUpdate("other.app", "1.1.0", "1.1.0", cert, cert))
        assertFalse(UpdateSigner.isValidUpdate(null, "1.1.0", "1.1.0", cert, cert))
    }

    @Test fun anotherVersionNameThanTheOfferedOneIsRefused() {
        val cert = listOf(byteArrayOf(1, 2, 3))
        assertFalse(UpdateSigner.isValidUpdate("com.flexweek.app", "1.0.0", "1.1.0", cert, cert))
        assertFalse(UpdateSigner.isValidUpdate("com.flexweek.app", null, "1.1.0", cert, cert))
    }

    @Test fun anotherSigningCertificateIsRefusedEvenWithTheRightNameAndVersion() {
        assertFalse(UpdateSigner.isValidUpdate("com.flexweek.app", "1.1.0", "1.1.0", listOf(byteArrayOf(1)), listOf(byteArrayOf(2))))
    }

    @Test fun debugBuildRefusalIsExactlyTheBriefsSentence() {
        assertEquals("This test build can't update itself. Install FlexWeek from the release page.", UpdateSigner.refusalMessage(true))
    }

    @Test fun releaseBuildRefusalSaysNothingWasInstalledAndIsNotAnError() {
        val message = UpdateSigner.refusalMessage(false)
        assertTrue(message.contains("nothing was installed", ignoreCase = true))
        assertFalse(message.contains("exception", ignoreCase = true))
        assertFalse(message.contains("debug", ignoreCase = true))
    }

    // Host allow-list (Q12): https only, github.com, api.github.com, *.githubusercontent.com.

    @Test fun githubHttpsHostsAreAllowed() {
        assertTrue(UpdateParsing.allowed("https://github.com/a/b"))
        assertTrue(UpdateParsing.allowed("https://api.github.com/a"))
        assertTrue(UpdateParsing.allowed("https://release-assets.githubusercontent.com/a"))
        assertTrue(UpdateParsing.allowed("https://objects.githubusercontent.com/a"))
    }

    @Test fun plainHttpIsRefusedEvenOnGithub() {
        assertFalse(UpdateParsing.allowed("http://github.com/a"))
        assertFalse(UpdateParsing.allowed("http://api.github.com/a"))
        assertFalse(UpdateParsing.allowed("http://objects.githubusercontent.com/a"))
    }

    @Test fun lookAlikeHostsAreRefused() {
        assertFalse(UpdateParsing.allowed("https://evilgithub.com/a"))
        assertFalse(UpdateParsing.allowed("https://github.com.evil.test/a"))
        assertFalse(UpdateParsing.allowed("https://githubusercontent.com.evil.net/a"))
        assertFalse(UpdateParsing.allowed("https://evilgithubusercontent.com/a"))
        assertFalse(UpdateParsing.allowed("https://github.com@evil.test/a"))
        assertFalse(UpdateParsing.allowed("https://objects.githubusercontent.com.evil.net/a"))
        assertFalse(UpdateParsing.allowed("https://api.github.com.evil.net/a"))
        assertFalse(UpdateParsing.allowed("https://evil.test/a"))
    }

    @Test fun theBareGithubusercontentDomainAndNonUrlsAreRefused() {
        assertFalse(UpdateParsing.allowed("https://githubusercontent.com/a"))
        assertFalse(UpdateParsing.allowed("not a url"))
        assertFalse(UpdateParsing.allowed(""))
        assertFalse(UpdateParsing.allowed("file:///etc/passwd"))
    }

    // Size cap (Q11): 200 MB, enforced while streaming.

    @Test fun theCapIs200Megabytes() {
        assertEquals(200L * 1024 * 1024, HttpUpdateSource.MAX_APK_BYTES)
    }

    @Test fun streamStopsAndDeletesTheFileOnceItGoesPastTheLimit() {
        val file = files.newFile("over.part")
        val error = runCatching { HttpUpdateSource().streamDownload(ZeroStream(101), file, -1, 100) { _, _ -> } }.exceptionOrNull()
        assertTrue("oversize stream must throw", error is IllegalStateException)
        assertEquals("The download is too large.", error?.message)
        assertFalse("oversize partial file must be deleted", file.exists())
    }

    @Test fun streamAtExactlyTheLimitIsKept() {
        val file = files.newFile("exact.part")
        HttpUpdateSource().streamDownload(ZeroStream(100), file, -1, 100) { _, _ -> }
        assertEquals(100L, file.length())
    }

    @Test fun streamLimitIsCountedFromBytesReceivedNotFromTheAnnouncedTotal() {
        val file = files.newFile("lying.part")
        val error = runCatching { HttpUpdateSource().streamDownload(ZeroStream(5000), file, 10, 100) { _, _ -> } }.exceptionOrNull()
        assertTrue(error is IllegalStateException)
        assertFalse(file.exists())
    }

    @Test fun streamReportsReceivedAndTheTotalIncludingUnknownMinusOne() {
        val file = files.newFile("progress.part")
        val seen = mutableListOf<Pair<Long, Long>>()
        HttpUpdateSource().streamDownload(ZeroStream(10), file, -1, 100) { got, total -> seen += got to total }
        assertEquals(listOf(10L to -1L), seen)
    }

    @Test fun streamThatBreaksPartWayDeletesThePartialFile() {
        val file = files.newFile("broken.part")
        val broken = object : InputStream() {
            private var sent = false
            override fun read() = throw IOException("dropped")
            override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
                if (sent) throw IOException("dropped")
                sent = true; buffer.fill(0, offset, offset + 10); return 10
            }
        }
        val error = runCatching { HttpUpdateSource().streamDownload(broken, file, -1, 100) { _, _ -> } }.exceptionOrNull()
        assertTrue(error is IOException)
        assertFalse("a broken transfer must leave no file", file.exists())
    }

    private class ZeroStream(private var remaining: Long) : InputStream() {
        override fun read(): Int { if (remaining == 0L) return -1; remaining--; return 0 }
        override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            if (remaining == 0L) return -1
            val count = minOf(length.toLong(), remaining).toInt()
            buffer.fill(0.toByte(), offset, offset + count)
            remaining -= count
            return count
        }
    }
}
