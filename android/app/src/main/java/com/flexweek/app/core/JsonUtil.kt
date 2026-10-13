package com.flexweek.app.core

import org.json.JSONObject

/** Android's org.json returns void from [JSONObject.put], not a fluent builder. */
internal fun jsonObject(block: JSONObject.() -> Unit): JSONObject = JSONObject().apply(block)

internal fun jsonString(block: JSONObject.() -> Unit): String = jsonObject(block).toString()
