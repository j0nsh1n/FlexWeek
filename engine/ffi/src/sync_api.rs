pub(crate) trait SyncApi: Send + Sync {
    fn status(&self) -> String;
    fn sync_once(&self, deadline_ms: i64) -> String;
    fn pair_with_code(&self, code: &str) -> String;
    fn pair_from_qr(&self, text: &str) -> String;
    fn cancel_sync(&self) -> String;
    fn unlink(&self) -> String;
    fn join_from_pairing(&self, payload: &str) -> String;
}

pub(crate) struct NotPairedSync;

impl SyncApi for NotPairedSync {
    fn status(&self) -> String {
        "not paired".into()
    }

    fn sync_once(&self, _deadline_ms: i64) -> String {
        "not paired".into()
    }

    fn pair_with_code(&self, _code: &str) -> String {
        "not paired".into()
    }

    fn pair_from_qr(&self, _text: &str) -> String {
        "not paired".into()
    }

    fn cancel_sync(&self) -> String {
        "not paired".into()
    }

    fn unlink(&self) -> String {
        "not paired".into()
    }

    fn join_from_pairing(&self, _payload: &str) -> String {
        "not paired".into()
    }
}
