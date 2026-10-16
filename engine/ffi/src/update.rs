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

    #[test]
    fn ffi_checksum_requires_exact_asset_name_and_hex_digest() {
        let digest = "a".repeat(64);
        assert_eq!(
            update_expected_digest(
                format!("{digest}  FlexWeek-Android-1.1.0.apk"),
                "FlexWeek-Android-1.1.0.apk".into()
            ),
            Some(digest)
        );
    }
}
