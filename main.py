from fastapi import FastAPI
from app.routers import auth, dashboard, commands

app = FastAPI()

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(commands.router, prefix="/commands", tags=["Commands"])

@app.get("/")
def root():
    return {"message": "Welcome to the FastAPI Application"}
