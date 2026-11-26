import cv2
import numpy as np
import pytest

from innersight.cards import CardColor
from innersight.color import classify_card_color

CARD_HEIGHT = 300
CARD_WIDTH = 200
CARD_CENTER = (CARD_WIDTH // 2, CARD_HEIGHT // 2)
OVAL_AXES = (110, 60)
OVAL_TILT_DEGREES = -60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

RED_HUE = 2
RED_HUE_BELOW_ZERO = 177
YELLOW_HUE = 25
GREEN_HUE = 65
BLUE_HUE = 110
# A webcam shows both a yellow and a green card in about this hue.
OLIVE_HUE = 40
# How much of the green and red light is left in the bluish light of a monitor.
BLUISH_LIGHT_BGR = (1.0, 0.6, 0.6)


def bgr_from_hue(hue: int, saturation: int = 220, value: int = 220) -> tuple[int, int, int]:
    hsv_pixel = np.uint8([[[hue, saturation, value]]])
    blue, green, red = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0, 0]
    return int(blue), int(green), int(red)


def make_blank_card(bgr: tuple[int, int, int]) -> np.ndarray:
    return np.full((CARD_HEIGHT, CARD_WIDTH, 3), bgr, dtype=np.uint8)


def make_number_card(bgr: tuple[int, int, int]) -> np.ndarray:
    """A colored card with the white tilted oval and a colored digit block in its middle."""
    card = make_blank_card(bgr)
    cv2.ellipse(card, CARD_CENTER, OVAL_AXES, OVAL_TILT_DEGREES, 0, 360, WHITE, cv2.FILLED)
    cv2.rectangle(card, (80, 110), (120, 190), bgr, cv2.FILLED)
    return card


def make_wild_card() -> np.ndarray:
    """A black card whose oval is split into the four UNO colors."""
    card = make_blank_card(BLACK)
    for quadrant, hue in enumerate((RED_HUE, YELLOW_HUE, GREEN_HUE, BLUE_HUE)):
        start_angle = quadrant * 90
        cv2.ellipse(
            card,
            CARD_CENTER,
            OVAL_AXES,
            OVAL_TILT_DEGREES,
            start_angle,
            start_angle + 90,
            bgr_from_hue(hue),
            cv2.FILLED,
        )
    return card


@pytest.mark.parametrize(
    ("hue", "expected_color"),
    [
        (RED_HUE, CardColor.RED),
        (RED_HUE_BELOW_ZERO, CardColor.RED),
        (YELLOW_HUE, CardColor.YELLOW),
        (GREEN_HUE, CardColor.GREEN),
        (BLUE_HUE, CardColor.BLUE),
    ],
)
def test_classifies_number_card_by_its_hue(hue: int, expected_color: CardColor) -> None:
    card = make_number_card(bgr_from_hue(hue))

    assert classify_card_color(card) is expected_color


def test_classifies_dimly_lit_card() -> None:
    card = make_number_card(bgr_from_hue(BLUE_HUE, saturation=180, value=90))

    assert classify_card_color(card) is CardColor.BLUE


def test_ignores_white_glare_on_the_card() -> None:
    card = make_blank_card(bgr_from_hue(GREEN_HUE))
    cv2.circle(card, CARD_CENTER, 70, WHITE, cv2.FILLED)

    assert classify_card_color(card) is CardColor.GREEN


def test_ignores_background_at_the_edges_of_the_crop() -> None:
    crop = make_blank_card(bgr_from_hue(BLUE_HUE))
    cv2.rectangle(crop, (30, 45), (170, 255), bgr_from_hue(GREEN_HUE), cv2.FILLED)
    cv2.ellipse(crop, CARD_CENTER, (70, 40), OVAL_TILT_DEGREES, 0, 360, WHITE, cv2.FILLED)

    assert classify_card_color(crop) is CardColor.GREEN


def test_reads_a_red_card_in_bluish_light_that_tints_its_white_blue() -> None:
    card = make_number_card(bgr_from_hue(RED_HUE))
    tinted_card = (card * BLUISH_LIGHT_BGR).astype(np.uint8)

    assert classify_card_color(tinted_card) is CardColor.RED


@pytest.mark.parametrize(
    ("value", "expected_color"),
    [(220, CardColor.YELLOW), (110, CardColor.GREEN)],
)
def test_tells_yellow_from_green_by_brightness_where_their_hues_meet(
    value: int, expected_color: CardColor
) -> None:
    card = make_number_card(bgr_from_hue(OLIVE_HUE, value=value))

    assert classify_card_color(card) is expected_color


def test_reads_a_well_lit_olive_card_that_is_dark_beside_its_white_as_green() -> None:
    card = make_number_card(bgr_from_hue(OLIVE_HUE, value=178))

    assert classify_card_color(card) is CardColor.GREEN


def test_reads_a_dimly_lit_olive_card_that_is_as_bright_as_its_white_as_yellow() -> None:
    card = make_number_card(bgr_from_hue(OLIVE_HUE))
    dim_card = (card * 0.5).astype(np.uint8)

    assert classify_card_color(dim_card) is CardColor.YELLOW


def test_reads_a_green_card_washed_out_by_bright_light_behind_it() -> None:
    card = make_number_card(bgr_from_hue(GREEN_HUE))
    washed_out_card = (card * 0.4 + 150).astype(np.uint8)

    assert classify_card_color(washed_out_card) is CardColor.GREEN


def test_does_not_take_a_finger_on_a_washed_out_card_for_a_red_card() -> None:
    card = make_number_card((170, 170, 170))
    skin_bgr = bgr_from_hue(RED_HUE + 6, saturation=150, value=200)
    cv2.rectangle(card, (60, 200), (96, 248), skin_bgr, cv2.FILLED)

    assert classify_card_color(card) is CardColor.UNKNOWN


def test_returns_unknown_for_a_crop_split_between_four_colors() -> None:
    assert classify_card_color(make_wild_card()) is CardColor.UNKNOWN


def test_returns_unknown_for_card_without_any_color() -> None:
    assert classify_card_color(make_blank_card(BLACK)) is CardColor.UNKNOWN
