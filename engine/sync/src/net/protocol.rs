//! Wire constants, the pairing key derivation and the small JSON messages both sides speak.
//!
//! One request and one response travel on one bidirectional stream, each ended by `finish()`, so
//! the messages need no length prefix. The sync stream is never opened for a peer that is not
//! paired: the connection is closed with `CLOSE_NOT_PAIRED` before any stream is accepted.

use hmac::{Hmac, Mac};
use iroh::SecretKey;
use serde_json::{Value, json};
use sha2::Sha256;

use super::NetError;

pub const SYNC_ALPN: &[u8] = b"flexweek/sync/1";
pub const PAIR_ALPN: &[u8] = b"flexweek/pair/1";
pub const PROTO_VERSION: i64 = 1;
pub const PAIR_VERSION: i64 = 2;

pub const CONNECT_TIMEOUT_MS: u64 = 10_000;
pub const SYNC_DEADLINE_MS: u64 = 45_000;
pub const PAIR_EXPIRY_MS: i64 = 5 * 60 * 1000;
pub const PAIR_MAX_TRIES: u32 = 3;
/// Larger than any batch (256 KiB of records plus framing), small enough to stop a hostile peer.
pub const MAX_MESSAGE_BYTES: usize = 2 * 1024 * 1024;
pub const BATCH_LIMIT: usize = 500;

pub const CLOSE_DONE: u32 = 0;
pub const CLOSE_NOT_PAIRED: u32 = 1;
pub const CLOSE_BAD_REQUEST: u32 = 2;

const PAIR_SALT: &[u8] = b"flexweek-pair-v2";
const PROOF_CONTEXT: &[u8] = b"flexweek-pair-v2/hello";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct PairCost {
    log_n: u8,
    r: u32,
    p: u32,
}

const PRODUCTION_PAIR_COST: PairCost = PairCost {
    log_n: 15,
    r: 8,
    p: 32,
};

#[cfg(not(test))]
const PAIR_COST: PairCost = PRODUCTION_PAIR_COST;
#[cfg(test)]
const PAIR_COST: PairCost = PairCost {
    log_n: 4,
    r: 8,
    p: 1,
};

/// What a code stretches into: the pairing endpoint's secret key and a separate key for the proof.
pub struct PairKeys {
    pub secret: SecretKey,
    pub proof_key: [u8; 32],
}

/// Eight digits are only 10^8 guesses, so the code is stretched: a guess made from the public
/// endpoint id costs about a second in an optimised desktop build.
pub fn derive_pair_keys(code: &str) -> Result<PairKeys, NetError> {
    derive_pair_keys_with_cost(code, PAIR_COST)
}

fn derive_pair_keys_with_cost(code: &str, cost: PairCost) -> Result<PairKeys, NetError> {
    let code = normalize_code(code)?;
    let params = scrypt::Params::new(cost.log_n, cost.r, cost.p, 64)
        .map_err(|e| NetError::Protocol(e.to_string()))?;
    let mut out = [0u8; 64];
    scrypt::scrypt(code.as_bytes(), PAIR_SALT, &params, &mut out)
        .map_err(|e| NetError::Protocol(e.to_string()))?;
    let mut secret = [0u8; 32];
    secret.copy_from_slice(&out[..32]);
    let mut proof_key = [0u8; 32];
    proof_key.copy_from_slice(&out[32..]);
    Ok(PairKeys {
        secret: SecretKey::from_bytes(&secret),
        proof_key,
    })
}

/// Accepts "1234 5678", "1234-5678" and "12345678".
pub fn normalize_code(text: &str) -> Result<String, NetError> {
    let digits: String = text
        .chars()
        .filter(|c| !c.is_ascii_whitespace() && *c != '-')
        .collect();
    if digits.len() == 8 && digits.bytes().all(|b| b.is_ascii_digit()) {
        Ok(digits)
    } else {
        Err(NetError::BadCode)
    }
}

pub fn display_code(code: &str) -> String {
    format!("{} {}", &code[..4], &code[4..])
}

fn hello_mac(
    proof_key: &[u8; 32],
    nonce: &[u8],
    endpoint_id: &[u8; 32],
    device_id: &str,
    device_name: &str,
) -> Hmac<Sha256> {
    let mut mac = Hmac::<Sha256>::new_from_slice(proof_key).expect("hmac takes any key length");
    mac.update(PROOF_CONTEXT);
    for part in [
        nonce,
        endpoint_id,
        device_id.as_bytes(),
        device_name.as_bytes(),
    ] {
        mac.update(&(part.len() as u32).to_be_bytes());
        mac.update(part);
    }
    mac
}

pub fn hello_proof(
    proof_key: &[u8; 32],
    nonce: &[u8],
    endpoint_id: &[u8; 32],
    device_id: &str,
    device_name: &str,
) -> Vec<u8> {
    hello_mac(proof_key, nonce, endpoint_id, device_id, device_name)
        .finalize()
        .into_bytes()
        .to_vec()
}

/// Constant-time comparison.
pub fn hello_proof_matches(
    proof_key: &[u8; 32],
    nonce: &[u8],
    endpoint_id: &[u8; 32],
    device_id: &str,
    device_name: &str,
    proof: &[u8],
) -> bool {
    hello_mac(proof_key, nonce, endpoint_id, device_id, device_name)
        .verify_slice(proof)
        .is_ok()
}

pub fn refusal(code: &str, message: &str) -> Value {
    json!({"ok": false, "code": code, "message": message})
}

pub(crate) fn check_pair_version(value: &Value) -> Result<(), NetError> {
    if value.get("proto").and_then(Value::as_i64) == Some(PAIR_VERSION) {
        Ok(())
    } else {
        Err(NetError::PairVersionMismatch)
    }
}

pub fn encode(value: &Value) -> Vec<u8> {
    value.to_string().into_bytes()
}

pub fn decode(bytes: &[u8]) -> Result<Value, NetError> {
    serde_json::from_slice(bytes)
        .map_err(|e| NetError::Protocol(format!("unreadable message: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn old_missing_and_future_pairing_versions_are_refused() {
        for value in [json!({"proto": 1}), json!({}), json!({"proto": 3})] {
            let error = check_pair_version(&value).unwrap_err();
            assert_eq!(error.kind(), "version_mismatch");
            assert_eq!(
                error.to_string(),
                "these devices use different pairing versions; update FlexWeek on both devices"
            );
        }
        check_pair_version(&json!({"proto": 2})).unwrap();
        assert_eq!(PROTO_VERSION, 1);
    }

    #[test]
    #[ignore = "measure the production KDF with --release --ignored --nocapture"]
    fn production_pairing_derivation_time() {
        let start = std::time::Instant::now();
        let keys = derive_pair_keys_with_cost("12345678", PRODUCTION_PAIR_COST).unwrap();
        let elapsed = start.elapsed();
        let bytes = 128
            * PRODUCTION_PAIR_COST.r as usize
            * ((1usize << PRODUCTION_PAIR_COST.log_n) + PRODUCTION_PAIR_COST.p as usize + 1);
        println!("production scrypt: {elapsed:?}; work buffers: {bytes} bytes");
        assert_ne!(keys.secret.to_bytes(), keys.proof_key);
    }
}
