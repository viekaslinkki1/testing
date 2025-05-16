import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
RENDER_API_KEY = os.getenv("RENDER_API_KEY")
RENDER_SUSPEND_URL = os.getenv("RENDER_SUSPEND_URL")

app = FastAPI()

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")

    # New: handle /selfdestroy command
    if message.strip() == "/selfdestroy":
        try:
            headers = {
                "Authorization": f"Bearer {RENDER_API_KEY}",
                "Content-Type": "application/json"
            }

            # Send POST request to Render.com to suspend the service
            response = requests.post(RENDER_SUSPEND_URL, headers=headers)

            # Log response for debugging
            print(f"[INFO] Render API Response: {response.status_code} - {response.text}")

            # Handle the response
            if response.status_code == 200:
                return JSONResponse({"reply": "💣 Chatroom will be disabled shortly."})
            elif response.status_code == 401:
                return JSONResponse({"reply": "🔒 Unauthorized! Check your API key."})
            elif response.status_code == 404:
                return JSONResponse({"reply": "❓ Service not found. Check the URL."})
            else:
                return JSONResponse({"reply": f"⚠️ Failed to disable chatroom: {response.status_code}"})
        except Exception as e:
            print(f"[ERROR] Exception during Render API call: {str(e)}")
            return JSONResponse({"reply": f"❌ Error sending disable request: {str(e)}"})

    # Existing chat handling below
    return JSONResponse({"reply": f"Received message: {message}"})
