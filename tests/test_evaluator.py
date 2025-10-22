import pytest

from host.cards import Card, build_deck
from host.evaluator import evaluate_best, parse_cards


def test_evaluate_best_identifies_all_hand_categories():
    cases = [
        (8, ["Ah", "Kh", "Qh", "Jh", "Th"]),  # straight flush
        (7, ["As", "Ah", "Ad", "Ac", "Kd"]),  # four of a kind
        (6, ["Qc", "Qd", "Qs", "9h", "9s"]),  # full house
        (5, ["Ah", "Jh", "9h", "6h", "2h"]),  # flush
        (4, ["9h", "8d", "7c", "6s", "5h"]),  # straight
        (3, ["8h", "8d", "8s", "Qd", "Js"]),  # three of a kind
        (2, ["7h", "7d", "4s", "4c", "As"]),  # two pair
        (1, ["6h", "6s", "Qh", "8d", "4c"]),  # one pair
        (0, ["As", "Kd", "Jh", "9c", "4d"]),  # high card
    ]

    for expected_rank, labels in cases:
        cards = parse_cards(labels)
        rank, _ = evaluate_best(cards)
        assert rank == expected_rank, f"labels={labels}"


def test_evaluate_best_handles_wheel_straight():
    cards = parse_cards(["Ah", "2d", "3c", "4s", "5h", "9d", "Kd"])
    rank, detail = evaluate_best(cards)
    assert rank == 4
    assert detail[0] == 5


def test_evaluate_best_compares_kickers_for_equal_pairs():
    hand_a = parse_cards(["Ah", "Ad", "Kc", "Qs", "9h", "2d", "3c"])
    hand_b = parse_cards(["Ah", "Ad", "Qc", "Js", "8h", "2d", "3c"])
    assert evaluate_best(hand_a) > evaluate_best(hand_b)


def test_card_validation_rejects_invalid_labels():
    with pytest.raises(ValueError, match="Invalid rank"):
        Card("1", "h")
    with pytest.raises(ValueError, match="Invalid suit"):
        Card("A", "x")


def test_parse_cards_and_evaluate_supports_multiple_seven_card_hands():
    deck = build_deck(seed=777)
    for idx in range(0, 42, 7):
        seven_card_hand = deck[idx : idx + 7]
        rank, detail = evaluate_best(seven_card_hand)
        assert 0 <= rank <= 8
        assert isinstance(detail, list)
