import uvicorn
from conf.settings import Settings

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=Settings.PORT, reload=True)
