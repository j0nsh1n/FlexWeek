//! The sentences that say why homework was not placed name who is in the way and what to do, and speak of
//! the homework type's order rather than a "priority" (0.19.0 wording audit, findings 4 and 5).

use flexweek_engine::plan::sentence;

#[test]
fn test_the_two_no_room_reasons_say_who_is_in_the_way_and_what_to_do() {
    assert_eq!(
        sentence("NO_SLOT_LEFT").unwrap(),
        "Your other homework is using every free gap before it's due. Move or shorten one, or choose a time yourself."
    );
    assert_eq!(
        sentence("LOCKED_OVERLAP").unwrap(),
        "Your fixed times and finished work leave no gap long enough for it before it's due. Shorten it, split it, or change the due date."
    );
}

#[test]
fn test_the_type_reason_names_the_order_instead_of_priority() {
    let reason = sentence("PRIORITY_PREEMPT").unwrap();
    assert_eq!(
        reason,
        "Tests and other homework that's planned first used the free time before it's due. Move one of them, shorten this, or choose a time yourself."
    );
    assert!(!reason.to_lowercase().contains("priority"));
}
