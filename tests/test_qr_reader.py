import cv2

from machine_vision.readers.qr_reader import QrReader


def test_generated_qr_is_decoded():
    image = cv2.QRCodeEncoder_create().encode("VN123456789")
    image = cv2.resize(image, (480, 480), interpolation=cv2.INTER_NEAREST)
    result = QrReader({"upscale": 2.0, "try_inverted": True}).read(image)

    assert result is not None
    assert result.text == "VN123456789"
    assert result.corners is not None
    assert result.corners.shape == (4, 2)
