package com.flexweek.app.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.mutableStateOf
import com.flexweek.app.BuildConfig
import com.flexweek.app.bindings.updateAndroidRelease
import com.flexweek.app.bindings.updateDueForCheck
import com.flexweek.app.bindings.updateExpectedDigest
import com.flexweek.app.bindings.updateIsNewer
import com.flexweek.app.bindings.updateReleaseFromPage
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

data class OfferedUpdate(val version: String, val apkName: String, val apkUrl: String, val checksumUrl: String, val size: Long?, val notes: List<String>)
sealed interface UpdateState {
    data object Idle : UpdateState
    data object Checking : UpdateState
    data object UpToDate : UpdateState
    data class Available(val offer: OfferedUpdate, val message: String? = null) : UpdateState
    data class Downloading(val offer: OfferedUpdate, val received: Long, val total: Long) : UpdateState
    data class Verifying(val offer: OfferedUpdate) : UpdateState
    data class NeedsPermission(val offer: OfferedUpdate) : UpdateState
    data class Installing(val offer: OfferedUpdate) : UpdateState
    data class Failed(val reason: String) : UpdateState
}

interface UpdateSource {
    suspend fun get(url: String): String?
    suspend fun download(url: String, file: File, progress: (Long, Long) -> Unit): Boolean
}
interface UpdateInstaller {
    fun canInstall(): Boolean
    fun validApk(file: File, version: String): Boolean
    fun install(file: File): Boolean
}
interface UpdatePrefs { var checkDaily: Boolean; var lastChecked: Long? }
interface UpdateRules {
    fun due(enabled: Boolean, lastChecked: Long?, now: Long): Boolean
    fun offered(json: String, installed: String): OfferedUpdate?
    fun digest(text: String, apkName: String): String?
}
object RustUpdateRules : UpdateRules {
    override fun due(enabled: Boolean, lastChecked: Long?, now: Long) = updateDueForCheck(enabled, lastChecked, now)
    override fun offered(json: String, installed: String) = UpdateParsing.offered(json, installed)
    override fun digest(text: String, apkName: String) = updateExpectedDigest(text, apkName)
}

object UpdateParsing {
    fun offered(json: String, installed: String): OfferedUpdate? {
        val encoded = updateAndroidRelease(json, installed) ?: return null
        val data = JSONObject(encoded)
        val body = JSONObject(json).optString("body")
        val notes = UpdateNotes.head(body)
        return OfferedUpdate(data.getString("version"), data.getString("apk_name"), data.getString("apk_url"), data.getString("checksum_url"), if (data.isNull("apk_size")) null else data.getLong("apk_size"), notes)
    }
    fun allowed(url: String): Boolean = try {
        val uri = java.net.URI(url)
        uri.scheme == "https" && (uri.host == "github.com" || uri.host == "api.github.com" || uri.host?.endsWith(".githubusercontent.com") == true)
    } catch (_: Exception) { false }
    fun sha256(input: InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val bytes = ByteArray(32768)
        while (true) { val count = input.read(bytes); if (count < 0) break; digest.update(bytes, 0, count) }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

object AppVersion {
    fun isNewer(candidate: String, installed: String): Boolean = updateIsNewer(candidate, installed)
}
object UpdateRelease {
    fun offered(releaseJson: String, installed: String): OfferedUpdate? = UpdateParsing.offered(releaseJson, installed)
}
object UpdateDigest {
    fun expectedFor(text: String, apkName: String): String? = updateExpectedDigest(text, apkName)
    fun sha256Hex(input: InputStream): String = UpdateParsing.sha256(input)
    fun matches(actualHex: String, expectedHex: String?): Boolean = expectedHex?.let { it.length == 64 && it.all { char -> char.isDigitOrHex() } && actualHex.equals(it, true) } ?: false
    private fun Char.isDigitOrHex() = this in '0'..'9' || this.lowercaseChar() in 'a'..'f'
}
object UpdateSigner {
    fun matches(installed: List<ByteArray>, downloaded: List<ByteArray>): Boolean = installed.isNotEmpty() && downloaded.isNotEmpty() && installed.size == downloaded.size && installed.zip(downloaded).all { (a, b) -> a.contentEquals(b) }
    fun isValidUpdate(packageName: String?, versionName: String?, offeredVersion: String, installed: List<ByteArray>, downloaded: List<ByteArray>): Boolean =
        packageName == "com.flexweek.app" && versionName == offeredVersion && matches(installed, downloaded)
    fun refusalMessage(debugBuild: Boolean): String = if (debugBuild) "This test build can't update itself. Install FlexWeek from the release page." else "The downloaded app is signed differently. Nothing was installed."
}
object UpdateNotes {
    fun head(body: String): List<String> = body.split(Regex("\\r?\\n")).map(String::trim).filter(String::isNotEmpty).take(2)
}
object UpdateSchedule {
    const val CHECK_EVERY_MS = 24L * 60 * 60 * 1000
    fun dueForCheck(enabled: Boolean, lastCheckedMs: Long?, nowMs: Long): Boolean = updateDueForCheck(enabled, lastCheckedMs, nowMs)
}

class HttpUpdateSource : UpdateSource {
    override suspend fun get(url: String): String? {
        if (!UpdateParsing.allowed(url)) return null
        return try {
            val connection = connection(url)
            if (url.endsWith("/releases/latest") && connection.url.toString() != url) {
                updateReleaseFromPage(connection.url.toString())
            } else connection.inputStream.bufferedReader().use { it.readText() }
        } catch (_: Exception) { null }
    }
    override suspend fun download(url: String, file: File, progress: (Long, Long) -> Unit): Boolean {
        if (!UpdateParsing.allowed(url)) return false
        return try {
            val connection = connection(url)
            val total = connection.contentLengthLong.takeIf { it >= 0 } ?: -1L
            if (total > MAX_APK_BYTES) throw IllegalStateException("The download is too large.")
            connection.inputStream.use { input -> streamDownload(input, file, total, MAX_APK_BYTES, progress) }
            true
        } catch (error: IllegalStateException) {
            file.delete()
            throw error
        } catch (_: Exception) { file.delete(); false }
    }
    private fun connection(url: String): HttpURLConnection {
        var next = url
        repeat(6) {
            val current = (URL(next).openConnection() as HttpURLConnection).apply {
                connectTimeout = 15000
                readTimeout = 15000
                setRequestProperty("User-Agent", "FlexWeek-Android/${BuildConfig.VERSION_NAME}")
                instanceFollowRedirects = false
                connect()
            }
            if (current.responseCode !in 300..399) return current
            val location = current.getHeaderField("Location") ?: return current
            val target = URL(URL(next), location).toString()
            current.disconnect()
            if (!UpdateParsing.allowed(target)) throw IllegalArgumentException("Untrusted update host")
            next = target
        }
        throw IllegalStateException("Too many update redirects")
    }
    internal fun streamDownload(input: InputStream, file: File, total: Long, limit: Long = MAX_APK_BYTES, progress: (Long, Long) -> Unit) {
        try {
            file.outputStream().use { output ->
                val bytes = ByteArray(32768); var received = 0L
                while (true) {
                    val count = input.read(bytes)
                    if (count < 0) break
                    received += count
                    if (received > limit) throw IllegalStateException("The download is too large.")
                    output.write(bytes, 0, count)
                    progress(received, total)
                }
            }
        } catch (error: Exception) {
            file.delete()
            throw error
        }
    }
    companion object { const val MAX_APK_BYTES = 200L * 1024 * 1024 }
}

class SharedPreferenceUpdatePrefs(context: Context) : UpdatePrefs {
    private val prefs = context.getSharedPreferences("flexweek_update", Context.MODE_PRIVATE)
    override var checkDaily: Boolean
        get() = prefs.getBoolean("check_daily", true)
        set(value) { prefs.edit().putBoolean("check_daily", value).apply() }
    override var lastChecked: Long?
        get() = if (prefs.contains("last_checked")) prefs.getLong("last_checked", 0) else null
        set(value) { prefs.edit().apply { if (value == null) remove("last_checked") else putLong("last_checked", value) }.apply() }
}

class PackageUpdateInstaller(private val context: Context) : UpdateInstaller {
    override fun canInstall() = context.packageManager.canRequestPackageInstalls()
    override fun validApk(file: File, version: String): Boolean {
        return try {
            val info = context.packageManager.getPackageArchiveInfo(file.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES) ?: return false
            info.applicationInfo?.sourceDir = file.absolutePath
            UpdateSigner.isValidUpdate(info.packageName, info.versionName, version, signatureBytes(context.packageManager.getPackageInfo(context.packageName, PackageManager.GET_SIGNING_CERTIFICATES)), signatureBytes(info))
        } catch (_: Exception) { false }
    }
    @Suppress("DEPRECATION")
    private fun signatureBytes(info: android.content.pm.PackageInfo): List<ByteArray> =
        if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners?.map { it.toByteArray() } ?: emptyList()
        else info.signatures?.map { it.toByteArray() } ?: emptyList()
    override fun install(file: File): Boolean = try {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        val id = installer.createSession(params)
        installer.openSession(id).use { session ->
            file.inputStream().use { input -> session.openWrite(file.name, 0, file.length()).use { output -> input.copyTo(output); session.fsync(output) } }
            val intent = Intent(context, UpdateInstallReceiver::class.java).setAction(UpdateInstallReceiver.ACTION)
            val pending = android.app.PendingIntent.getBroadcast(context, id, intent, android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_MUTABLE)
            session.commit(pending.intentSender)
        }
        true
    } catch (_: Exception) { false }
}

class UpdateViewModel(private val installedVersion: String, private val source: UpdateSource, private val installer: UpdateInstaller, private val prefs: UpdatePrefs, private val updatesDir: File, private val now: () -> Long = System::currentTimeMillis, private val debug: Boolean = BuildConfig.DEBUG, private val worker: CoroutineDispatcher = Dispatchers.IO, private val rules: UpdateRules = RustUpdateRules) : ViewModel() {
    val state = mutableStateOf<UpdateState>(UpdateState.Idle)
    val checkDaily: Boolean get() = prefs.checkDaily
    private var busy = false
    fun start() { if (rules.due(prefs.checkDaily, prefs.lastChecked, now())) check(false) }
    fun checkNow() = check(true)
    private fun check(loud: Boolean) {
        if (busy) return
        busy = true; state.value = UpdateState.Checking
        viewModelScope.launch { try { val found = withContext(worker) { lookup() }; state.value = found ?: if (loud) UpdateState.Failed("Could not check for updates.") else UpdateState.Idle } finally { prefs.lastChecked = now(); busy = false } }
    }
    private suspend fun lookup(): UpdateState? {
        val json = source.get("https://api.github.com/repos/j0nsh1n/FlexWeek/releases/latest")
            ?: source.get("https://github.com/j0nsh1n/FlexWeek/releases/latest")
            ?: return null
        val offer = rules.offered(json, installedVersion) ?: return UpdateState.UpToDate
        return UpdateState.Available(offer)
    }
    fun setDailyCheck(on: Boolean) { prefs.checkDaily = on }
    fun downloadAndInstall() {
        val offer = (state.value as? UpdateState.Available)?.offer ?: return
        if (busy) return
        if (debug) { state.value = UpdateState.Failed(UpdateSigner.refusalMessage(true)); return }
        busy = true
        viewModelScope.launch { try {
            withContext(worker) {
                val checksum = source.get(offer.checksumUrl)?.let { rules.digest(it, offer.apkName) }
                    ?: throw IllegalStateException("Could not check the update checksum.")
                val part = File(updatesDir, offer.apkName + ".part"); val apk = File(updatesDir, offer.apkName); updatesDir.mkdirs(); part.delete()
                state.value = UpdateState.Downloading(offer, 0, offer.size ?: -1)
                if (!source.download(offer.apkUrl, part) { got, total -> state.value = UpdateState.Downloading(offer, got, total) }) {
                    val oversized = part.length() > HttpUpdateSource.MAX_APK_BYTES
                    part.delete()
                    throw IllegalStateException(if (oversized) "The download is too large." else "The download stopped.")
                }
                if (part.length() > HttpUpdateSource.MAX_APK_BYTES) { part.delete(); throw IllegalStateException("The download is too large.") }
                state.value = UpdateState.Downloading(offer, part.length(), offer.size ?: -1)
                state.value = UpdateState.Verifying(offer)
                val actual = part.inputStream().use(UpdateParsing::sha256)
                if (!UpdateDigest.matches(actual, checksum)) { part.delete(); throw IllegalStateException("The checksum did not match. The download was discarded.") }
                apk.delete()
                if (!part.renameTo(apk)) { part.delete(); throw IllegalStateException("Could not save the verified download.") }
                if (!installer.validApk(apk, offer.version)) { apk.delete(); throw IllegalStateException("The downloaded app does not match this FlexWeek release. Nothing was installed.") }
                if (!installer.canInstall()) { state.value = UpdateState.NeedsPermission(offer); return@withContext }
                if (!installer.install(apk)) throw IllegalStateException("Android's installer could not start.")
                state.value = UpdateState.Installing(offer)
            }
        } catch (error: Exception) { state.value = UpdateState.Failed(error.message ?: "The update could not be installed.") } finally { busy = false } }
    }
    fun later() { (state.value as? UpdateState.NeedsPermission)?.let { state.value = UpdateState.Available(it.offer) } }
    fun onResumed() {
        val offer = (state.value as? UpdateState.NeedsPermission)?.offer ?: return
        if (busy) return
        if (!installer.canInstall()) return
        busy = true
        val apk = File(updatesDir, offer.apkName)
        viewModelScope.launch {
            try {
                withContext(worker) {
                    if (!installer.validApk(apk, offer.version)) throw IllegalStateException("The verified update is no longer available.")
                    if (!installer.install(apk)) throw IllegalStateException("Android's installer could not start.")
                    state.value = UpdateState.Installing(offer)
                }
            } catch (error: Exception) { state.value = UpdateState.Failed(error.message ?: "The update could not be installed.") }
            finally { busy = false }
        }
    }
    fun onInstallResult(ok: Boolean, message: String?) { val current = state.value as? UpdateState.Installing ?: return; state.value = if (ok) UpdateState.UpToDate else UpdateState.Available(current.offer, "Not installed. Your week is as it was.") }
    fun onResumeCheck() = start()
}

class UpdateInstallReceiver : android.content.BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        onResult?.invoke(status == PackageInstaller.STATUS_SUCCESS, intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE))
    }
    companion object {
        const val ACTION = "com.flexweek.app.UPDATE_INSTALL_RESULT"
        @Volatile var onResult: ((Boolean, String?) -> Unit)? = null
    }
}
