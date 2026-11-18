package com.flexweek.app.ui.reminders

import java.net.URLEncoder

/**
 * The online form Settings > Help > Report a problem opens. `{version}` and `{device}` are replaced with the
 * app version and the phone's model and Android version, so the form's two prefilled fields arrive filled in.
 * The form id and the two `entry.` ids below are placeholders until the real form exists.
 */
const val FEEDBACK_FORM_URL =
    "https://docs.google.com/forms/d/e/FORM_ID/viewform?usp=pp_url&entry.VERSION_ID={version}&entry.DEVICE_ID={device}"

object FeedbackForm {
    fun url(version: String, device: String, template: String = FEEDBACK_FORM_URL): String =
        template.replace("{version}", encode(version)).replace("{device}", encode(device))

    /** "Pixel 8, Android 15": the model and the Android version, the two things a bug report needs. */
    fun device(manufacturer: String, model: String, androidRelease: String): String {
        val name = if (model.startsWith(manufacturer, ignoreCase = true)) model else "$manufacturer $model"
        return "${name.trim()}, Android $androidRelease"
    }

    private fun encode(value: String) = URLEncoder.encode(value, "UTF-8").replace("+", "%20")
}
