package com.flexweek.app

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

// A receiver that is not in the manifest never gets its broadcast: the focus end alarm was routed to one
// that was missing, so on a phone it would have done nothing, and no JVM test could see it. A home-screen
// widget's provider is a receiver too.
class ManifestReceiversTest {
    @Test fun everyBroadcastReceiverInTheAppIsDeclared() {
        val root = File("src/main/java/com/flexweek/app")
        val manifest = File("src/main/AndroidManifest.xml").readText()
        val receivers = root.walk().filter { it.extension == "kt" }.flatMap { file ->
            Regex("""class (\w+)\s*:\s*(?:android\.content\.BroadcastReceiver|android\.appwidget\.AppWidgetProvider|BroadcastReceiver|AppWidgetProvider)\(\)""").findAll(file.readText()).map {
                val folder = file.parentFile.relativeTo(root).path.replace(File.separatorChar, '.')
                (if (folder.isEmpty()) "." else ".$folder.") + it.groupValues[1]
            }
        }.toList()
        assertTrue("the app has receivers to check", receivers.isNotEmpty())
        val missing = receivers.filter { "android:name=\"$it\"" !in manifest }
        assertTrue("receivers missing from AndroidManifest.xml: $missing", missing.isEmpty())
    }
}
