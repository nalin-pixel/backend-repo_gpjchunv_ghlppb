import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import BlogPost, Category

app = FastAPI(title="Blog CMS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class BlogCreate(BaseModel):
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    author: Optional[str] = "Admin"
    published: bool = True

class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Blog CMS Backend running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# ----- Categories -----
@app.post("/api/categories")
def create_category(payload: CategoryCreate):
    try:
        cid = create_document("category", payload.model_dump())
        return {"id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
def list_categories():
    try:
        cats = get_documents("category")
        # Convert ObjectId
        for c in cats:
            c["id"] = str(c.pop("_id"))
        return cats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- Blog Posts -----
@app.post("/api/posts")
def create_post(payload: BlogCreate):
    try:
        # ensure slug unique
        existing = db["blogpost"].find_one({"slug": payload.slug})
        if existing:
            raise HTTPException(status_code=400, detail="Slug already exists")
        doc = payload.model_dump()
        if doc.get("published") and "published_at" not in doc:
            from datetime import datetime, timezone
            doc["published_at"] = datetime.now(timezone.utc)
        pid = create_document("blogpost", doc)
        return {"id": pid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/posts")
def list_posts(category: Optional[str] = None, tag: Optional[str] = None, q: Optional[str] = None, limit: int = 20):
    try:
        filt = {}
        if category:
            filt["category"] = category
        if tag:
            filt["tags"] = {"$in": [tag]}
        if q:
            filt["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"excerpt": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}},
            ]
        items = get_documents("blogpost", filt, limit)
        for it in items:
            it["id"] = str(it.pop("_id"))
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/posts/{slug}")
def get_post(slug: str):
    try:
        doc = db["blogpost"].find_one({"slug": slug})
        if not doc:
            raise HTTPException(status_code=404, detail="Post not found")
        doc["id"] = str(doc.pop("_id"))
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Simple admin login (no auth provider) - username/password from env
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/admin/login")
def admin_login(payload: LoginRequest):
    user = os.getenv("ADMIN_USER", "admin")
    pwd = os.getenv("ADMIN_PASS", "admin123")
    if payload.username == user and payload.password == pwd:
        # In a real app, return JWT. Here, a simple flag token.
        return {"token": "ok"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
