//! The Driver a screen test steps the app with (2.0.0 plan, tests.md section 3), and the first thing behind it:
//! the Python app's test door (desktop/tests/door.py). A screen test written here runs first against the app
//! that is known to work; when the window moves to Rust, the same test runs against the new host.
//!
//! The door is started per test: `python -m desktop.tests.door_app` opens the signed-in test account on the
//! week of Monday 2 November 2026 (the shared fake clock, Thursday 19:00) and answers one JSON step per line on
//! a local socket file. It needs the project's Python environment: `FLEXWEEK_DOOR_PYTHON`, or `.venv/bin/python`
//! at the repository root.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use serde_json::{Value, json};

/// What a step names: an item's test id (its objectName), or the words a student reads on it, the latter
/// optionally looked for only inside the item with a given test id.
#[derive(Clone, Debug)]
pub enum Target {
    Name(String),
    Words(String),
    WordsWithin(String, String),
}

/// The item whose test id is `id`.
pub fn named(id: &str) -> Target {
    Target::Name(id.to_string())
}

/// The visible item showing exactly `words`.
pub fn reading(words: &str) -> Target {
    Target::Words(words.to_string())
}

/// The visible item showing exactly `words` inside the item whose test id is `id`.
pub fn reading_within(words: &str, id: &str) -> Target {
    Target::WordsWithin(words.to_string(), id.to_string())
}

impl Target {
    fn to_json(&self) -> Value {
        match self {
            Self::Name(id) => json!({ "name": id }),
            Self::Words(words) => json!({ "words": words }),
            Self::WordsWithin(words, id) => json!({ "words": words, "within": id }),
        }
    }
}

/// What a student could tell about one item.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Seen {
    pub found: bool,
    pub name: String,
    pub text: String,
    pub enabled: bool,
    pub focused: bool,
    pub visible: bool,
}

/// The steps of a screen test, as the rig's play steps (docs/tooling/fwtest.md) are function calls.
pub trait Driver {
    fn click(&mut self, target: &Target);
    /// A key by its Qt name without "Key_": "Return", "Escape", "Down", "Tab".
    fn key(&mut self, key: &str);
    fn type_text(&mut self, text: &str);
    /// Give an item the keyboard, where a test starts keys from (not a student's step).
    fn focus(&mut self, target: &Target);
    fn read(&mut self, target: &Target) -> Seen;
    /// One property of an item, for what the screen holds but does not print (a picker being open).
    fn property(&mut self, target: &Target, name: &str) -> Value;
    /// Let the app run `turns` turns of its event loop; time moves only when a test moves it.
    fn pump(&mut self, turns: u32);
    /// The session's state the window was built from: week_start, selected_month, screen.
    fn app(&mut self) -> Value;

    /// Run the app until `holds` is true, or fail naming `what`. No sleeps: the app runs its queued work.
    fn wait_until(&mut self, what: &str, mut holds: impl FnMut(&mut Self) -> bool)
    where
        Self: Sized,
    {
        for _ in 0..200 {
            if holds(self) {
                return;
            }
            self.pump(5);
        }
        panic!("waited for {what}");
    }
}

/// The repository root, from this crate's place in it (engine/testkit).
fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("engine/testkit sits two folders below the repository root")
        .to_path_buf()
}

/// How long one step may take before the test fails instead of waiting forever.
const STEP_LIMIT: Duration = Duration::from_secs(60);

/// Doors started by this test binary, so two with the same name never share a folder.
static STARTED: AtomicUsize = AtomicUsize::new(0);

/// The app's process and its folder: stopped and removed when dropped, on every path, a failed start too.
struct App {
    child: Child,
    folder: PathBuf,
}

impl Drop for App {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_dir_all(&self.folder);
    }
}

/// The Python app, started for one test and stopped when the test ends.
pub struct Door {
    stream: BufReader<UnixStream>,
    // Dropped after the stream, so the app is stopped last.
    _app: App,
}

impl Door {
    /// Starts the app on the test account; `name` says which test it is for in the folder's name.
    pub fn start(name: &str) -> Self {
        let root = repository();
        let python = std::env::var_os("FLEXWEEK_DOOR_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join(".venv/bin/python"));
        let number = STARTED.fetch_add(1, Ordering::Relaxed);
        let folder = std::env::temp_dir().join(format!(
            "flexweek-door-{name}-{}-{number}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&folder);
        let home = folder.join("home");
        std::fs::create_dir_all(&home).expect("door folder");
        let socket = folder.join("door.sock");
        let child = Command::new(&python)
            .args(["-m", "desktop.tests.door_app", "--door"])
            .arg(&socket)
            .arg("--folder")
            .arg(&folder)
            .current_dir(&root)
            // Its own home, so Qt's test paths (look and week-start files) are this test's alone.
            .env("HOME", &home)
            .env_remove("XDG_CONFIG_HOME")
            .env_remove("XDG_DATA_HOME")
            .env("QT_QPA_PLATFORM", "offscreen")
            .env("FLEXWEEK_SILENT", "1")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap_or_else(|error| panic!("starting {}: {error}", python.display()));
        let mut app = App { child, folder };
        let stdout: ChildStdout = app.child.stdout.take().expect("the app's output");
        let mut output = BufReader::new(stdout);
        let mut said = Vec::new();
        loop {
            let mut line = String::new();
            let read = output.read_line(&mut line).expect("the app's output");
            if read == 0 {
                panic!("the app ended before opening its door; it said: {said:?}");
            }
            if line.trim() == "door ready" {
                break;
            }
            said.push(line);
        }
        // Anything the app prints later is read and dropped, so a full pipe never stops it.
        std::thread::spawn(move || std::io::copy(&mut output, &mut std::io::sink()));
        let stream = UnixStream::connect(&socket).expect("connect to the door");
        stream
            .set_read_timeout(Some(STEP_LIMIT))
            .expect("a read limit");
        stream
            .set_write_timeout(Some(STEP_LIMIT))
            .expect("a write limit");
        Self {
            stream: BufReader::new(stream),
            _app: app,
        }
    }

    fn step(&mut self, step: Value) -> Value {
        let answer = self.ask(&step);
        assert_eq!(answer["ok"], true, "the step {step} was refused: {answer}");
        answer
    }

    /// The folder this app keeps its account, socket and home in.
    pub fn folder(&self) -> &Path {
        &self._app.folder
    }

    /// One step as raw JSON, and the door's answer whatever it is (for the door's own tests).
    pub fn ask(&mut self, step: &Value) -> Value {
        let mut line = step.to_string();
        line.push('\n');
        self.stream
            .get_mut()
            .write_all(line.as_bytes())
            .expect("send a step");
        let mut answer = String::new();
        self.stream
            .read_line(&mut answer)
            .unwrap_or_else(|error| panic!("no answer to {step} within the limit: {error}"));
        serde_json::from_str(&answer).expect("the door answers JSON")
    }
}

impl Driver for Door {
    fn click(&mut self, target: &Target) {
        self.step(json!({ "step": "click", "target": target.to_json() }));
    }

    fn key(&mut self, key: &str) {
        self.step(json!({ "step": "key", "key": key }));
    }

    fn type_text(&mut self, text: &str) {
        self.step(json!({ "step": "type", "text": text }));
    }

    fn focus(&mut self, target: &Target) {
        self.step(json!({ "step": "focus", "target": target.to_json() }));
    }

    fn read(&mut self, target: &Target) -> Seen {
        let seen = self.step(json!({ "step": "read", "target": target.to_json() }));
        let text = |field: &str| seen[field].as_str().unwrap_or_default().to_string();
        let flag = |field: &str| seen[field].as_bool().unwrap_or(false);
        Seen {
            found: flag("found"),
            name: text("name"),
            text: text("text"),
            enabled: flag("enabled"),
            focused: flag("focused"),
            visible: flag("visible"),
        }
    }

    fn property(&mut self, target: &Target, name: &str) -> Value {
        let answer =
            self.step(json!({ "step": "property", "target": target.to_json(), "name": name }));
        answer["value"].clone()
    }

    fn pump(&mut self, turns: u32) {
        self.step(json!({ "step": "pump", "turns": turns }));
    }

    fn app(&mut self) -> Value {
        let mut answer = self.step(json!({ "step": "app" }));
        if let Value::Object(fields) = &mut answer {
            fields.shift_remove("ok");
        }
        answer
    }
}
