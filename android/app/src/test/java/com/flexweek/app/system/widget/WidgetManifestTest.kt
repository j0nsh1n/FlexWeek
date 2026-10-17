package com.flexweek.app.system.widget

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

class WidgetManifestTest {
    private val android = "http://schemas.android.com/apk/res/android"

    private fun parse(path: String): Element {
        val file = File(path)
        assertTrue("$path does not exist", file.exists())
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        return factory.newDocumentBuilder().parse(file).documentElement
    }

    private fun receiver(name: String): Element? {
        val list = parse("src/main/AndroidManifest.xml").getElementsByTagName("receiver")
        return (0 until list.length).map { list.item(it) as Element }.firstOrNull { it.getAttributeNS(android, "name") == name }
    }

    @Test fun theProviderHasTheUpdateFilterAndTheInfoMetaData() {
        val provider = receiver(".system.widget.UpNextWidgetProvider")
        assertNotNull("the provider is not declared in the manifest", provider)
        assertEquals("true", provider!!.getAttributeNS(android, "exported"))
        val actions = provider.getElementsByTagName("action")
        val names = (0 until actions.length).map { (actions.item(it) as Element).getAttributeNS(android, "name") }
        assertTrue("the provider needs the update action: $names", "android.appwidget.action.APPWIDGET_UPDATE" in names)
        val meta = provider.getElementsByTagName("meta-data")
        val infos = (0 until meta.length).map { meta.item(it) as Element }
            .filter { it.getAttributeNS(android, "name") == "android.appwidget.provider" }
        assertEquals("the provider needs its info meta-data", 1, infos.size)
        assertEquals("@xml/up_next_widget_info", infos[0].getAttributeNS(android, "resource"))
    }

    @Test fun theInfoFileSetsSizesPeriodResizeAndLayout() {
        val info = parse("src/main/res/xml/up_next_widget_info.xml")
        fun attr(name: String) = info.getAttributeNS(android, name)
        assertEquals("${WidgetSize.ROWS_MIN_WIDTH_DP}dp", attr("minWidth"))
        assertEquals("${WidgetSize.ROWS_MIN_HEIGHT_DP}dp", attr("minHeight"))
        assertTrue("minResizeWidth is missing", attr("minResizeWidth").isNotEmpty())
        assertTrue("minResizeHeight is missing", attr("minResizeHeight").isNotEmpty())
        assertEquals("the platform floor is 30 minutes", (30 * 60 * 1000).toString(), attr("updatePeriodMillis"))
        val resize = attr("resizeMode").split("|")
        assertTrue("resizeMode must allow both axes: $resize", "horizontal" in resize && "vertical" in resize)
        assertEquals("@layout/widget_up_next", attr("initialLayout"))
        assertTrue("the initial layout file is missing", File("src/main/res/layout/widget_up_next.xml").exists())
    }

    @Test fun theTickAndAlarmReceiversAreDeclaredAndNotExported() {
        for (name in listOf(".system.widget.WidgetTickReceiver", ".system.widget.WidgetAlarmReceiver")) {
            val declared = receiver(name)
            assertNotNull("$name is not declared", declared)
            assertEquals("$name must not be exported", "false", declared!!.getAttributeNS(android, "exported"))
        }
    }
}
