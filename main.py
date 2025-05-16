import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
RENDER_API_KEY = os.getenv("RENDER_API_KEY")

app = FastAPI()

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")

    # New: handle /selfdestroy command
    if message.strip() == "/selfdestroy":
        try:
            render_url = "https://your-render-url.com/api/disable-chatroom"  # Change this to your real URL
            headers = {
                "Authorization": f"Bearer {RENDER_API_KEY}",
                "Content-Type": "application/json"
            }
            response = requests.post(render_url, headers=headers, json={"reason": "selfdestroy command triggered"})

            if response.status_code == 200:
                return JSONResponse({"reply": "Chatroom will be disabled shortly."})
            else:
                return JSONResponse({"reply": f"Failed to disable chatroom: {response.status_code}"})
        except Exception as e:
            return JSONResponse({"reply": f"Error sending disable request: {str(e)}"})

    # Existing chat handling below
    return JSONResponse({"reply": f"Received message: {message}"})
