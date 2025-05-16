from pydantic import BaseModel

class CommandModel(BaseModel):
    command: str
