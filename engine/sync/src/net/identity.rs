//! The device's permanent iroh key and its row in `sync_device`.

use std::fs;
use std::io::Write;
use std::path::Path;

use iroh::SecretKey;
use rusqlite::{Connection, OptionalExtension};

use super::NetError;
use crate::{migrate, set_device};

/// Fills `buf` from the operating system's random generator. iroh already depends on it, so this
/// borrows `SecretKey::generate` instead of adding a crate for entropy.
pub fn fill_random(buf: &mut [u8]) {
    for chunk in buf.chunks_mut(32) {
        let bytes = SecretKey::generate().to_bytes();
        chunk.copy_from_slice(&bytes[..chunk.len()]);
    }
}

/// Reads the key at `path`, or makes one with mode 0600. A damaged file is an error, never a new
/// key: a silent new key would change this device's identity and lock out every paired peer.
pub fn load_or_create_key(path: &Path) -> Result<SecretKey, NetError> {
    match fs::read(path) {
        Ok(bytes) => {
            let array: [u8; 32] = bytes
                .try_into()
                .map_err(|_| NetError::Key("the device key file is damaged".into()))?;
            tighten_mode(path)?;
            Ok(SecretKey::from_bytes(&array))
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => create_key(path),
        Err(error) => Err(NetError::Key(error.to_string())),
    }
}

fn create_key(path: &Path) -> Result<SecretKey, NetError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| NetError::Key(e.to_string()))?;
    }
    let key = SecretKey::generate();
    let temp = path.with_extension("tmp");
    let _ = fs::remove_file(&temp);
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&temp)
        .map_err(|e| NetError::Key(e.to_string()))?;
    file.write_all(&key.to_bytes())
        .and_then(|()| file.sync_all())
        .map_err(|e| NetError::Key(e.to_string()))?;
    drop(file);
    fs::rename(&temp, path).map_err(|e| NetError::Key(e.to_string()))?;
    Ok(key)
}

#[cfg(unix)]
fn tighten_mode(path: &Path) -> Result<(), NetError> {
    use std::os::unix::fs::PermissionsExt;
    let mode = fs::metadata(path)
        .map_err(|e| NetError::Key(e.to_string()))?
        .permissions()
        .mode();
    if mode & 0o077 != 0 {
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .map_err(|e| NetError::Key(e.to_string()))?;
    }
    Ok(())
}

#[cfg(not(unix))]
fn tighten_mode(_path: &Path) -> Result<(), NetError> {
    Ok(())
}

/// The device id is the endpoint id, so a database copied to a machine with another key refuses to
/// sync as the original device instead of quietly becoming its twin.
pub fn ensure_device(conn: &Connection, device_id: &str, name: &str) -> Result<(), NetError> {
    migrate(conn)?;
    let current: Option<String> = conn
        .query_row(
            "SELECT device_id FROM sync_device WHERE singleton = 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(crate::SyncError::from)?;
    if current.is_some_and(|current| current != device_id) {
        return Err(NetError::DeviceMismatch);
    }
    set_device(conn, device_id, name)?;
    Ok(())
}
