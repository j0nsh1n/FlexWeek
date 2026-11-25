//! The playback state kept by `desktop.native.spotify.SpotifyPlayer`.

use flexweek_app::session::spotify::{Play, Player, Poll, Stop};
use pyo3::prelude::*;

use crate::guard;

fn play_name(play: Play) -> &'static str {
    match play {
        Play::Ask => "ask",
        Play::OpenApp => "open_app",
        Play::OpenBrowser => "open_browser",
        Play::Listening => "listening",
        Play::Starting => "starting",
        Play::Shown => "shown",
        Play::Unavailable => "",
    }
}

#[pyclass(name = "SpotifyCore", module = "flexweek_engine")]
struct SpotifyCore {
    player: Player,
}

#[pymethods]
impl SpotifyCore {
    #[new]
    fn new() -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                player: Player::default(),
            })
        })
    }

    #[staticmethod]
    #[pyo3(signature = (address, reachable, running))]
    fn play(address: Option<&str>, reachable: bool, running: bool) -> PyResult<&'static str> {
        guard(|| Ok(play_name(Player::play(address, reachable, running))))
    }

    fn asked_to_play(&mut self, address: &str) -> PyResult<&'static str> {
        guard(|| Ok(play_name(self.player.asked_to_play(address))))
    }

    fn app_opened(
        &mut self,
        address: &str,
        reachable: bool,
        opened: bool,
    ) -> PyResult<&'static str> {
        guard(|| {
            Ok(play_name(
                self.player.app_opened(address, reachable, opened),
            ))
        })
    }

    #[staticmethod]
    fn browser_opened(opened: bool) -> PyResult<&'static str> {
        guard(|| Ok(play_name(Player::browser_opened(opened))))
    }

    fn tick(&mut self, poll_ms: i64) -> PyResult<()> {
        guard(|| {
            self.player.tick(poll_ms);
            Ok(())
        })
    }

    fn check_playing(&self) -> PyResult<bool> {
        guard(|| Ok(self.player.check_playing()))
    }

    fn poll(
        &mut self,
        running: bool,
        playing: bool,
        ask_again_ms: i64,
    ) -> PyResult<(Option<String>, bool)> {
        guard(|| {
            Ok(match self.player.poll(running, playing, ask_again_ms) {
                Poll::Quiet => (None, false),
                Poll::Ask(address) => (Some(address), false),
                Poll::Heard => (None, true),
            })
        })
    }

    fn finish_poll(&mut self, asked: bool, grace_ms: i64) -> PyResult<bool> {
        guard(|| Ok(self.player.finish_poll(asked, grace_ms)))
    }

    fn give_up(&mut self, give_up_ms: i64) -> PyResult<bool> {
        guard(|| Ok(self.player.give_up(give_up_ms)))
    }

    fn stop(&self) -> PyResult<&'static str> {
        guard(|| {
            Ok(match self.player.stop() {
                Stop::Nothing => "",
                Stop::Pause => "pause",
                Stop::StopKey => "stop_key",
            })
        })
    }

    fn stopped(&mut self) -> PyResult<()> {
        guard(|| {
            self.player.stopped();
            Ok(())
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<SpotifyCore>()
}
