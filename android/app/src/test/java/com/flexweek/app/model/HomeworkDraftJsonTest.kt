package com.flexweek.app.model

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class HomeworkDraftJsonTest {
    @Test fun draftSendsOnlyKeysTheCoreReads() {
        val keys = JSONObject(V2Json.homeworkDraftJson(HomeworkDraft(title = "Essay", due = "2026-10-23T23:59"))).keys().asSequence().toSet()
        assertEquals(setOf("title", "due", "estimate_min", "sessions"), keys)
    }
}
