from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
from bson import ObjectId
import os
from jose import jwt
import hashlib
import uuid
from datetime import datetime, timedelta
import shutil

app = FastAPI(title="The Limon Restaurant API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "limon_restaurant")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# JWT Secret
JWT_SECRET = os.environ.get("JWT_SECRET", "limon-restaurant-secret-key-2024")
JWT_ALGORITHM = "HS256"

# Security
security = HTTPBearer()

# Upload directory
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic Models
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminCreate(BaseModel):
    username: str
    password: str
    role: str = "admin"

class CategoryCreate(BaseModel):
    name: str
    name_ar: str = ""
    slug: str
    image: str
    order: int = 0

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    slug: Optional[str] = None
    image: Optional[str] = None
    order: Optional[int] = None

class MenuItemCreate(BaseModel):
    title: str
    title_ar: str = ""
    description: str
    description_ar: str = ""
    price: float
    image: str
    category_id: str
    is_published: bool = True

class MenuItemUpdate(BaseModel):
    title: Optional[str] = None
    title_ar: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    category_id: Optional[str] = None
    order: Optional[int] = None
    is_published: Optional[bool] = None

class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_name_ar: Optional[str] = None
    company_subtitle: Optional[str] = None
    company_subtitle_ar: Optional[str] = None
    title_font: Optional[str] = None
    subtitle_font: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    hero_video: Optional[str] = None
    hero_image: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    address_ar: Optional[str] = None
    opening_hours: Optional[str] = None
    opening_hours_ar: Optional[str] = None
    instagram: Optional[str] = None
    google_maps: Optional[str] = None
    about_story: Optional[str] = None
    about_story_ar: Optional[str] = None
    about_mission: Optional[str] = None
    about_mission_ar: Optional[str] = None
    about_vision: Optional[str] = None
    about_vision_ar: Optional[str] = None
    default_language: Optional[str] = None
    # New fields for admin controls
    restaurant_email: Optional[str] = None
    enable_favorites: Optional[bool] = None
    enable_cart: Optional[bool] = None
    enable_menu: Optional[bool] = None
    # Data version for sync
    data_version: Optional[int] = None

class OrderCreate(BaseModel):
    table_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    items: List[dict]
    total: float
    notes: Optional[str] = None
    language: Optional[str] = "en"

class ContactMessage(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    message: str
    language: Optional[str] = "en"

# Helper functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def serialize_doc(doc):
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc

def serialize_docs(docs):
    return [serialize_doc(doc) for doc in docs]

# Initialize default data
def init_default_data():
    # Create default admin if not exists
    if db.admins.count_documents({}) == 0:
        db.admins.insert_one({
            "username": "admin",
            "password": hash_password("admin123"),
            "role": "admin",
            "created_at": datetime.utcnow()
        })
    
    # Create default settings if not exists
    if db.settings.count_documents({}) == 0:
        db.settings.insert_one({
            "company_name": "The Limon",
            "company_subtitle": "Turkish Cuisine",
            "hero_video": "hero-video-new.mp4",
            "hero_image": "menu-images/dish_01_01.jpeg",
            "phone": "+971 4 123 4567",
            "address": "Sheikh Zayed Road, Dubai, UAE",
            "opening_hours": "Daily: 8:00 AM - 11:00 PM",
            "instagram": "https://instagram.com",
            "google_maps": "https://maps.google.com",
            "about_story": "Welcome to The Limon Turkish Cuisine, where centuries-old Turkish culinary traditions meet contemporary dining excellence.",
            "about_mission": "To share the rich heritage of Turkish cuisine with our community, creating memorable dining experiences.",
            "about_vision": "To become the premier destination for Turkish cuisine, recognized for our commitment to authenticity.",
            "updated_at": datetime.utcnow()
        })
    
    # Create default categories if not exists
    if db.categories.count_documents({}) == 0:
        default_categories = [
            {"name": "Turkish Breakfast", "name_en": "Turkish Breakfast", "slug": "breakfast", "image": "menu-images/dish_01_01.jpeg", "order": 1},
            {"name": "Meze & Salad Selection", "name_en": "Meze & Salad Selection", "slug": "mezze", "image": "menu-images/dish_06_01.jpeg", "order": 2},
            {"name": "Charcoal Grill", "name_en": "Charcoal Grill", "slug": "main", "image": "menu-images/dish_09_03.jpeg", "order": 3},
            {"name": "Sweet Moments", "name_en": "Sweet Moments", "slug": "sweet", "image": "menu-images/dish_12_04.jpeg", "order": 4},
            {"name": "Kids Meal", "name_en": "Kids Meal", "slug": "kids", "image": "menu-images/dish_13_05.jpeg", "order": 5},
            {"name": "Coffee & Teas", "name_en": "Coffee & Teas", "slug": "coffee", "image": "menu-images/dish_14_01.jpeg", "order": 6},
            {"name": "Fresh Juices & Cocktails", "name_en": "Fresh Juices & Cocktails", "slug": "juices", "image": "menu-images/dish_16_01.jpeg", "order": 7},
        ]
        db.categories.insert_many(default_categories)

# Run initialization
init_default_data()

# Auth Routes
@app.post("/api/auth/login")
async def login(data: AdminLogin):
    admin = db.admins.find_one({
        "username": data.username,
        "password": hash_password(data.password)
    })
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(str(admin["_id"]), admin["username"], admin["role"])
    return {
        "token": token,
        "user": {
            "id": str(admin["_id"]),
            "username": admin["username"],
            "role": admin["role"]
        }
    }

@app.get("/api/auth/me")
async def get_me(user = Depends(verify_token)):
    return {"user": user}

@app.post("/api/auth/change-password")
async def change_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    user = Depends(verify_token)
):
    admin = db.admins.find_one({
        "_id": ObjectId(user["user_id"]),
        "password": hash_password(old_password)
    })
    if not admin:
        raise HTTPException(status_code=400, detail="Invalid old password")
    
    db.admins.update_one(
        {"_id": ObjectId(user["user_id"])},
        {"$set": {"password": hash_password(new_password)}}
    )
    return {"message": "Password changed successfully"}

# Categories Routes
@app.get("/api/categories")
async def get_categories():
    categories = list(db.categories.find().sort("order", 1))
    return {"categories": serialize_docs(categories)}

@app.post("/api/categories")
async def create_category(data: CategoryCreate, user = Depends(verify_token)):
    category = data.dict()
    category["created_at"] = datetime.utcnow()
    result = db.categories.insert_one(category)
    category["id"] = str(result.inserted_id)
    if "_id" in category:
        del category["_id"]
    return {"category": category}

@app.put("/api/categories/{category_id}")
async def update_category(category_id: str, data: CategoryUpdate, user = Depends(verify_token)):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    update_data["updated_at"] = datetime.utcnow()
    result = db.categories.update_one(
        {"_id": ObjectId(category_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    
    category = db.categories.find_one({"_id": ObjectId(category_id)})
    return {"category": serialize_doc(category)}

@app.delete("/api/categories/{category_id}")
async def delete_category(category_id: str, user = Depends(verify_token)):
    # Also delete all items in this category
    db.menu_items.delete_many({"category_id": category_id})
    result = db.categories.delete_one({"_id": ObjectId(category_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}

# Menu Items Routes
@app.get("/api/menu-items")
async def get_menu_items(category_id: Optional[str] = None, published_only: Optional[bool] = None):
    query = {}
    if category_id:
        query["category_id"] = category_id
    if published_only:
        query["is_published"] = {"$ne": False}  # Include items without is_published field (legacy) or True
    items = list(db.menu_items.find(query).sort("order", 1))
    return {"items": serialize_docs(items)}

@app.get("/api/menu-items/{item_id}")
async def get_menu_item(item_id: str):
    item = db.menu_items.find_one({"_id": ObjectId(item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": serialize_doc(item)}

@app.post("/api/menu-items")
async def create_menu_item(data: MenuItemCreate, user = Depends(verify_token)):
    item = data.dict()
    item["created_at"] = datetime.utcnow()
    result = db.menu_items.insert_one(item)
    item["id"] = str(result.inserted_id)
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    return {"item": item}

@app.put("/api/menu-items/{item_id}")
async def update_menu_item(item_id: str, data: MenuItemUpdate, user = Depends(verify_token)):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    update_data["updated_at"] = datetime.utcnow()
    result = db.menu_items.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    
    item = db.menu_items.find_one({"_id": ObjectId(item_id)})
    return {"item": serialize_doc(item)}

@app.delete("/api/menu-items/{item_id}")
async def delete_menu_item(item_id: str, user = Depends(verify_token)):
    result = db.menu_items.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    return {"message": "Item deleted"}

@app.put("/api/menu-items/{item_id}/toggle-publish")
async def toggle_publish_menu_item(item_id: str, user = Depends(verify_token)):
    item = db.menu_items.find_one({"_id": ObjectId(item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    current_status = item.get("is_published", True)
    new_status = not current_status
    
    db.menu_items.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"is_published": new_status, "updated_at": datetime.utcnow()}}
    )
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    
    return {"item_id": item_id, "is_published": new_status}

# Bulk reorder endpoints
@app.post("/api/categories/reorder")
async def reorder_categories(orders: List[dict], user = Depends(verify_token)):
    for item in orders:
        db.categories.update_one(
            {"_id": ObjectId(item["id"])},
            {"$set": {"order": item["order"]}}
        )
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    return {"message": "Categories reordered"}

@app.post("/api/menu-items/reorder")
async def reorder_menu_items(orders: List[dict], user = Depends(verify_token)):
    for item in orders:
        db.menu_items.update_one(
            {"_id": ObjectId(item["id"])},
            {"$set": {"order": item["order"]}}
        )
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    return {"message": "Menu items reordered"}

# Settings Routes
@app.get("/api/settings")
async def get_settings():
    settings = db.settings.find_one()
    if settings:
        return {"settings": serialize_doc(settings)}
    return {"settings": {}}

@app.put("/api/settings")
async def update_settings(data: SettingsUpdate, user = Depends(verify_token)):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    update_data["updated_at"] = datetime.utcnow()
    db.settings.update_one({}, {"$set": update_data}, upsert=True)
    # Update data version for sync
    db.settings.update_one({}, {"$inc": {"data_version": 1}}, upsert=True)
    settings = db.settings.find_one()
    return {"settings": serialize_doc(settings)}

# File Upload Routes
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user = Depends(verify_token)):
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"url": f"uploads/{filename}", "filename": filename}

# Public data endpoint for frontend (combines all data for offline caching)
@app.get("/api/public/data")
async def get_public_data():
    settings = db.settings.find_one()
    categories = list(db.categories.find().sort("order", 1))
    items = list(db.menu_items.find().sort("order", 1))
    
    return {
        "settings": serialize_doc(settings) if settings else {},
        "categories": serialize_docs(categories),
        "items": serialize_docs(items),
        "dataVersion": settings.get("data_version", 1) if settings else 1,
        "lastUpdated": datetime.utcnow().isoformat()
    }

# Get only data version for sync check
@app.get("/api/public/version")
async def get_data_version():
    settings = db.settings.find_one()
    return {
        "dataVersion": settings.get("data_version", 1) if settings else 1,
        "timestamp": datetime.utcnow().isoformat()
    }

# Email helper function
def send_email_notification(to_email: str, subject: str, body: str):
    """Send email notification - logs for now, integrate with email service later"""
    # Store in database for admin to see
    db.notifications.insert_one({
        "to": to_email,
        "subject": subject,
        "body": body,
        "created_at": datetime.utcnow(),
        "sent": False
    })
    print(f"Email notification queued: {subject} -> {to_email}")
    return True

# Order endpoint
@app.post("/api/orders")
async def create_order(order: OrderCreate):
    settings = db.settings.find_one()
    restaurant_email = settings.get("restaurant_email") if settings else None
    
    order_data = order.dict()
    order_data["created_at"] = datetime.utcnow()
    order_data["status"] = "pending"
    
    result = db.orders.insert_one(order_data)
    order_id = str(result.inserted_id)
    
    # Send email notification
    if restaurant_email:
        items_text = "\n".join([f"- {item.get('title', 'Item')} x{item.get('quantity', 1)} = {item.get('price', 0)} AED" for item in order.items])
        email_body = f"""
New Order Received!
-------------------
Order ID: {order_id}
Table: {order.table_number or 'N/A'}
Customer: {order.customer_name or 'N/A'}
Phone: {order.customer_phone or 'N/A'}

Items:
{items_text}

Total: {order.total} AED

Notes: {order.notes or 'None'}

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_email_notification(restaurant_email, f"New Order #{order_id[:8]}", email_body)
    
    return {"order_id": order_id, "message": "Order placed successfully"}

# Contact message endpoint
@app.post("/api/contact")
async def send_contact_message(message: ContactMessage):
    settings = db.settings.find_one()
    restaurant_email = settings.get("restaurant_email") if settings else None
    
    message_data = message.dict()
    message_data["created_at"] = datetime.utcnow()
    
    result = db.contact_messages.insert_one(message_data)
    message_data["id"] = str(result.inserted_id)
    
    # Send email notification
    if restaurant_email:
        email_body = f"""
New Contact Message!
--------------------
From: {message.name}
Phone: {message.phone or 'N/A'}
Email: {message.email or 'N/A'}
Language: {message.language}

Message:
{message.message}

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_email_notification(restaurant_email, f"Contact Message from {message.name}", email_body)
    
    return {"message": "Message sent successfully", "id": message_data["id"]}

# Get orders (admin)
@app.get("/api/orders")
async def get_orders(user = Depends(verify_token)):
    orders = list(db.orders.find().sort("created_at", -1).limit(100))
    return {"orders": serialize_docs(orders)}

# Update order status (admin)
@app.put("/api/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str, user = Depends(verify_token)):
    result = db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": f"Order status updated to {status}"}

# Delete order (admin)
@app.delete("/api/orders/{order_id}")
async def delete_order(order_id: str, user = Depends(verify_token)):
    result = db.orders.delete_one({"_id": ObjectId(order_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": "Order deleted"}

# Get contact messages (admin)  
@app.get("/api/contact-messages")
async def get_contact_messages(user = Depends(verify_token)):
    messages = list(db.contact_messages.find().sort("created_at", -1).limit(100))
    return {"messages": serialize_docs(messages)}

# Mark message as read (admin)
@app.put("/api/contact-messages/{message_id}/read")
async def mark_message_read(message_id: str, user = Depends(verify_token)):
    result = db.contact_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message marked as read"}

# Delete message (admin)
@app.delete("/api/contact-messages/{message_id}")
async def delete_message(message_id: str, user = Depends(verify_token)):
    result = db.contact_messages.delete_one({"_id": ObjectId(message_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message deleted"}

# Health check
@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
