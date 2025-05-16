class CommandService:
    def __init__(self):
        # Predefined commands that the system can execute
        self.commands = {
            "status": "System is running smoothly.",
            "restart": "System restart initiated.",
            "shutdown": "System shutdown initiated.",
            "help": "Available commands: status, restart, shutdown, help"
        }

    def get_all_commands(self):
        """Retrieve the list of all available commands."""
        return list(self.commands.keys())

    def execute_command(self, command: str):
        """Execute a command and return its output."""
        return self.commands.get(command, None)
