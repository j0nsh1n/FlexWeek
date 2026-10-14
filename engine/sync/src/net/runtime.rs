//! One tokio runtime for the whole process, so a phone worker that runs a sync every 15 minutes
//! does not build and drop a thread pool each time.

use std::future::Future;
use std::sync::OnceLock;

use tokio::runtime::{Builder, Runtime};

static RUNTIME: OnceLock<Runtime> = OnceLock::new();

pub fn runtime() -> &'static Runtime {
    RUNTIME.get_or_init(|| {
        Builder::new_multi_thread()
            .worker_threads(2)
            .thread_name("fw-sync")
            .enable_all()
            .build()
            .expect("tokio runtime")
    })
}

/// Blocks the calling thread. Must not be called from inside the runtime (tokio panics); callers
/// are Kotlin or Python threads and plain test threads.
pub fn block_on<F: Future>(future: F) -> F::Output {
    runtime().block_on(future)
}
