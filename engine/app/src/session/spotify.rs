//! Playback decisions for the desktop Spotify player. The window performs the requested I/O.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Play {
    Ask,
    OpenApp,
    OpenBrowser,
    Listening,
    Starting,
    Shown,
    Unavailable,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Poll {
    Quiet,
    Ask(String),
    Heard,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Stop {
    Nothing,
    Pause,
    StopKey,
}

struct Listening {
    address: String,
    waited: i64,
    asked_at: Option<i64>,
    late_said: bool,
}

#[derive(Default)]
enum Playback {
    #[default]
    Idle,
    Listening(Listening),
    Started,
    OpenedTrack,
}

#[derive(Default)]
pub struct Player {
    playback: Playback,
}

impl Player {
    /// Choose the first action after the caller has stopped the previous playback.
    pub fn play(address: Option<&str>, reachable: bool, running: bool) -> Play {
        if address.is_none() {
            Play::Unavailable
        } else if reachable && running {
            Play::Ask
        } else {
            Play::OpenApp
        }
    }

    pub fn asked_to_play(&mut self, address: &str) -> Play {
        self.listen(address, Some(0))
    }

    pub fn app_opened(&mut self, address: &str, reachable: bool, opened: bool) -> Play {
        if !opened {
            Play::OpenBrowser
        } else if reachable {
            self.listen(address, None)
        } else if address.starts_with("spotify:track:") {
            self.playback = Playback::OpenedTrack;
            Play::Starting
        } else {
            Play::Shown
        }
    }

    pub fn browser_opened(opened: bool) -> Play {
        if opened {
            Play::Shown
        } else {
            Play::Unavailable
        }
    }

    fn listen(&mut self, address: &str, asked_at: Option<i64>) -> Play {
        self.playback = Playback::Listening(Listening {
            address: address.to_owned(),
            waited: 0,
            asked_at,
            late_said: false,
        });
        Play::Listening
    }

    pub fn tick(&mut self, poll_ms: i64) {
        if let Playback::Listening(state) = &mut self.playback {
            state.waited = state.waited.saturating_add(poll_ms);
        }
    }

    /// A just-opened app gets its first play request before its playback status is read.
    pub fn check_playing(&self) -> bool {
        matches!(&self.playback, Playback::Listening(state) if state.asked_at.is_some())
    }

    pub fn poll(&mut self, running: bool, playing: bool, ask_again_ms: i64) -> Poll {
        let Playback::Listening(state) = &self.playback else {
            return Poll::Quiet;
        };
        if running && playing && state.asked_at.is_some() {
            self.playback = Playback::Started;
            return Poll::Heard;
        }

        if running
            && state
                .asked_at
                .is_none_or(|asked_at| state.waited.saturating_sub(asked_at) >= ask_again_ms)
        {
            Poll::Ask(state.address.clone())
        } else {
            Poll::Quiet
        }
    }

    /// A failed remote call leaves the request and the late signal due on the next poll.
    pub fn finish_poll(&mut self, asked: bool, grace_ms: i64) -> bool {
        let Playback::Listening(state) = &mut self.playback else {
            return false;
        };
        if asked {
            state.asked_at = Some(state.waited);
        }
        if !state.late_said && state.waited >= grace_ms {
            state.late_said = true;
            true
        } else {
            false
        }
    }

    /// Check after delivering `late`, since a signal handler can dismiss or start playback.
    pub fn give_up(&mut self, give_up_ms: i64) -> bool {
        if matches!(&self.playback, Playback::Listening(state) if state.waited >= give_up_ms) {
            self.playback = Playback::Started;
            true
        } else {
            false
        }
    }

    pub fn stop(&self) -> Stop {
        match self.playback {
            Playback::Idle => Stop::Nothing,
            Playback::Listening(_) | Playback::Started => Stop::Pause,
            Playback::OpenedTrack => Stop::StopKey,
        }
    }

    /// Keep the stop action due until the caller has performed it.
    pub fn stopped(&mut self) {
        self.playback = Playback::Idle;
    }
}
