
import pytest

from quality_engine.command_processor import CommandProcessor


class FakeEngine:
    def __init__(self):
        self.calls = []

    def receive_batch(self, *args):
        self.calls.append(("RECEIVE_BATCH", args))

    def sample_batch(self, *args):
        self.calls.append(("SAMPLE", args))

    def record_result(self, *args):
        self.calls.append(("RECORD_RESULT", args))

    def rework_batch(self, *args):
        self.calls.append(("REWORK", args))

    def hold_request(self, *args):
        self.calls.append(("HOLD_REQUEST", args))

    def complaint(self, *args):
        self.calls.append(("COMPLAINT", args))

    def corrective_action(self, *args):
        self.calls.append(("CORRECTIVE_ACTION", args))


@pytest.fixture
def processor():
    return CommandProcessor(FakeEngine())


def test_ignores_blank_lines_and_comments(processor):
    assert processor.execute_line("") is None
    assert processor.execute_line("   ") is None
    assert processor.execute_line("# comment") is None
    assert processor.engine.calls == []


def test_dispatches_receive_batch(processor):
    processor.execute_line(
        "RECEIVE_BATCH|BT-0001|2026-05-04 09:48:00"
    )
    assert processor.engine.calls[0] == (
        "RECEIVE_BATCH",
        ("BT-0001", "2026-05-04 09:48:00"),
    )


def test_dispatches_record_result_with_integer_defects(processor):
    processor.execute_line(
        "RECORD_RESULT|BT-0001|2026-05-06 08:10:00|0|1|3"
    )
    assert processor.engine.calls[0] == (
        "RECORD_RESULT",
        ("BT-0001", "2026-05-06 08:10:00", 0, 1, 3),
    )


def test_dispatches_other_engine_commands(processor):
    lines = [
        "SAMPLE|BT-0001|2026-05-04 12:04:00",
        "REWORK|BT-0001|2026-05-07 09:00:00",
        "HOLD_REQUEST|BT-0002|2026-05-08 09:00:00|BT-0001",
        "COMPLAINT|BT-0001|2026-05-09 09:00:00|CMP-01",
        "CORRECTIVE_ACTION|SUP-03|2026-05-10 09:00:00|CAR-01",
    ]

    for line in lines:
        processor.execute_line(line)

    assert [call[0] for call in processor.engine.calls] == [
        "SAMPLE",
        "REWORK",
        "HOLD_REQUEST",
        "COMPLAINT",
        "CORRECTIVE_ACTION",
    ]


def test_stores_print_requests(processor):
    processor.execute_line("PRINT_DECISIONS")
    processor.execute_line("PRINT_SWITCHING|SUP-01")
    processor.execute_line("PRINT_RELEASE_REGISTER")

    assert processor.print_requests == [
        ("PRINT_DECISIONS", None),
        ("PRINT_SWITCHING", "SUP-01"),
        ("PRINT_RELEASE_REGISTER", None),
    ]


def test_rejects_invalid_command(processor):
    with pytest.raises(ValueError):
        processor.execute_line("UNKNOWN_COMMAND|value")


def test_rejects_wrong_argument_count(processor):
    with pytest.raises(ValueError):
        processor.execute_line("RECEIVE_BATCH|BT-0001")


def test_executes_file_in_order(processor, tmp_path):
    command_file = tmp_path / "commands.txt"
    command_file.write_text(
        "# sample commands\n"
        "RECEIVE_BATCH|BT-0001|2026-05-04 09:48:00\n"
        "\n"
        "SAMPLE|BT-0001|2026-05-04 12:04:00\n",
        encoding="utf-8",
    )

    results = processor.execute_file(command_file)

    assert len(results) == 2
    assert [call[0] for call in processor.engine.calls] == [
        "RECEIVE_BATCH",
        "SAMPLE",
    ]


def test_missing_command_file_raises_error(processor, tmp_path):
    missing_file = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        processor.execute_file(missing_file)
