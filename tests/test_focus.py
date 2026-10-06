import cv2
import numpy as np

from machine_vision.imaging.focus import focus_peaking, laplacian_variance, motion_score, tenengrad


def test_sharp_checkerboard_scores_higher_than_blurred_image():
    tile = np.indices((200, 200)).sum(axis=0) // 10 % 2
    sharp = (tile * 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(sharp, (21, 21), 5)

    assert laplacian_variance(sharp) > laplacian_variance(blurred)
    assert tenengrad(sharp) > tenengrad(blurred)


def test_first_frame_cannot_prove_stationary_state():
    image = np.zeros((100, 100), dtype=np.uint8)
    assert motion_score(None, image) == float("inf")


def test_focus_peaking_is_confined_to_target_roi():
    image = np.full((160, 240, 3), 70, dtype=np.uint8)
    tile = np.indices((100, 100)).sum(axis=0) // 5 % 2
    image[30:130, 70:170] = np.repeat((tile * 255)[:, :, None], 3, axis=2)

    overlay = focus_peaking(image, threshold=25, roi=(70, 30, 100, 100), percentile=80)

    outside = np.ones(image.shape[:2], dtype=bool)
    outside[30:130, 70:170] = False
    assert np.array_equal(overlay[outside], image[outside])
    assert np.count_nonzero(overlay[30:130, 70:170] != image[30:130, 70:170]) > 0
