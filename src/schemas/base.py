from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, EmailStr


class BaseSchema(BaseModel):
    updated_at: Optional[datetime]
    created_at: Optional[datetime]


RESPONSE_SCHEMA = {
    200: {
        "description": "Successful request"
    },
    400: {
        "description": "Invalid  request payload"
    },
    404: {
        "description": "Data not found"
    },
    403: {
        "description": "Permission denied"
    }
}


class BaseResponseSchema(BaseModel):
    status_code: int
    description: str
    data: Optional[dict]


class QueryRequest(BaseModel):
    question: str
