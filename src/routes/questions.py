import logging
from fastapi import APIRouter, Cookie, HTTPException, Response, Request, Query, Path
from conf.settings import Settings
from schemas.base import QueryRequest, BaseResponseSchema
from services.fpds_query_helper import FPDSQueryHelper

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Lightweight health check endpoint to verify the API is running.
    """
    return {"status": "healthy", "message": "FPDS API is running"}


@router.post("/query", response_model=BaseResponseSchema)
async def query(request: QueryRequest):
    """
    Accepts a JSON body with a 'question' field and returns an 'answer'.
    """
    query_helper = FPDSQueryHelper(
        openai_api_key=Settings.open_api_key
    )
    try:
        answer = query_helper.query(request.question)
        print(f"Filter: {answer['mongo_filter']}")
        print(f"\nFormatted Response:\n{answer['formatted_response']}")
        formatted_response = answer["formatted_response"]
        return BaseResponseSchema(status_code=200, description="return questions answer", data={"results": formatted_response})
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to process query")