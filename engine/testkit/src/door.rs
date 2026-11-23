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

use serde_json::{Value, json};

/// What a step names: an item's test id (its objectName), or the words a student reads on it.
#[derive(Clone, Debug)]
pub enum Target {
    Name(String),
    Words(String),
}

/// The item whose test id is `id`.
pub fn named(id: &str) -> Target {
    Target::Name(id.to_string())
}

/// The visible item showing exactly `words`.
pub fn reading(words: &str) -> Target {
    Target::Words(words.to_string())
}

impl Target {
    fn to_json(&self) -> Value {
        match self {
            Self::Name(id) => json!({ "name": id }),
            Self::Words(words) => json!({ "words": words }),
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

/// The Python app, started for one test and stopped when the test ends.
pub struct Door {
    child: Child,
    stream: BufReader<UnixStream>,
    folder: PathBuf,
}

impl Door {
    /// Starts the app on the test account; `name` keeps tests running at once apart.
    pub fn start(name: &str) -> Self {
        let root = repository();
        let python = std::env::var_os("FLEXWEEK_DOOR_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join(".venv/bin/python"));
        let folder =
            std::env::temp_dir().join(format!("flexweek-door-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&folder);
        std::fs::create_dir_all(&folder).expect("door folder");
        let socket = folder.join("door.sock");
        let mut child = Command::new(&python)
            .args(["-m", "desktop.tests.door_app", "--door"])
            .arg(&socket)
            .arg("--folder")
            .arg(&folder)
            .current_dir(&root)
            .env("QT_QPA_PLATFORM", "offscreen")
            .env("FLEXWEEK_SILENT", "1")
            .stdout(Stdio::piped())
            .spawn()
            .unwrap_or_else(|error| panic!("starting {}: {error}", python.display()));
        let stdout: ChildStdout = child.stdout.take().expect("the app's output");
        let mut output = BufReader::new(stdout);
        let mut said = String::new();
        output.read_line(&mut said).expect("the app's first line");
        assert_eq!(said.trim(), "door ready", "the app did not open its door");
        // Anything the app prints later is read and dropped, so a full pipe never stops it.
        std::thread::spawn(move || std::io::copy(&mut output, &mut std::io::sink()));
        let stream = UnixStream::connect(&socket).expect("connect to the door");
        Self {
            child,
            stream: BufReader::new(stream),
            folder,
        }
    }

    fn step(&mut self, step: Value) -> Value {
        let mut line = step.to_string();
        line.push('\n');
        self.stream
            .get_mut()
            .write_all(line.as_bytes())
            .expect("send a step");
        let mut answer = String::new();
        self.stream
            .read_line(&mut answer)
            .expect("the door's answer");
        let answer: Value = serde_json::from_str(&answer).expect("the door answers JSON");
        assert_eq!(answer["ok"], true, "the step {step} was refused: {answer}");
        answer
    }
}

impl Drop for Door {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_dir_all(&self.folder);
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
