from fastapi import APIRouter, HTTPException
from app.models.commands import CommandModel
from app.services.command_service import CommandService

router = APIRouter()
command_service = CommandService()

@router.get("/")
def get_all_commands():
    """Fetch all available commands."""
    commands = command_service.get_all_commands()
    if not commands:
        raise HTTPException(status_code=404, detail="No commands found.")
    return {"commands": commands}

@router.post("/execute")
def execute_command(command: CommandModel):
    """Execute a specified command."""
    result = command_service.execute_command(command.command)
    if result is None:
        raise HTTPException(status_code=404, detail="Command not found.")
    return {"result": result}
