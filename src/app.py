from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routes.questions import router as question_router

app = FastAPI(
    title="FPDS API’s",
    description="FPDS API v1",
    version="1.0.0",
    docs_url=None, redoc_url=None
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(question_router, tags=["Questions"], prefix="/ask_fpds/api/v1")