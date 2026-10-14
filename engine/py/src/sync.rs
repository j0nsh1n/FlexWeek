//! The device sync service, as `flexweek_engine.SyncService`. The rules and the network live in
//! `flexweek-sync`; this file converts arguments, results and errors. Every call that can block
//! releases the GIL, so the desktop may call it from a worker thread.

use std::net::SocketAddr;
use std::path::Path;
use std::time::Duration;

use flexweek_sync::Peer;
use flexweek_sync::net::{
    NetError, NodeConfig, PairOffer, PairStatus, PairedHost, SyncService, SyncStatus, SyncSummary,
    Transport,
};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

use crate::guard;

pyo3::create_exception!(
    flexweek_engine,
    SyncError,
    pyo3::exceptions::PyException,
    "A sync call failed. `kind` is a stable word (`unreachable`, `not_paired`, `wrong_code`, ...)."
);

/// The Python error for a sync failure: the message as the text, and `kind` as an attribute.
fn raise(py: Python<'_>, error: NetError) -> PyErr {
    let kind = error.kind();
    match py.get_type::<SyncError>().call1((error.to_string(),)) {
        Ok(instance) => match instance.setattr("kind", kind) {
            Ok(()) => PyErr::from_value(instance),
            Err(problem) => problem,
        },
        Err(problem) => problem,
    }
}

fn to_py<T>(py: Python<'_>, result: Result<T, NetError>) -> PyResult<T> {
    result.map_err(|error| raise(py, error))
}

fn socket(text: &str) -> PyResult<SocketAddr> {
    text.parse()
        .map_err(|_| pyo3::exceptions::PyValueError::new_err(format!("not an address: {text}")))
}

fn sockets(texts: &[String]) -> PyResult<Vec<SocketAddr>> {
    texts.iter().map(|text| socket(text)).collect()
}

fn summary_dict<'py>(py: Python<'py>, summary: &SyncSummary) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("sent", summary.sent)?;
    dict.set_item("received", summary.received)?;
    dict.set_item("applied", summary.applied)?;
    dict.set_item("quarantined", summary.quarantined)?;
    dict.set_item("clock_skewed", summary.clock_skewed)?;
    dict.set_item("exchanges", summary.exchanges)?;
    Ok(dict)
}

fn peer_dict<'py>(py: Python<'py>, peer: &Peer) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("device_id", &peer.device_id)?;
    dict.set_item("endpoint_id", &peer.endpoint_id)?;
    dict.set_item("name", &peer.name)?;
    dict.set_item("paired_at", &peer.paired_at)?;
    dict.set_item("last_seen", peer.last_seen.as_deref())?;
    dict.set_item("revoked", peer.revoked)?;
    Ok(dict)
}

fn pair_status_dict<'py>(py: Python<'py>, status: &PairStatus) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("state", pair_state(status))?;
    dict.set_item("expires_at_ms", None::<i64>)?;
    dict.set_item("tries_left", None::<u32>)?;
    dict.set_item("peer", py.None())?;
    match status {
        PairStatus::Waiting {
            expires_at_ms,
            tries_left,
        } => {
            dict.set_item("expires_at_ms", *expires_at_ms)?;
            dict.set_item("tries_left", *tries_left)?;
        }
        PairStatus::Paired(peer) => {
            let made = PyDict::new(py);
            made.set_item("user_id", peer.user_id)?;
            made.set_item("device_id", &peer.device_id)?;
            made.set_item("device_name", &peer.device_name)?;
            made.set_item("endpoint_id", &peer.endpoint_id)?;
            dict.set_item("peer", made)?;
        }
        PairStatus::Idle | PairStatus::Expired | PairStatus::TooManyTries => {}
    }
    Ok(dict)
}

fn pair_state(status: &PairStatus) -> &'static str {
    match status {
        PairStatus::Idle => "idle",
        PairStatus::Waiting { .. } => "waiting",
        PairStatus::Paired(_) => "paired",
        PairStatus::Expired => "expired",
        PairStatus::TooManyTries => "too_many_tries",
    }
}

fn offer_dict<'py>(py: Python<'py>, offer: &PairOffer) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("code", &offer.code)?;
    dict.set_item("display_code", &offer.display_code)?;
    dict.set_item("qr", &offer.qr)?;
    dict.set_item("expires_at_ms", offer.expires_at_ms)?;
    Ok(dict)
}

fn host_dict<'py>(py: Python<'py>, host: &PairedHost) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("user_id", host.user_id)?;
    dict.set_item("account_uuid", &host.account_uuid)?;
    dict.set_item("username", &host.username)?;
    dict.set_item("host_device_id", &host.host_device_id)?;
    dict.set_item("host_name", &host.host_name)?;
    dict.set_item("host_endpoint_id", &host.host_endpoint_id)?;
    Ok(dict)
}

fn status_dict<'py>(py: Python<'py>, status: &SyncStatus) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("device_id", &status.device_id)?;
    dict.set_item("listening", status.listening)?;
    dict.set_item("syncing", status.syncing)?;
    dict.set_item("last_sync_ms", status.last_sync_ms)?;
    dict.set_item("last_error", status.last_error.as_deref())?;
    dict.set_item("generation", status.generation)?;
    dict.set_item("pairing", pair_status_dict(py, &status.pairing)?)?;
    Ok(dict)
}

#[pyclass(name = "SyncService", module = "flexweek_engine")]
pub struct PySyncService {
    inner: SyncService,
}

#[pymethods]
impl PySyncService {
    /// Opens this device's key, its endpoint and its listener. `scan_ms` is how often edits made by
    /// other connections to the same database are picked up; the desktop passes 1000.
    #[staticmethod]
    #[pyo3(signature = (db_path, key_path, device_name, lan_only=false, bind=None, scan_ms=None))]
    fn start(
        py: Python<'_>,
        db_path: &str,
        key_path: &str,
        device_name: &str,
        lan_only: bool,
        bind: Option<&str>,
        scan_ms: Option<u64>,
    ) -> PyResult<Self> {
        guard(|| {
            let transport = if lan_only {
                let bind = bind.map(socket).transpose()?;
                Transport::LanOnly { bind }
            } else {
                Transport::Auto
            };
            let mut cfg = NodeConfig::new(
                Path::new(db_path),
                Path::new(key_path),
                device_name,
                transport,
            );
            cfg.scan_interval = scan_ms.map(Duration::from_millis);
            let inner = py.detach(|| SyncService::start(cfg));
            Ok(Self {
                inner: to_py(py, inner)?,
            })
        })
    }

    fn device_id(&self) -> PyResult<String> {
        guard(|| Ok(self.inner.device_id().to_string()))
    }

    fn stop(&self, py: Python<'_>) -> PyResult<()> {
        guard(|| {
            py.detach(|| self.inner.stop());
            Ok(())
        })
    }

    fn sync_once<'py>(
        &self,
        py: Python<'py>,
        peer_device_id: &str,
        deadline_ms: u64,
    ) -> PyResult<Bound<'py, PyDict>> {
        guard(|| {
            let result = py.detach(|| self.inner.sync_once(peer_device_id, deadline_ms));
            summary_dict(py, &to_py(py, result)?)
        })
    }

    /// One tuple per paired device: (device_id, summary or None, error kind or None).
    fn sync_all<'py>(&self, py: Python<'py>, deadline_ms: u64) -> PyResult<Bound<'py, PyList>> {
        guard(|| {
            let result = py.detach(|| self.inner.sync_all(deadline_ms));
            let rows = PyList::empty(py);
            for (device_id, outcome) in to_py(py, result)? {
                let row = match outcome {
                    Ok(summary) => PyTuple::new(
                        py,
                        [
                            device_id.into_pyobject(py)?.into_any(),
                            summary_dict(py, &summary)?.into_any(),
                            py.None().into_bound(py),
                        ],
                    )?,
                    Err(error) => PyTuple::new(
                        py,
                        [
                            device_id.into_pyobject(py)?.into_any(),
                            py.None().into_bound(py),
                            error.kind().into_pyobject(py)?.into_any(),
                        ],
                    )?,
                };
                rows.append(row)?;
            }
            Ok(rows)
        })
    }

    fn cancel_sync(&self, py: Python<'_>) -> PyResult<()> {
        guard(|| {
            py.detach(|| self.inner.cancel_sync());
            Ok(())
        })
    }

    fn status<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        guard(|| status_dict(py, &self.inner.status()))
    }

    fn generation(&self) -> PyResult<u64> {
        guard(|| Ok(self.inner.generation()))
    }

    fn local_addrs(&self, py: Python<'_>) -> PyResult<Vec<String>> {
        guard(|| {
            let addrs = py.detach(|| self.inner.local_addrs());
            Ok(addrs.iter().map(SocketAddr::to_string).collect())
        })
    }

    fn set_peer_addrs(&self, endpoint_id: &str, addrs: Vec<String>) -> PyResult<()> {
        guard(|| {
            let parsed = sockets(&addrs)?;
            self.inner.set_peer_addrs(endpoint_id, &parsed);
            Ok(())
        })
    }

    fn peers<'py>(&self, py: Python<'py>, user_id: i64) -> PyResult<Bound<'py, PyList>> {
        guard(|| {
            let peers = to_py(py, self.inner.peers(user_id))?;
            let rows = PyList::empty(py);
            for peer in &peers {
                rows.append(peer_dict(py, peer)?)?;
            }
            Ok(rows)
        })
    }

    fn pair_start<'py>(&self, py: Python<'py>, user_id: i64) -> PyResult<Bound<'py, PyDict>> {
        guard(|| {
            let offer = py.detach(|| self.inner.pair_start(user_id));
            offer_dict(py, &to_py(py, offer)?)
        })
    }

    fn pair_status<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        guard(|| pair_status_dict(py, &self.inner.pair_status()))
    }

    fn pair_cancel(&self, py: Python<'_>) -> PyResult<()> {
        guard(|| {
            py.detach(|| self.inner.pair_cancel());
            Ok(())
        })
    }

    fn pair_with_code<'py>(
        &self,
        py: Python<'py>,
        code: &str,
        hints: Vec<String>,
        deadline_ms: u64,
    ) -> PyResult<Bound<'py, PyDict>> {
        guard(|| {
            let parsed = sockets(&hints)?;
            let host = py.detach(|| self.inner.pair_with_code(code, &parsed, deadline_ms));
            host_dict(py, &to_py(py, host)?)
        })
    }

    fn pair_from_qr<'py>(
        &self,
        py: Python<'py>,
        text: &str,
        deadline_ms: u64,
    ) -> PyResult<Bound<'py, PyDict>> {
        guard(|| {
            let host = py.detach(|| self.inner.pair_from_qr(text, deadline_ms));
            host_dict(py, &to_py(py, host)?)
        })
    }

    fn unlink(
        &self,
        py: Python<'_>,
        user_id: i64,
        device_id: &str,
        notify: bool,
    ) -> PyResult<bool> {
        guard(|| {
            let told = py.detach(|| self.inner.unlink(user_id, device_id, notify));
            to_py(py, told)
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PySyncService>()?;
    module.add("SyncError", module.py().get_type::<SyncError>())?;
    Ok(())
}
