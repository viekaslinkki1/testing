import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>FastAPI Chatroom</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 600px; margin: 2em auto; }
  #messages { 
    width: 100%; 
    height: 300px; 
    border: 1px solid #ccc; 
    padding: 0.5em; 
    overflow-y: scroll; 
    white-space: pre-wrap;
    background-color: #f9f9f9;
  }
  #input { 
    width: 80%; 
    padding: 0.5em; 
    font-size: 1em; 
  }
  #sendBtn {
    padding: 0.5em 1em; 
    font-size: 1em;
  }
</style>
</head>
<body>

<h2>Chatroom</h2>
<div id="messages"></div>

<input type="text" id="input" placeholder="Type your message here..." />
<button id="sendBtn">Send</button>

<script>
  const messagesDiv = document.getElementById('messages');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('sendBtn');

  // Use correct ws or wss protocol based on page protocol
  const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
  const ws = new WebSocket(wsProtocol + window.location.host + '/ws/chat');

  ws.onmessage = (event) => {
    messagesDiv.textContent += event.data + '\\n';
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  };

  sendBtn.onclick = () => {
    const msg = input.value.trim();
    if (msg !== '') {
      ws.send(msg);
      input.value = '';
    }
  };

  input.addEventListener('keyup', (e) => {
    if (e.key === 'Enter') {
      sendBtn.click();
    }
  });

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
  };

  ws.onclose = () => {
    console.warn("WebSocket connection closed.");
  };
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
