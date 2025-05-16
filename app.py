from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

app = FastAPI()

# Serve static frontend files from 'frontend' folder
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Global variables
banned_emails = set()
logged_in_emails = set()

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Save message to a file
def save_message(message: str):
    with open("messages.txt", "a", encoding="utf-8") as file:
        file.write(message + "\n")

# Delete a specified number of messages
def delete_messages(num: int):
    with open("messages.txt", "r", encoding="utf-8") as file:
        lines = file.readlines()
    with open("messages.txt", "w", encoding="utf-8") as file:
        file.writelines(lines[:-num])

# WebSocket endpoint for chat
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if os.path.exists("messages.txt"):
            with open("messages.txt", "r", encoding="utf-8") as file:
                for line in file:
                    await websocket.send_text(line.strip())

        while True:
            data = await websocket.receive_text()

            # Command handling
            if data.startswith("/deletemessage"):
                try:
                    num = int(data.split(" ")[1])
                    delete_messages(num)
                    await manager.send_message(f"Deleted {num} messages.")
                except (IndexError, ValueError):
                    await manager.send_message("Invalid command format.")
            elif data.startswith("/safetycheck"):
                await manager.send_message(f"Logged in users: {', '.join(logged_in_emails)}")
            elif data.startswith("/ban"):
                email = data.split(" ")[1]
                banned_emails.add(email)
                await manager.send_message(f"Banned: {email}")
            elif data.startswith("/unban"):
                email = data.split(" ")[1]
                banned_emails.discard(email)
                await manager.send_message(f"Unbanned: {email}")
            elif data.startswith("/selfdestruct"):
                await manager.send_message("Enter password:")
                password = await websocket.receive_text()
                if password == "100005":
                    await manager.send_message("Shutting down...")
                    os._exit(0)
                else:
                    await manager.send_message("Invalid password.")
            else:
                save_message(data)
                await manager.send_message(data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
