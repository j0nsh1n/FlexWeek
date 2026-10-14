//! The text a QR code carries: the pairing code plus LAN address hints. Drawing it is the
//! desktop's job; this module only builds and reads the string.

use std::net::SocketAddr;

use super::NetError;
use super::protocol::normalize_code;

const PREFIX: &str = "flexweek://pair/2?";
const MAX_HINTS: usize = 8;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QrPayload {
    pub code: String,
    pub hints: Vec<SocketAddr>,
}

pub fn build(code: &str, hints: &[SocketAddr]) -> String {
    let mut text = format!("{PREFIX}c={code}");
    if !hints.is_empty() {
        let list: Vec<String> = hints.iter().map(SocketAddr::to_string).collect();
        text.push_str("&a=");
        text.push_str(&list.join(","));
    }
    text
}

pub fn parse(text: &str) -> Result<QrPayload, NetError> {
    let text = text.trim();
    if !text.starts_with(PREFIX)
        && (text.starts_with("flexweek://pair?") || text.starts_with("flexweek://pair/"))
    {
        return Err(NetError::PairVersionMismatch);
    }
    let query = text
        .strip_prefix(PREFIX)
        .ok_or_else(|| NetError::Protocol("this is not a FlexWeek pairing code".into()))?;
    let mut code = None;
    let mut hints = Vec::new();
    for part in query.split('&') {
        match part.split_once('=') {
            Some(("c", value)) => code = Some(normalize_code(value)?),
            Some(("a", value)) => {
                for item in value.split(',').filter(|item| !item.is_empty()) {
                    if hints.len() < MAX_HINTS {
                        hints.push(item.parse::<SocketAddr>().map_err(|_| {
                            NetError::Protocol("a pairing address is not readable".into())
                        })?);
                    }
                }
            }
            _ => {}
        }
    }
    Ok(QrPayload {
        code: code.ok_or(NetError::BadCode)?,
        hints,
    })
}
