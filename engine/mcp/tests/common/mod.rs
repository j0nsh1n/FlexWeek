//! Hand-written newline-delimited JSON-RPC client. It returns `Value` and never
//! panics on a missing field, so a failing test stops at its own assertion.

#![allow(dead_code)]

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{Value, json};

/// `2026-10-21T12:00:00Z`.
pub const NOW_UNIX: i64 = 1_792_584_000;
pub const NOW_ISO: &str = "2026-10-21T12:00:00Z";
/// Keep-me-signed-in lifetime: 30 days.
pub const KEPT_FOR: i64 = 30 * 24 * 60 * 60;

pub struct Server {
    child: Child,
    stdin: ChildStdin,
    lines: std::sync::mpsc::Receiver<String>,
    stdout: Arc<Mutex<Vec<String>>>,
    stderr: Arc<Mutex<String>>,
}

impl Drop for Server {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[allow(dead_code)]
impl Server {
    pub fn spawn(args: &[&str]) -> Self {
        // The test process inherits this desktop's sockets. Mark them close-on-exec
        // so the child only shows descriptors it opened itself.
        cloexec_above_stdio();
        let mut child = Command::new(env!("CARGO_BIN_EXE_flexweek-mcp"))
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("flexweek-mcp starts");
        let stdin = child.stdin.take().expect("stdin");
        let stdout = child.stdout.take().expect("stdout");
        let stderr = child.stderr.take().expect("stderr");
        let (tx, lines) = std::sync::mpsc::channel();
        let stdout_lines = Arc::new(Mutex::new(Vec::new()));
        let held_out = stdout_lines.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                let Ok(line) = line else { break };
                held_out.lock().expect("stdout").push(line.clone());
                if tx.send(line).is_err() {
                    break;
                }
            }
        });
        let stderr_text = Arc::new(Mutex::new(String::new()));
        let held = stderr_text.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                let Ok(line) = line else { break };
                let mut guard = held.lock().expect("stderr");
                guard.push_str(&line);
                guard.push('\n');
            }
        });
        Self {
            child,
            stdin,
            lines,
            stdout: stdout_lines,
            stderr: stderr_text,
        }
    }

    pub fn pid(&self) -> u32 {
        self.child.id()
    }

    pub fn stderr(&self) -> String {
        self.stderr.lock().expect("stderr").clone()
    }

    pub fn stdout_lines(&self) -> Vec<String> {
        self.stdout.lock().expect("stdout").clone()
    }

    pub fn request(&mut self, method: &str, params: Value, id: i64) -> Value {
        let message = json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params});
        self.send(&message);
        self.response_with_id(id)
    }

    pub fn notify(&mut self, method: &str) {
        self.send(&json!({"jsonrpc": "2.0", "method": method}));
    }

    pub fn handshake(&mut self) -> Value {
        let response = self.request(
            "initialize",
            json!({
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "flexweek-test", "version": "0"}
            }),
            1,
        );
        self.notify("notifications/initialized");
        response
    }

    pub fn call(&mut self, name: &str, arguments: Value, id: i64) -> Value {
        self.request(
            "tools/call",
            json!({"name": name, "arguments": arguments}),
            id,
        )
    }

    fn send(&mut self, message: &Value) {
        let line = match serde_json::to_string(message) {
            Ok(line) => line,
            Err(_) => return,
        };
        let _ = writeln!(self.stdin, "{line}");
        let _ = self.stdin.flush();
    }

    fn response_with_id(&self, id: i64) -> Value {
        let deadline = std::time::Instant::now() + Duration::from_secs(8);
        while std::time::Instant::now() < deadline {
            let remaining = deadline.saturating_duration_since(std::time::Instant::now());
            let Ok(line) = self.lines.recv_timeout(remaining) else {
                return Value::Null;
            };
            let Ok(value) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            if value.get("id").and_then(Value::as_i64) == Some(id) {
                return value;
            }
        }
        Value::Null
    }
}

fn cloexec_above_stdio() {
    unsafe extern "C" {
        safe fn fcntl(fd: i32, cmd: i32, ...) -> i32;
    }
    const F_GETFD: i32 = 1;
    const F_SETFD: i32 = 2;
    const FD_CLOEXEC: i32 = 1;
    let Ok(entries) = std::fs::read_dir("/proc/self/fd") else {
        return;
    };
    let fds: Vec<i32> = entries
        .flatten()
        .filter_map(|entry| entry.file_name().to_str()?.parse().ok())
        .filter(|fd| *fd > 2)
        .collect();
    for fd in fds {
        let flags = fcntl(fd, F_GETFD);
        if flags >= 0 {
            fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
        }
    }
}

pub fn scratch(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../target/mcp-tests")
        .join(format!("{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("scratch dir");
    dir
}

/// The desktop's instance file: `flexweek-` plus the first 16 hex of sha256(database path).
pub fn session_path(data_dir: &str, database: &str) -> PathBuf {
    let hash = flexweek_store::digest(database);
    let instance = format!("flexweek-{}", &hash[..16]);
    PathBuf::from(data_dir)
        .join("signed-in")
        .join(format!("{instance}.json"))
}

pub fn tool_names(response: &Value) -> Vec<String> {
    response
        .get("result")
        .and_then(|result| result.get("tools"))
        .and_then(Value::as_array)
        .map(|tools| {
            tools
                .iter()
                .filter_map(|tool| tool.get("name").and_then(Value::as_str).map(str::to_string))
                .collect()
        })
        .unwrap_or_default()
}

pub fn tool_ok_text(response: &Value) -> Option<&str> {
    let result = response.get("result")?;
    if result.get("isError").and_then(Value::as_bool) == Some(true) {
        return None;
    }
    result
        .get("content")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .and_then(|item| item.get("text"))
        .and_then(Value::as_str)
}

pub fn tool_error_text(response: &Value) -> Option<&str> {
    let result = response.get("result")?;
    if result.get("isError").and_then(Value::as_bool) != Some(true) {
        return None;
    }
    result
        .get("content")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .and_then(|item| item.get("text"))
        .and_then(Value::as_str)
}

/// Arguments every current tool accepts, so a refusal comes from the session.
pub fn read_arguments(name: &str) -> Value {
    match name {
        "get_week" | "list_homework" => json!({"week_start": "2026-10-19"}),
        "get_month" => json!({"month": "2026-10"}),
        "add_homework" => json!({
            "operation_id": "session-check",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        "edit_homework" | "delete_homework" => json!({
            "operation_id": "session-check",
            "id": "essay",
            "expected_revision": 0
        }),
        "set_homework_done" => json!({
            "operation_id": "session-check",
            "id": "essay",
            "done": true
        }),
        "set_block_done" => json!({
            "operation_id": "session-check",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 0,
            "done": true
        }),
        "move_block" => json!({
            "operation_id": "session-check",
            "week_start": "2026-10-19",
            "expected_revision": 0,
            "block_id": "club",
            "day": 2,
            "start": "17:00",
            "end": "18:00"
        }),
        "delete_block" => json!({
            "operation_id": "session-check",
            "week_start": "2026-10-19",
            "expected_revision": 0,
            "block_id": "club",
            "scope": "series"
        }),
        _ => json!({}),
    }
}
