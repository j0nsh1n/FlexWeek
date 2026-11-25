package com.flexweek.app.ui.reminders

import java.net.URLDecoder
import java.net.URLEncoder

/**
 * The form's pre-filled link exactly as the form gives it, made with the sample answers below, the same link
 * the computer uses. Empty means no form yet, and then Settings shows no Report a problem row.
 */
const val FEEDBACK_FORM_LINK =
    "https://docs.google.com/forms/d/e/1FAIpQLSeA3P9-IWlLc44HPzrNT-FnnEL7D-0FZfTzSXxO9nuhWKJ0rQ/viewform" +
        "?usp=pp_url&entry.1113372711=1.4.0&entry.710379005=test"
const val SAMPLE_VERSION = "1.4.0"
const val SAMPLE_DEVICE = "test"

object FeedbackForm {
    fun available(link: String = FEEDBACK_FORM_LINK): Boolean = link.isNotEmpty()

    /** The link with its sample answers replaced by this app's version and this phone. */
    fun url(version: String, device: String, link: String = FEEDBACK_FORM_LINK): String {
        val cut = link.indexOf('?')
        if (cut < 0) return link
        val query = link.substring(cut + 1).split('&').joinToString("&") { pair ->
            val eq = pair.indexOf('=')
            if (eq < 0) return@joinToString pair
            val value = URLDecoder.decode(pair.substring(eq + 1), "UTF-8")
            when (value) {
                SAMPLE_VERSION -> pair.substring(0, eq + 1) + encode(version)
                SAMPLE_DEVICE -> pair.substring(0, eq + 1) + encode(device)
                else -> pair
            }
        }
        return link.substring(0, cut + 1) + query
    }

    /** "Pixel 8, Android 15": the model and the Android version, the two things a bug report needs. */
    fun device(manufacturer: String, model: String, androidRelease: String): String {
        val name = if (model.startsWith(manufacturer, ignoreCase = true)) model else "$manufacturer $model"
        return "${name.trim()}, Android $androidRelease"
    }

    private fun encode(value: String) = URLEncoder.encode(value, "UTF-8").replace("+", "%20")
}
