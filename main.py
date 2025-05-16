from fastapi import FastAPI
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/selfdestroy")
async def selfdestroy():
    url = os.getenv("RENDER_SUSPEND_URL")
    api_key = os.getenv("RENDER_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code == 200:
        return {"message": "Instance suspended successfully"}
    else:
        return {"message": "Failed to suspend instance", "details": response.text}
