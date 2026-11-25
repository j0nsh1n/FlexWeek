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
    NameWithin(String, String),
    NameTitled(String, String),
}

/// The item with test id `id` whose title is `title` (the week block "Club").
pub fn titled(id: &str, title: &str) -> Target {
    Target::NameTitled(id.to_string(), title.to_string())
}

/// The week block (on Week or Day) whose title is `title`.
pub fn block(title: &str) -> Target {
    titled("weekBlock", title)
}

/// The item whose test id is `id`.
pub fn named(id: &str) -> Target {
    Target::Name(id.to_string())
}

/// The visible item showing exactly `words`.
pub fn reading(words: &str) -> Target {
    Target::Words(words.to_string())
}

/// The item whose test id is `id` inside the item whose test id is `within` (a field's input in a sheet).
pub fn named_within(id: &str, within: &str) -> Target {
    Target::NameWithin(id.to_string(), within.to_string())
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
            Self::NameWithin(id, within) => json!({ "name": id, "within": within }),
            Self::NameTitled(id, title) => json!({ "name": id, "title": title }),
        }
    }
}

/// What a student could tell about one item.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Seen {
    pub found: bool,
    pub name: String,
    pub text: String,
    /// A block's or a sheet's title, where the item has one.
    pub title: String,
    pub enabled: bool,
    pub focused: bool,
    pub visible: bool,
    pub opacity: f64,
    /// Where it is drawn in the window: left, top, width, height.
    pub rect: Rect,
    /// What a screen reader says for it.
    pub accessible: String,
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Rect {
    pub left: f64,
    pub top: f64,
    pub width: f64,
    pub height: f64,
}

impl Rect {
    pub fn right(&self) -> f64 {
        self.left + self.width
    }

    pub fn bottom(&self) -> f64 {
        self.top + self.height
    }

    pub fn middle_y(&self) -> f64 {
        self.top + self.height / 2.0
    }

    /// Whether the two share any area (touching edges do not count).
    pub fn overlaps(&self, other: &Rect) -> bool {
        !(self.right() <= other.left
            || other.right() <= self.left
            || self.bottom() <= other.top
            || other.bottom() <= self.top)
    }

    /// Grown by `by` on every side.
    pub fn grown(&self, by: f64) -> Rect {
        Rect {
            left: self.left - by,
            top: self.top - by,
            width: self.width + 2.0 * by,
            height: self.height + 2.0 * by,
        }
    }
}

/// The item that has the keyboard.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Focus {
    pub seen: Seen,
    /// The item and the items holding it, outwards: (test id, title).
    pub chain: Vec<(String, String)>,
    /// Its focus ring is showing.
    pub ring: bool,
    /// It is wholly inside the scroller holding it, or inside the window.
    pub in_view: bool,
}

impl Focus {
    /// Whether the item with the keyboard is, or sits inside, the item with test id `id`.
    pub fn inside(&self, id: &str) -> bool {
        self.chain.iter().any(|(name, _)| name == id)
    }

    /// The title of the nearest item with test id `id` holding the keyboard, if any.
    pub fn title_of(&self, id: &str) -> Option<&str> {
        self.chain
            .iter()
            .find(|(name, _)| name == id)
            .map(|(_, title)| title.as_str())
    }

    /// The chain's test ids, for a failure message.
    pub fn path(&self) -> String {
        let names: Vec<&str> = self
            .chain
            .iter()
            .take(4)
            .map(|(name, _)| name.as_str())
            .collect();
        if names.is_empty() {
            "nothing".to_string()
        } else {
            names.join(" < ")
        }
    }
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
    /// Every item with that test id or those words, shown or not, in drawing order.
    fn read_all(&mut self, target: &Target) -> Vec<Seen>;
    /// The item with the keyboard.
    fn focused(&mut self) -> Focus;
    /// Press at the middle of an item, moved by `at`, move by `by` and let go, as the pointer does it.
    fn drag(&mut self, target: &Target, at: (i32, i32), by: (i32, i32));
    /// The mouse wheel over an item: `notches` up (positive) or down, with `held` ("ctrl", "" for none).
    fn wheel(&mut self, target: &Target, notches: i32, held: &str);
    /// Let the app run `turns` turns of its event loop; time moves only when a test moves it.
    fn pump(&mut self, turns: u32);
    /// The session's state the window was built from: week_start, selected_month, screen, busy, dirty,
    /// snack (the notice's words), sheet (the open sheet's kind), window_has_keyboard, blocks and homework.
    fn app(&mut self) -> Value;

    // Setting up (not a student's steps; the Rust core's seeds and fake clock stand in for these later).

    /// "material_week": School Monday to Friday 08:00-14:30, the History essay planned for Thursday 18:45,
    /// weekends shown, the 24-hour clock, the clock at Thursday 19:00.
    fn seed(&mut self, name: &str);
    /// Homework added and saved.
    fn homework(&mut self, id: &str, title: &str, minutes: u32, due: &str);
    /// A block added (or replaced, by id) and saved.
    fn block(&mut self, block: Value);
    /// The fake clock held at `at` (ISO local time), and the window's clock tick run.
    fn clock(&mut self, at: &str);
    /// Preferences changed as Settings would change them.
    fn preferences(&mut self, values: Value);
    /// The Day screen on `day` (ISO date).
    fn open_day(&mut self, day: &str);
    /// One property of an item set (a scroller's contentY).
    fn set_property(&mut self, target: &Target, name: &str, value: Value);
    /// The scroller holding the item scrolled so it shows with room around it (a drag must start on screen).
    fn reveal(&mut self, target: &Target);

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
    socket: PathBuf,
}

impl Drop for App {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_dir_all(&self.folder);
        let _ = std::fs::remove_file(&self.socket);
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
        // A socket file's path is limited to about 100 bytes, so a long test name is cut.
        let name: String = name.chars().take(32).collect();
        let folder = std::env::temp_dir().join(format!(
            "flexweek-door-{name}-{}-{number}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&folder);
        let home = folder.join("home");
        std::fs::create_dir_all(&home).expect("door folder");
        // A socket file's whole path must stay under about 100 bytes; a long temporary folder (a sandbox's)
        // would leave none, so then the socket goes straight in /tmp.
        let socket = match folder.join("door.sock") {
            socket if socket.as_os_str().len() <= 96 => socket,
            _ => PathBuf::from(format!("/tmp/fw-door-{}-{number}.sock", std::process::id())),
        };
        // The real font and QML caches, so each door does not build them again in its own home.
        let cache = std::env::var_os("XDG_CACHE_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".cache")));
        let mut command = Command::new(&python);
        if let Some(cache) = cache {
            command.env("XDG_CACHE_HOME", cache);
        }
        let child = command
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
        let mut app = App {
            child,
            folder,
            socket: socket.clone(),
        };
        let stdout: ChildStdout = app.child.stdout.take().expect("the app's output");
        // Its output is read on a thread: the first "door ready" is passed back, and anything later is read
        // and dropped, so a full pipe never stops the app. A start that takes too long fails the test.
        let (ready, started) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let mut output = BufReader::new(stdout);
            let mut said = Vec::new();
            loop {
                let mut line = String::new();
                match output.read_line(&mut line) {
                    Ok(0) | Err(_) => {
                        let _ = ready.send(Err(said));
                        return;
                    }
                    Ok(_) if line.trim() == "door ready" => break,
                    Ok(_) => said.push(line),
                }
            }
            let _ = ready.send(Ok(()));
            let _ = std::io::copy(&mut output, &mut std::io::sink());
        });
        match started.recv_timeout(STEP_LIMIT) {
            Ok(Ok(())) => {}
            Ok(Err(said)) => panic!("the app ended before opening its door; it said: {said:?}"),
            Err(_) => panic!("the app did not open its door within {STEP_LIMIT:?}"),
        }
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
        seen_from(&seen)
    }

    fn read_all(&mut self, target: &Target) -> Vec<Seen> {
        let answer = self.step(json!({ "step": "read_all", "target": target.to_json() }));
        answer["items"]
            .as_array()
            .map(|items| items.iter().map(seen_from).collect())
            .unwrap_or_default()
    }

    fn focused(&mut self) -> Focus {
        let answer = self.step(json!({ "step": "focused" }));
        let chain = answer["chain"]
            .as_array()
            .map(|chain| {
                chain
                    .iter()
                    .map(|link| {
                        (
                            link["name"].as_str().unwrap_or_default().to_string(),
                            link["title"].as_str().unwrap_or_default().to_string(),
                        )
                    })
                    .collect()
            })
            .unwrap_or_default();
        Focus {
            seen: seen_from(&answer),
            chain,
            ring: answer["ring"].as_bool().unwrap_or(false),
            in_view: answer["in_view"].as_bool().unwrap_or(false),
        }
    }

    fn drag(&mut self, target: &Target, at: (i32, i32), by: (i32, i32)) {
        self.step(json!({
            "step": "drag", "target": target.to_json(), "at": [at.0, at.1], "by": [by.0, by.1]
        }));
    }

    fn wheel(&mut self, target: &Target, notches: i32, held: &str) {
        self.step(
            json!({ "step": "wheel", "target": target.to_json(), "dy": notches, "key": held }),
        );
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

    fn seed(&mut self, name: &str) {
        self.step(json!({ "step": "seed", "name": name }));
    }

    fn homework(&mut self, id: &str, title: &str, minutes: u32, due: &str) {
        self.step(json!({
            "step": "homework", "id": id, "title": title, "minutes": minutes, "due": due
        }));
    }

    fn block(&mut self, block: Value) {
        self.step(json!({ "step": "block", "block": block }));
    }

    fn clock(&mut self, at: &str) {
        self.step(json!({ "step": "clock", "at": at }));
    }

    fn preferences(&mut self, values: Value) {
        self.step(json!({ "step": "preferences", "values": values }));
    }

    fn open_day(&mut self, day: &str) {
        self.step(json!({ "step": "open_day", "day": day }));
    }

    fn set_property(&mut self, target: &Target, name: &str, value: Value) {
        self.step(json!({
            "step": "set_property", "target": target.to_json(), "name": name, "value": value
        }));
    }

    fn reveal(&mut self, target: &Target) {
        self.step(json!({ "step": "reveal", "target": target.to_json() }));
    }
}

fn seen_from(seen: &Value) -> Seen {
    let text = |field: &str| seen[field].as_str().unwrap_or_default().to_string();
    let flag = |field: &str| seen[field].as_bool().unwrap_or(false);
    let number = |index: usize| seen["rect"][index].as_f64().unwrap_or(0.0);
    Seen {
        found: flag("found"),
        name: text("name"),
        text: text("text"),
        title: text("title"),
        enabled: flag("enabled"),
        focused: flag("focused"),
        visible: flag("visible"),
        opacity: seen["opacity"].as_f64().unwrap_or(1.0),
        rect: Rect {
            left: number(0),
            top: number(1),
            width: number(2),
            height: number(3),
        },
        accessible: text("accessible"),
    }
}
