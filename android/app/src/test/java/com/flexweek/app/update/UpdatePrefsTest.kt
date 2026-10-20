package com.flexweek.app.update

import android.content.SharedPreferences
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdatePrefsTest {
    @Test fun dailyCheckIsOnByDefaultAndNothingIsRecordedYet() {
        val prefs = SharedPreferenceUpdatePrefs(MemoryPreferences())
        assertTrue(prefs.checkDaily)
        assertNull(prefs.lastChecked)
    }

    @Test fun turningTheDailyCheckOffSurvivesANewInstanceOnTheSameStore() {
        val store = MemoryPreferences()
        SharedPreferenceUpdatePrefs(store).checkDaily = false
        assertFalse(SharedPreferenceUpdatePrefs(store).checkDaily)
        SharedPreferenceUpdatePrefs(store).checkDaily = true
        assertTrue(SharedPreferenceUpdatePrefs(store).checkDaily)
    }

    @Test fun theLastCheckTimeIsRememberedAndCanBeCleared() {
        val store = MemoryPreferences()
        SharedPreferenceUpdatePrefs(store).lastChecked = 1_700_000_000_000L
        assertEquals(1_700_000_000_000L, SharedPreferenceUpdatePrefs(store).lastChecked)
        SharedPreferenceUpdatePrefs(store).lastChecked = null
        assertNull(SharedPreferenceUpdatePrefs(store).lastChecked)
    }

    @Test fun aLastCheckOfZeroIsARealTimeNotMissing() {
        val store = MemoryPreferences()
        SharedPreferenceUpdatePrefs(store).lastChecked = 0L
        assertEquals(0L, SharedPreferenceUpdatePrefs(store).lastChecked)
    }

    private class MemoryPreferences : SharedPreferences {
        val values = mutableMapOf<String, Any?>()
        override fun getAll(): MutableMap<String, *> = values
        override fun getString(key: String?, defValue: String?) = values[key] as? String ?: defValue
        override fun getStringSet(key: String?, defValues: MutableSet<String>?): MutableSet<String>? = defValues
        override fun getInt(key: String?, defValue: Int) = values[key] as? Int ?: defValue
        override fun getLong(key: String?, defValue: Long) = values[key] as? Long ?: defValue
        override fun getFloat(key: String?, defValue: Float) = values[key] as? Float ?: defValue
        override fun getBoolean(key: String?, defValue: Boolean) = values[key] as? Boolean ?: defValue
        override fun contains(key: String?) = values.containsKey(key)
        override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
            val pending = mutableMapOf<String, Any?>()
            val removed = mutableSetOf<String>()
            override fun putString(key: String, value: String?) = apply { pending[key] = value }
            override fun putStringSet(key: String, values: MutableSet<String>?) = apply { pending[key] = values }
            override fun putInt(key: String, value: Int) = apply { pending[key] = value }
            override fun putLong(key: String, value: Long) = apply { pending[key] = value }
            override fun putFloat(key: String, value: Float) = apply { pending[key] = value }
            override fun putBoolean(key: String, value: Boolean) = apply { pending[key] = value }
            override fun remove(key: String) = apply { removed += key }
            override fun clear() = apply { values.clear() }
            override fun commit(): Boolean { apply(); return true }
            override fun apply() { removed.forEach(values::remove); values.putAll(pending) }
        }
        override fun registerOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) = Unit
        override fun unregisterOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) = Unit
    }
}
