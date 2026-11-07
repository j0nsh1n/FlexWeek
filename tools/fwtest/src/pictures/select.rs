//! Which screens a pull request draws: those whose sources its changed paths touch.

use super::index::Listing;

/// Paths every picture is drawn from: the renderer, the contract, the light app, the font setup and
/// the bundled fonts. A change to one draws every screen.
pub const EVERY_SCREEN: &[&str] = &[
    "scripts/pictures",
    "desktop/tests/pictures/screen.py",
    "desktop/tests/light_app.py",
    "desktop/tests/fontconfig.conf",
    "desktop/assets/fonts",
];

/// A changed path touches a source when it is that file or lies in that folder.
pub fn touches(changed: &str, source: &str) -> bool {
    let changed = changed
        .trim()
        .trim_start_matches("./")
        .trim_end_matches('/');
    let source = source.trim().trim_start_matches("./").trim_end_matches('/');
    if changed.is_empty() || source.is_empty() {
        return false;
    }
    changed == source
        || changed
            .strip_prefix(source)
            .is_some_and(|rest| rest.starts_with('/'))
}

/// The ids of the screens to draw, in the registry's order: a screen whose sources or own screens
/// file a changed path touches, or every screen when a changed path is one all pictures use.
pub fn select(listing: &Listing, changed: &[String]) -> Vec<String> {
    let everything = changed
        .iter()
        .any(|path| EVERY_SCREEN.iter().any(|shared| touches(path, shared)));
    listing
        .screens
        .iter()
        .filter(|screen| {
            everything
                || changed.iter().any(|path| {
                    touches(path, &screen.module)
                        || screen.sources.iter().any(|source| touches(path, source))
                })
        })
        .map(|screen| screen.id.clone())
        .collect()
}

/// Changed paths from a file: one per line, blank lines skipped.
pub fn read_changed(text: &str) -> Vec<String> {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(str::to_string)
        .collect()
}
