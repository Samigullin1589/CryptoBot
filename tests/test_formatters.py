from bot.utils.formatters import format_halving_info, format_network_status


def test_format_halving_info():
    data = {
        "progressPercent": 12.3456,
        "remainingBlocks": 12345,
        "estimated_date": "2030-01-01",
    }
    text = format_halving_info(data)
    assert "12.35%" in text
    assert "12,345" in text
    assert "2030-01-01" in text


def test_format_network_status():
    data = {
        "hashrate_ehs": 321.1234,
        "difficulty_change": -5.678,
        "estimated_retarget_date": "2025-12-31",
    }
    text = format_network_status(data)
    assert "321.12 EH/s" in text
    assert "~-5.68%" in text
    assert "2025-12-31" in text

