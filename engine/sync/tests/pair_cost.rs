use flexweek_sync::net::protocol::derive_pair_keys;

#[test]
fn production_pairing_uses_the_expensive_cost() {
    // Independent hashlib.scrypt vector with N=32768, r=8, p=32 and 64 output bytes.
    let keys = derive_pair_keys("12345678").unwrap();
    let output = [keys.secret.to_bytes(), keys.proof_key].concat();
    assert_eq!(
        hex::encode(output),
        "5515309570d263c71828544894e110ac6861977e85a98166e9105a0ae585990a9f36f454c67ce319b730c41b575ba8d4f4f6e16cc9d2511072d845db6cf475a7"
    );
}
