package com.flexweek.app.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream

class UpdateParsingTest {
    @Test fun onlyGithubHttpsHostsAreAllowed() {
        assertTrue(UpdateParsing.allowed("https://github.com/a/b"))
        assertTrue(UpdateParsing.allowed("https://api.github.com/a"))
        assertTrue(UpdateParsing.allowed("https://release-assets.githubusercontent.com/a"))
        assertFalse(UpdateParsing.allowed("http://github.com/a"))
        assertFalse(UpdateParsing.allowed("https://github.com.evil.test/a"))
        assertFalse(UpdateParsing.allowed("https://evil.test/a"))
    }

    @Test fun sha256UsesStandardDigest() {
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            UpdateParsing.sha256(ByteArrayInputStream("abc".toByteArray())))
    }

    @Test fun checksumMustBeValidAndMatchExactly() {
        val digest = UpdateDigest.sha256Hex(ByteArrayInputStream("abc".toByteArray()))
        assertTrue(UpdateDigest.matches(digest.uppercase(), digest))
        assertFalse(UpdateDigest.matches(digest, null))
        assertFalse(UpdateDigest.matches(digest, "g" + digest.drop(1)))
    }

    @Test fun signaturesRequireNonEmptyByteEqualLists() {
        assertTrue(UpdateSigner.matches(listOf(byteArrayOf(1, 2)), listOf(byteArrayOf(1, 2))))
        assertFalse(UpdateSigner.matches(emptyList(), emptyList()))
        assertFalse(UpdateSigner.matches(listOf(byteArrayOf(1)), listOf(byteArrayOf(2))))
        assertTrue(UpdateSigner.refusalMessage(false).contains("nothing was installed", ignoreCase = true))
        assertTrue(UpdateSigner.refusalMessage(true).contains("debug", ignoreCase = true))
    }

}
