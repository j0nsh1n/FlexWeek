use flexweek_engine::desk::update;

#[uniffi::export]
pub fn update_is_newer(candidate: String, installed: String) -> bool {
    update::is_newer(&candidate, &installed)
}

#[uniffi::export]
pub fn update_expected_digest(checksum_text: String, apk_name: String) -> Option<String> {
    update::android_expected_digest(&checksum_text, &apk_name)
}

#[uniffi::export]
pub fn update_due_for_check(enabled: bool, last_checked_ms: Option<i64>, now_ms: i64) -> bool {
    let settings = serde_json::json!({"check": enabled, "last_ms": last_checked_ms.unwrap_or(0)});
    update::due_for_check(&settings, now_ms).unwrap_or(false)
}

#[uniffi::export]
pub fn update_release_from_page(location: String) -> Option<String> {
    update::release_from_page(&location).map(|release| release.to_string())
}

#[uniffi::export]
pub fn update_android_asset_name(version: String) -> Option<String> {
    update::android_asset_name(&version)
}

#[uniffi::export]
pub fn update_android_release(release_json: String, installed: String) -> Option<String> {
    let release = serde_json::from_str(&release_json).ok()?;
    let offer = update::android_available(&release, &installed).ok()??;
    let size = release
        .get("assets")?
        .as_array()?
        .iter()
        .find(|asset| asset["name"].as_str() == Some(offer.asset.as_str()))?
        .get("size")
        .and_then(serde_json::Value::as_i64);
    Some(
        serde_json::json!({
            "version": offer.version,
            "apk_name": offer.asset,
            "apk_url": offer.url,
            "checksum_url": offer.checksum_url,
            "notes": offer.notes,
            "apk_size": size
        })
        .to_string(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ffi_exposes_shared_rules_and_android_release_details() {
        assert!(update_is_newer("1.10.0".into(), "1.9.0".into()));
        assert!(!update_due_for_check(false, None, 24 * 60 * 60 * 1000));
        assert_eq!(
            update_android_asset_name("1.1.0".into()).as_deref(),
            Some("FlexWeek-Android-1.1.0.apk")
        );
        let json = serde_json::json!({
            "tag_name": "v1.1.0",
            "draft": false,
            "prerelease": false,
            "assets": [
                {"name":"FlexWeek-Android-1.1.0.apk", "browser_download_url":"https://github.com/a.apk", "size": 42},
                {"name":"FlexWeek-Android-1.1.0.apk.sha256", "browser_download_url":"https://github.com/a.sha256"}
            ]
        });
        let offer: serde_json::Value = serde_json::from_str(
            &update_android_release(json.to_string(), "1.0.0".into()).unwrap(),
        )
        .unwrap();
        assert_eq!(offer["version"], "1.1.0");
        assert_eq!(offer["apk_size"], 42);
        assert!(
            update_release_from_page(
                "https://github.com/j0nsh1n/FlexWeek/releases/tag/v1.1.0".into()
            )
            .unwrap()
            .contains("FlexWeek-Android-1.1.0.apk.sha256")
        );
    }

    fn android_release(size: Option<i64>) -> String {
        let mut apk = serde_json::json!({
            "name": "FlexWeek-Android-1.1.0.apk",
            "browser_download_url": "https://github.com/a.apk"
        });
        if let Some(size) = size {
            apk["size"] = size.into();
        }
        serde_json::json!({
            "tag_name": "v1.1.0",
            "draft": false,
            "prerelease": false,
            "body": "Month and Day.\nWidgets.",
            "assets": [
                apk,
                {"name":"FlexWeek-Android-1.1.0.apk.sha256", "browser_download_url":"https://github.com/a.sha256"}
            ]
        })
        .to_string()
    }

    #[test]
    fn ffi_offer_carries_both_urls_the_asset_name_and_the_notes() {
        let offer: serde_json::Value = serde_json::from_str(
            &update_android_release(android_release(Some(68_123_456)), "1.0.0".into()).unwrap(),
        )
        .unwrap();
        assert_eq!(offer["apk_name"], "FlexWeek-Android-1.1.0.apk");
        assert_eq!(offer["apk_url"], "https://github.com/a.apk");
        assert_eq!(offer["checksum_url"], "https://github.com/a.sha256");
        assert_eq!(offer["apk_size"], 68_123_456);
        assert_eq!(offer["notes"], "Month and Day.\nWidgets.");
    }

    #[test]
    fn ffi_offer_without_a_size_still_exists_and_the_size_is_null() {
        let offer: serde_json::Value = serde_json::from_str(
            &update_android_release(android_release(None), "1.0.0".into()).unwrap(),
        )
        .unwrap();
        assert_eq!(offer["version"], "1.1.0");
        assert!(offer["apk_size"].is_null());
    }

    #[test]
    fn ffi_offer_is_none_for_the_same_version_and_for_things_that_are_not_releases() {
        assert!(update_android_release(android_release(Some(1)), "1.1.0".into()).is_none());
        assert!(update_android_release(android_release(Some(1)), "1.1".into()).is_none());
        for payload in ["not json", "[]", "{}", "null", ""] {
            assert!(
                update_android_release(payload.into(), "1.0.0".into()).is_none(),
                "{payload:?}"
            );
        }
    }

    #[test]
    fn ffi_release_page_fallback_refuses_other_addresses() {
        assert!(update_release_from_page("https://evil.test/releases/tag/v1.1.0".into()).is_none());
        assert!(
            update_release_from_page(
                "https://github.com/j0nsh1n/FlexWeek/releases/tag/v1.1.0-rc1".into()
            )
            .is_none()
        );
    }

    const DAY_MS: i64 = 24 * 60 * 60 * 1000;

    #[test]
    fn ffi_daily_check_is_due_when_never_checked_and_on() {
        assert!(update_due_for_check(true, None, 1_700_000_000_000));
    }

    #[test]
    fn ffi_daily_check_off_is_never_due() {
        assert!(!update_due_for_check(false, None, 1_700_000_000_000));
        assert!(!update_due_for_check(
            false,
            Some(1_700_000_000_000 - 3 * DAY_MS),
            1_700_000_000_000
        ));
    }

    #[test]
    fn ffi_daily_check_waits_until_a_full_day_has_passed() {
        let now = 1_700_000_000_000;
        assert!(!update_due_for_check(true, Some(now - (DAY_MS - 1)), now));
        assert!(update_due_for_check(true, Some(now - DAY_MS), now));
        assert!(update_due_for_check(true, Some(now - DAY_MS - 1), now));
    }

    #[test]
    fn ffi_daily_check_after_the_clock_moved_back_is_due() {
        let now = 1_700_000_000_000;
        assert!(update_due_for_check(true, Some(now + 3_600_000), now));
    }

    #[test]
    fn ffi_checksum_requires_exact_asset_name_and_hex_digest() {
        let digest = "a".repeat(64);
        assert_eq!(
            update_expected_digest(
                format!("{digest}  FlexWeek-Android-1.1.0.apk"),
                "FlexWeek-Android-1.1.0.apk".into()
            ),
            Some(digest.clone())
        );
        assert_eq!(
            update_expected_digest(
                format!("{digest}  FlexWeek-Android-1.0.0.apk"),
                "FlexWeek-Android-1.1.0.apk".into()
            ),
            None
        );
        assert_eq!(
            update_expected_digest(format!("{digest}\n"), "FlexWeek-Android-1.1.0.apk".into()),
            None
        );
        assert_eq!(
            update_expected_digest(
                format!("{}g  FlexWeek-Android-1.1.0.apk", "a".repeat(63)),
                "FlexWeek-Android-1.1.0.apk".into()
            ),
            None
        );
    }
}
