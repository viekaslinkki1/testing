from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# Serve static HTML file (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

html = """
<!DOCTYPE html>
<html>
<head>
  <title>WebSocket Chat</title>
  <style>
    #messages {
      width: 400px; height: 300px;
      border: 1px solid #ccc;
      overflow-y: auto;
      padding: 10px;
      margin-bottom: 10px;
      font-family: monospace;
      background: #f9f9f9;
    }
    #input {
      width: 300px;
      padding: 5px;
    }
    #sendBtn {
      padding: 5px 10px;
    }
  </style>
</head>
<body>
  <h3>WebSocket Chat</h3>
  <div id="messages"></div>
  <input id="input" type="text" autocomplete="off" placeholder="Type message..." />
  <button id="sendBtn">Send</button>

  <script>
    const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(`${wsProtocol}${window.location.host}/ws/chat`);

    const messagesDiv = document.getElementById("messages");
    const input = document.getElementById("input");
    const sendBtn = document.getElementById("sendBtn");

    ws.onmessage = (event) => {
      const newMessage = document.createElement("div");
      newMessage.textContent = event.data;
      messagesDiv.appendChild(newMessage);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    };

    ws.onerror = (event) => {
      console.error("WebSocket error:", event);
      const errorMessage = document.createElement("div");
      errorMessage.textContent = "⚠️ Connection Error.";
      errorMessage.style.color = "red";
      messagesDiv.appendChild(errorMessage);
    };

    ws.onclose = () => {
      console.warn("WebSocket connection closed.");
      const closedMessage = document.createElement("div");
      closedMessage.textContent = "🔒 Connection closed.";
      closedMessage.style.color = "orange";
      messagesDiv.appendChild(closedMessage);
    };

    sendBtn.onclick = () => {
      const msg = input.value.trim();
      if (msg !== "") {
        ws.send(msg);
        input.value = '';
      }
    };

    input.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        sendBtn.click();
      }
    });
  </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"User: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
