# Skill: WUTT FastAPI Backend Patterns

## When to use this skill
Load when working on any backend Python file: main.py, routes/*.py, models.py, database.py

## FastAPI App Setup Pattern
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="WUTT API", version="1.0.0")

# CORS — add BEFORE routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://wutt.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Standard API Response Format
```python
# Always return this structure
def success_response(data=None, message="Success"):
    return {"status": "success", "data": data, "message": message}

def error_response(message="Error", code=400):
    return JSONResponse(
        status_code=code,
        content={"status": "error", "data": None, "message": message}
    )
```

## SQLite + SQLAlchemy Setup
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./wutt.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## JWT Auth Pattern
```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Cloudinary Upload Pattern
```python
import cloudinary.uploader

def upload_to_cloudinary(file_bytes: bytes, folder: str = "wutt/wardrobes") -> dict:
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=folder,
        resource_type="image",
        transformation=[{"width": 800, "crop": "limit"}]  # resize for storage
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"]
    }
```

## Environment Variables Required
```
OPENAI_API_KEY=
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
OPENWEATHER_API_KEY=
JWT_SECRET_KEY=
DATABASE_URL=sqlite:///./wutt.db
```
