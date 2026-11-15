
"""Read and execute commands in the order provided."""

from pathlib import Path


class CommandProcessor:
    """Dispatch command-file lines to the batch engine."""

    def __init__(self, engine):
        self.engine = engine
        self.print_requests = []
        self.refused_commands = []

    def execute_line(self, line):
        """Execute one command line. Ignore comments and blank lines."""

        line = line.strip()

        if not line or line.startswith("#"):
            return None

        parts = [part.strip() for part in line.split("|")]
        command = parts[0]
        args = parts[1:]

        if command == "RECEIVE_BATCH" and len(args) == 2:
            return self.engine.receive_batch(*args)

        if command == "SAMPLE" and len(args) == 2:
            try:
                return self.engine.sample_batch(*args)
            except ValueError as error:
                if str(error).startswith("Sampling refused:"):
                    self.refused_commands.append({
                        "command": line,
                        "reason": str(error),
                    })
                    print(f"Expected refusal: {line}")
                    print(f"Reason: {error}")
                    return None
                raise

        if command == "RECORD_RESULT" and len(args) == 5:
            batch_id, timestamp, critical, major, minor = args
            return self.engine.record_result(
                batch_id,
                timestamp,
                int(critical),
                int(major),
                int(minor),
            )

        if command == "REWORK" and len(args) == 2:
            try:
                return self.engine.rework_batch(*args)
            except ValueError as error:
                if str(error).startswith("Rework refused:"):
                    self.refused_commands.append({
                        "command": line,
                        "reason": str(error),
                    })
                    print(f"Expected refusal: {line}")
                    print(f"Reason: {error}")
                    return None
                raise

        if command == "HOLD_REQUEST" and len(args) == 3:
            return self.engine.hold_request(*args)

        if command == "COMPLAINT" and len(args) == 3:
            return self.engine.complaint(*args)

        if command == "CORRECTIVE_ACTION" and len(args) == 3:
            return self.engine.corrective_action(*args)

        if command == "PRINT_DECISIONS" and len(args) == 0:
            self.print_requests.append(("PRINT_DECISIONS", None))
            return None

        if command == "PRINT_SWITCHING" and len(args) == 1:
            self.print_requests.append(("PRINT_SWITCHING", args[0]))
            return None

        if command == "PRINT_RELEASE_REGISTER" and len(args) == 0:
            self.print_requests.append(("PRINT_RELEASE_REGISTER", None))
            return None

        raise ValueError(f"Invalid command or argument count: {line}")

    def execute_file(self, file_path):
        """Execute every command in strict file order."""

        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"Command file not found: {path}")

        results = []

        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                try:
                    result = self.execute_line(line)

                    if line.strip() and not line.lstrip().startswith("#"):
                        results.append((line_number, result))

                except Exception as error:
                    raise RuntimeError(
                        f"Command failed at line {line_number}: "
                        f"{line.strip()}"
                    ) from error

        return results
