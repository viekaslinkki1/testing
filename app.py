from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

app = FastAPI()

# Serve static frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve the main HTML page
@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")


# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


# Save message to a file
def save_message(message: str):
    with open("messages.txt", "a") as file:
        file.write(message + "\n")


# WebSocket endpoint
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send all previous messages to the new connection
        if os.path.exists("messages.txt"):
            with open("messages.txt", "r") as file:
                for line in file:
                    await websocket.send_text(line.strip())

        while True:
            data = await websocket.receive_text()
            save_message(data)
            await manager.send_message(data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)
