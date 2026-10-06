from machine_vision.services.label_parser import find_waybill, find_waybill_in_qr, normalize_text


def test_find_waybill_removes_visual_separators():
    assert find_waybill("Mã vận đơn: VN-123 456 789") == "VN123456789"


def test_normalize_text_preserves_vietnamese():
    assert normalize_text("  12   Nguyễn Huệ,  Quận 1 ") == "12 Nguyễn Huệ, Quận 1"


def test_find_waybill_in_json_qr():
    assert find_waybill_in_qr('{"waybill_code":"VN123456789"}') == "VN123456789"


def test_find_waybill_in_url_qr():
    value = "https://example.test/track?waybill=VN123456789"
    assert find_waybill_in_qr(value) == "VN123456789"
