use flexweek_app::session::spotify::{Play, Player, Poll, Stop};

const TRACK: &str = "spotify:track:4LUJzSLpBtgH3dpOH7J7Nf";
const PLAYLIST: &str = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M";
const POLL_MS: i64 = 250;
const ASK_AGAIN_MS: i64 = 2_000;
const GRACE_MS: i64 = 1_500;
const GIVE_UP_MS: i64 = 20_000;

fn listening() -> Player {
    let mut player = Player::default();
    assert_eq!(player.asked_to_play(TRACK), Play::Listening);
    player
}

fn poll(player: &mut Player, running: bool, playing: bool) -> (Poll, bool) {
    player.tick(POLL_MS);
    let action = player.poll(running, playing, ASK_AGAIN_MS);
    let late =
        action != Poll::Heard && player.finish_poll(matches!(action, Poll::Ask(_)), GRACE_MS);
    (action, late)
}

fn stop(player: &mut Player) -> Stop {
    let action = player.stop();
    player.stopped();
    action
}

#[test]
fn asks_running_spotify_once_then_retries_at_two_seconds() {
    assert_eq!(Player::play(Some(TRACK), true, true), Play::Ask);
    let mut player = listening();
    assert!(player.check_playing());
    for _ in 0..7 {
        assert_eq!(poll(&mut player, true, false).0, Poll::Quiet);
    }
    assert_eq!(poll(&mut player, true, false).0, Poll::Ask(TRACK.into()));
    for _ in 0..7 {
        assert_eq!(poll(&mut player, true, false).0, Poll::Quiet);
    }
    assert_eq!(poll(&mut player, true, false).0, Poll::Ask(TRACK.into()));
}

#[test]
fn asks_a_just_opened_spotify_before_checking_playback() {
    assert_eq!(Player::play(Some(PLAYLIST), true, false), Play::OpenApp);
    let mut player = Player::default();
    assert_eq!(player.app_opened(PLAYLIST, true, true), Play::Listening);
    assert_eq!(poll(&mut player, false, false), (Poll::Quiet, false));
    assert!(!player.check_playing());
    assert_eq!(poll(&mut player, true, false).0, Poll::Ask(PLAYLIST.into()));
    assert!(player.check_playing());
    for _ in 0..7 {
        assert_eq!(poll(&mut player, true, false).0, Poll::Quiet);
    }
    assert_eq!(poll(&mut player, true, false).0, Poll::Ask(PLAYLIST.into()));
}

#[test]
fn hearing_spotify_stops_polling_before_late_or_retry() {
    let mut player = listening();
    player.tick(2_000);
    assert_eq!(player.poll(true, true, ASK_AGAIN_MS), Poll::Heard);
    assert!(!player.check_playing());
    assert_eq!(poll(&mut player, true, true), (Poll::Quiet, false));
    assert_eq!(player.stop(), Stop::Pause);
}

#[test]
fn says_late_once_at_the_grace_period() {
    let mut player = listening();
    for _ in 0..5 {
        assert!(!poll(&mut player, false, false).1);
    }
    assert!(poll(&mut player, false, false).1);
    assert!(!poll(&mut player, false, false).1);
    assert_eq!(poll(&mut player, true, true).0, Poll::Heard);
}

#[test]
fn a_failed_first_request_can_retry_on_the_next_poll() {
    let mut player = Player::default();
    assert_eq!(player.app_opened(PLAYLIST, true, true), Play::Listening);
    player.tick(GRACE_MS);
    assert_eq!(
        player.poll(true, false, ASK_AGAIN_MS),
        Poll::Ask(PLAYLIST.into())
    );
    assert!(!player.check_playing());
    assert_eq!(
        poll(&mut player, true, false),
        (Poll::Ask(PLAYLIST.into()), true)
    );
}

#[test]
fn gives_up_at_twenty_seconds_and_can_still_pause() {
    let mut player = listening();
    for _ in 0..79 {
        poll(&mut player, false, false);
        assert!(!player.give_up(GIVE_UP_MS));
    }
    assert_eq!(poll(&mut player, false, false), (Poll::Quiet, false));
    assert!(player.give_up(GIVE_UP_MS));
    assert_eq!(poll(&mut player, true, true), (Poll::Quiet, false));
    assert_eq!(player.stop(), Stop::Pause);
}

#[test]
fn late_handler_can_start_new_playback_at_the_give_up_poll() {
    let mut player = listening();
    player.tick(GIVE_UP_MS);
    assert!(player.finish_poll(false, GRACE_MS));
    assert_eq!(stop(&mut player), Stop::Pause);
    assert_eq!(player.asked_to_play(PLAYLIST), Play::Listening);
    assert!(!player.give_up(GIVE_UP_MS));
}

#[test]
fn opening_a_track_without_a_remote_starts_it_and_uses_the_stop_key() {
    let mut player = Player::default();
    assert_eq!(Player::play(Some(TRACK), false, false), Play::OpenApp);
    assert_eq!(player.app_opened(TRACK, false, true), Play::Starting);
    assert_eq!(stop(&mut player), Stop::StopKey);
    assert_eq!(player.stop(), Stop::Nothing);
}

#[test]
fn opening_other_addresses_without_a_remote_only_shows_them() {
    let mut player = Player::default();
    for kind in ["playlist", "album", "episode", "show"] {
        let address = format!("spotify:{kind}:abc123");
        assert_eq!(Player::play(Some(&address), false, false), Play::OpenApp);
        assert_eq!(player.app_opened(&address, false, true), Play::Shown);
        assert_eq!(player.stop(), Stop::Nothing);
    }
}

#[test]
fn browser_fallback_is_shown_only_if_the_browser_opens() {
    let mut player = Player::default();
    for reachable in [false, true] {
        assert_eq!(Player::play(Some(TRACK), reachable, false), Play::OpenApp);
        assert_eq!(
            player.app_opened(TRACK, reachable, false),
            Play::OpenBrowser
        );
        assert_eq!(Player::browser_opened(true), Play::Shown);
        assert_eq!(player.stop(), Stop::Nothing);
    }
    assert_eq!(Player::browser_opened(false), Play::Unavailable);
    assert_eq!(Player::play(None, true, true), Play::Unavailable);
}

#[test]
fn stop_pauses_only_what_flexweek_started() {
    let mut player = Player::default();
    assert_eq!(player.stop(), Stop::Nothing);
    assert_eq!(player.asked_to_play(TRACK), Play::Listening);
    assert_eq!(stop(&mut player), Stop::Pause);
    assert_eq!(player.stop(), Stop::Nothing);

    assert_eq!(player.app_opened(PLAYLIST, true, true), Play::Listening);
    assert_eq!(stop(&mut player), Stop::Pause);
    assert_eq!(player.stop(), Stop::Nothing);
}

#[test]
fn failed_pause_can_be_retried() {
    let mut player = listening();
    assert_eq!(player.stop(), Stop::Pause);
    assert_eq!(stop(&mut player), Stop::Pause);
    assert_eq!(player.stop(), Stop::Nothing);
}
