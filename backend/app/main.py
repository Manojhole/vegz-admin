import os
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import jwt
import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, select, desc, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv()
APP_ENV = os.getenv("APP_ENV", "development").lower()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vegz_admin.db")
JWT_SECRET = os.getenv("JWT_SECRET", "local-dev-only-change-this-secret")
TOKEN_TTL_MINUTES = int(os.getenv("ADMIN_TOKEN_TTL_MINUTES", "60"))
PARTNER_ADMIN_TOKEN = os.getenv("PARTNER_ADMIN_TOKEN", "vegz-local-partner-token-change-before-production")
SHOP_SERVICE_URL = os.getenv("SHOP_SERVICE_URL", "http://host.docker.internal:8002" if APP_ENV == "development" else "").rstrip("/")
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://host.docker.internal:8001" if APP_ENV == "development" else "").rstrip("/")
if APP_ENV == "production" and (len(PARTNER_ADMIN_TOKEN) < 32 or "replace-with" in PARTNER_ADMIN_TOKEN.lower() or "change-before-production" in PARTNER_ADMIN_TOKEN or not SHOP_SERVICE_URL or not AGENT_SERVICE_URL):
    raise RuntimeError("Configure shop/agent service URLs and a unique PARTNER_ADMIN_TOKEN before production.")
if APP_ENV == "production" and (len(JWT_SECRET) < 32 or JWT_SECRET == "local-dev-only-change-this-secret"):
    raise RuntimeError("Configure a unique JWT_SECRET of at least 32 characters for production.")
engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str] = mapped_column(String(120), default="Vegz Admin")
    role: Mapped[str] = mapped_column(String(24), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ShopRecord(Base):
    __tablename__ = "managed_shops"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    owner_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(24), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    address: Mapped[str] = mapped_column(String(400), default="")
    city: Mapped[str] = mapped_column(String(100), default="Hubli", index=True)
    shop_type: Mapped[str] = mapped_column(String(20), default="vegetable", index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRecord(Base):
    __tablename__ = "managed_agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str] = mapped_column(String(24), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    vehicle_type: Mapped[str] = mapped_column(String(30), default="Bike")
    vehicle_number: Mapped[str] = mapped_column(String(24), default="")
    city: Mapped[str] = mapped_column(String(100), default="Hubli", index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductRecord(Base):
    __tablename__ = "managed_products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("managed_shops.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    category: Mapped[str] = mapped_column(String(60), default="Vegetables")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderRecord(Base):
    __tablename__ = "managed_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), default="Customer")
    customer_phone: Mapped[str] = mapped_column(String(24), default="")
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("managed_shops.id"), nullable=True, index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("managed_agents.id"), nullable=True, index=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(100), default="Hubli", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payment_status: Mapped[str] = mapped_column(String(24), default="pending")
    status: Mapped[str] = mapped_column(String(32), default="placed", index=True)
    source: Mapped[str] = mapped_column(String(40), default="admin_demo")
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerRecord(Base):
    __tablename__ = "managed_customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), default="Customer")
    phone: Mapped[str] = mapped_column(String(24), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(24), default="active")
    external_ref: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(String(250), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    admin_email: Mapped[str] = mapped_column(String(180), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


Base.metadata.create_all(bind=engine)
# Additive migration for existing installations.
with engine.begin() as connection:
    for table, columns in {
        "managed_shops": {"city": "VARCHAR(100) NOT NULL DEFAULT 'Hubli'", "shop_type": "VARCHAR(20) NOT NULL DEFAULT 'vegetable'"},
        "managed_agents": {"city": "VARCHAR(100) NOT NULL DEFAULT 'Hubli'"},
        "managed_orders": {"city": "VARCHAR(100) NOT NULL DEFAULT 'Hubli'"},
    }.items():
        existing = {column["name"] for column in inspect(engine).get_columns(table)}
        for column, sql_type in columns.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
app = FastAPI(title="Vegz Admin API", version="1.0.0", description="Central operations console API for platform administrators.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip()], allow_credentials=True, allow_methods=["GET","POST","PATCH","PUT","DELETE","OPTIONS"], allow_headers=["Authorization","Content-Type"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hash_password(password: str) -> str:
    import hashlib
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000).hex()
    return "pbkdf2_sha256$310000$%s$%s" % (salt, digest)


def _verify_password(password: str, encoded: str) -> bool:
    import hashlib, hmac
    try:
        scheme, rounds, salt, digest = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256": return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def bootstrap_admin():
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or not password: return
    if len(password) < 14: raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 14 characters.")
    with SessionLocal() as db:
        existing = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if existing is None:
            db.add(AdminUser(email=email, password_hash=_hash_password(password), full_name=os.getenv("BOOTSTRAP_ADMIN_NAME", "Platform Administrator"), role="super_admin", is_active=True))
            db.commit()
        elif APP_ENV == "development":
            # Recover a stale local SQLite volume during development only.
            existing.password_hash = _hash_password(password)
            existing.full_name = os.getenv("BOOTSTRAP_ADMIN_NAME", existing.full_name or "Platform Administrator")
            existing.is_active = True
            db.commit()


def ensure_default_settings():
    defaults = [("delivery_fee","25","Default delivery fee in INR"),("free_delivery_minimum","499","Free delivery threshold in INR"),("platform_commission_pct","5","Default shop commission percentage"),("maintenance_mode","false","Pause customer ordering"),("support_email","","Customer support contact"),("max_order_value","50000","Maximum accepted order value in INR")]
    with SessionLocal() as db:
        for key,value,description in defaults:
            if db.scalar(select(SystemSetting.id).where(SystemSetting.key == key)) is None: db.add(SystemSetting(key=key,value=value,description=description))
        db.commit()


bootstrap_admin()
ensure_default_settings()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
class ShopIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    owner_name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=24)
    email: str = Field(default="", max_length=180)
    address: str = Field(default="", max_length=400)
    city: str = Field(default="Hubli", min_length=2, max_length=100)
    shop_type: str = Field(default="vegetable", pattern=r"^(vegetable|grocery)$")
    status: str = "pending"
    is_open: bool = False
    accepts_orders: bool = False
    commission_pct: Decimal = Field(default=Decimal("5.00"), ge=0, le=100)
    external_ref: str = Field(default="", max_length=120)
class AgentIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=24)
    email: str = Field(default="", max_length=180)
    vehicle_type: str = Field(default="Bike", max_length=30)
    vehicle_number: str = Field(default="", max_length=24)
    city: str = Field(default="Hubli", min_length=2, max_length=100)
    status: str = "pending"
    is_online: bool = False
    external_ref: str = Field(default="", max_length=120)
class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    category: str = Field(default="Vegetables", max_length=60)
    shop_id: int | None = None
    price: Decimal = Field(gt=0, le=1000000)
    stock_qty: int = Field(default=0, ge=0, le=10000000)
    status: str = "pending"
    external_ref: str = Field(default="", max_length=120)
class OrderIn(BaseModel):
    public_code: str = Field(min_length=3, max_length=40)
    customer_name: str = Field(default="Customer", max_length=120)
    customer_phone: str = Field(default="", max_length=24)
    shop_id: int | None = None
    agent_id: int | None = None
    address: str = Field(default="", max_length=500)
    city: str = Field(default="Hubli", min_length=2, max_length=100)
    total_amount: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("10000000"))
    payment_status: str = "pending"
    status: str = "placed"
    source: str = Field(default="admin_demo", max_length=40)
    external_ref: str = Field(default="", max_length=120)
class SettingIn(BaseModel):
    value: str = Field(max_length=500)
class EntityStatus(BaseModel):
    status: str = Field(min_length=2, max_length=32)
class AssignmentIn(BaseModel):
    agent_id: int
class CustomerIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=24)
    email: str = Field(default="", max_length=180)
    status: str = "active"
    external_ref: str = Field(default="", max_length=120)
class AdminUserIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=14, max_length=200)
    role: str = "operations"


def require_admin(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> AdminUser:
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(status_code=401, detail="Please sign in as a platform administrator.")
    try:
        payload = jwt.decode(authorization.split(" ",1)[1].strip(), JWT_SECRET, algorithms=["HS256"])
        admin_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError): raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    admin = db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active: raise HTTPException(status_code=401, detail="Administrator account is inactive.")
    return admin


def require_super_admin(admin: AdminUser = Depends(require_admin)) -> AdminUser:
    if admin.role != "super_admin": raise HTTPException(status_code=403, detail="Super administrator permission required.")
    return admin


def _audit(db: Session, admin: AdminUser, action: str, entity_type: str, entity_id: Any = "", detail: str = ""):
    db.add(AuditLog(admin_id=admin.id, admin_email=admin.email, action=action, entity_type=entity_type, entity_id=str(entity_id), detail=detail[:4000]))


def _shop(o: ShopRecord):
    return {"id":o.id,"name":o.name,"owner_name":o.owner_name,"phone":o.phone,"email":o.email,"address":o.address,"city":o.city,"shop_type":o.shop_type,"status":o.status,"is_open":o.is_open,"accepts_orders":o.accepts_orders,"commission_pct":float(o.commission_pct),"external_ref":o.external_ref,"created_at":o.created_at.isoformat()+"Z","updated_at":o.updated_at.isoformat()+"Z"}
def _agent(o: AgentRecord):
    return {"id":o.id,"full_name":o.full_name,"phone":o.phone,"email":o.email,"vehicle_type":o.vehicle_type,"vehicle_number":o.vehicle_number,"city":o.city,"status":o.status,"is_online":o.is_online,"external_ref":o.external_ref,"created_at":o.created_at.isoformat()+"Z","updated_at":o.updated_at.isoformat()+"Z"}
def _product(o: ProductRecord):
    return {"id":o.id,"shop_id":o.shop_id,"name":o.name,"category":o.category,"price":float(o.price),"stock_qty":o.stock_qty,"status":o.status,"external_ref":o.external_ref,"created_at":o.created_at.isoformat()+"Z","updated_at":o.updated_at.isoformat()+"Z"}
def _order(o: OrderRecord):
    return {"id":o.id,"public_code":o.public_code,"customer_name":o.customer_name,"customer_phone":o.customer_phone,"shop_id":o.shop_id,"agent_id":o.agent_id,"address":o.address,"city":o.city,"total_amount":float(o.total_amount),"payment_status":o.payment_status,"status":o.status,"source":o.source,"external_ref":o.external_ref,"created_at":o.created_at.isoformat()+"Z","updated_at":o.updated_at.isoformat()+"Z"}
def _customer(o: CustomerRecord):
    return {"id":o.id,"full_name":o.full_name,"phone":o.phone,"email":o.email,"status":o.status,"external_ref":o.external_ref,"created_at":o.created_at.isoformat()+"Z"}
def _admin_user(o: AdminUser):
    return {"id":o.id,"email":o.email,"full_name":o.full_name,"role":o.role,"is_active":o.is_active,"last_login_at":o.last_login_at.isoformat()+"Z" if o.last_login_at else None,"created_at":o.created_at.isoformat()+"Z"}


def _require_partner_token(authorization: str | None):
    expected = PARTNER_ADMIN_TOKEN
    supplied = authorization.split(" ", 1)[1].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if len(expected) < 32 or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Partner registration authentication failed.")


@app.post("/api/internal/partner-requests/shop", status_code=201)
def partner_shop_request(payload: dict[str, Any], authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_partner_token(authorization)
    phone = str(payload.get("phone", "")).strip()
    if len(phone) < 8: raise HTTPException(status_code=422, detail="Valid owner phone is required.")
    city = " ".join(str(payload.get("city", "Hubli")).split()).title()
    shop_type = str(payload.get("shop_type", "vegetable"))
    if shop_type not in {"vegetable", "grocery"}: raise HTTPException(status_code=422, detail="Invalid shop type.")
    obj = db.scalar(select(ShopRecord).where(ShopRecord.phone == phone))
    if obj is None:
        duplicate = db.scalar(select(ShopRecord).where(func.lower(ShopRecord.city) == city.casefold(), ShopRecord.shop_type == shop_type, ShopRecord.status.in_(["pending", "approved"])))
        if duplicate is not None and duplicate.phone != phone:
            raise HTTPException(status_code=409, detail=f"A {shop_type} shop is already registered or pending in {city}.")
        obj = ShopRecord(name=str(payload.get("name") or "My Vegz Shop"), owner_name=str(payload.get("owner_name") or ""), phone=phone, city=city, shop_type=shop_type, address=str(payload.get("address") or ""), status="pending", is_open=False, accepts_orders=False, external_ref=str(payload.get("external_ref") or ""))
        db.add(obj)
    else:
        obj.name = str(payload.get("name") or obj.name); obj.city = city; obj.shop_type = shop_type
        obj.address = str(payload.get("address") or obj.address); obj.external_ref = str(payload.get("external_ref") or obj.external_ref)
    db.commit(); db.refresh(obj)
    return _shop(obj)


@app.post("/api/internal/partner-requests/agent", status_code=201)
def partner_agent_request(payload: dict[str, Any], authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_partner_token(authorization)
    phone = str(payload.get("phone", "")).strip()
    if len(phone) < 8: raise HTTPException(status_code=422, detail="Valid agent phone is required.")
    obj = db.scalar(select(AgentRecord).where(AgentRecord.phone == phone))
    if obj is None:
        obj = AgentRecord(full_name=str(payload.get("full_name") or "Delivery Partner"), phone=phone, city=" ".join(str(payload.get("city", "Hubli")).split()).title(), vehicle_type=str(payload.get("vehicle_type") or "Bike"), vehicle_number=str(payload.get("vehicle_number") or ""), status="pending", is_online=False, external_ref=str(payload.get("external_ref") or ""))
        db.add(obj)
    else:
        obj.full_name = str(payload.get("full_name") or obj.full_name); obj.city = " ".join(str(payload.get("city", obj.city)).split()).title()
        obj.vehicle_type = str(payload.get("vehicle_type") or obj.vehicle_type); obj.external_ref = str(payload.get("external_ref") or obj.external_ref)
    db.commit(); db.refresh(obj)
    return _agent(obj)


def _sync_partner_approval(kind: str, phone: str, status_value: str):
    base = SHOP_SERVICE_URL if kind == "shop" else AGENT_SERVICE_URL
    token = PARTNER_ADMIN_TOKEN
    if not base:
        if APP_ENV == "production":
            raise HTTPException(status_code=503, detail=f"{kind.title()} service URL is not configured; approval was not saved.")
        return
    try:
        response = httpx.post(base + "/api/internal/admin-approval", headers={"Authorization": "Bearer " + token}, json={"phone": phone, "status": status_value}, timeout=6.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not sync {kind} approval to its service; approval was not saved.") from exc


@app.get("/api/health")
def health(): return {"status":"ok","service":"vegz-admin-api"}
@app.post("/api/auth/login")
def login(payload:LoginIn,db:Session=Depends(get_db)):
    admin=db.scalar(select(AdminUser).where(AdminUser.email==str(payload.email).lower()))
    if admin is None or not admin.is_active or not _verify_password(payload.password,admin.password_hash): raise HTTPException(status_code=401,detail="Email or password is incorrect.")
    admin.last_login_at=datetime.utcnow();db.commit()
    token=jwt.encode({"sub":str(admin.id),"role":admin.role,"exp":datetime.utcnow()+timedelta(minutes=TOKEN_TTL_MINUTES)},JWT_SECRET,algorithm="HS256")
    return {"access_token":token,"token_type":"bearer","expires_in":TOKEN_TTL_MINUTES*60,"admin":_admin_user(admin)}
@app.get("/api/auth/me")
def auth_me(admin:AdminUser=Depends(require_admin)):return _admin_user(admin)


@app.get("/api/dashboard")
def dashboard(admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    today=datetime.utcnow().date()
    return {"shops":{"total":db.scalar(select(func.count(ShopRecord.id))) or 0,"pending":db.scalar(select(func.count(ShopRecord.id)).where(ShopRecord.status=="pending")) or 0,"active":db.scalar(select(func.count(ShopRecord.id)).where(ShopRecord.status=="approved")) or 0},
    "agents":{"total":db.scalar(select(func.count(AgentRecord.id))) or 0,"pending":db.scalar(select(func.count(AgentRecord.id)).where(AgentRecord.status=="pending")) or 0,"online":db.scalar(select(func.count(AgentRecord.id)).where(AgentRecord.is_online.is_(True),AgentRecord.status=="approved")) or 0},
    "products":{"total":db.scalar(select(func.count(ProductRecord.id))) or 0,"pending":db.scalar(select(func.count(ProductRecord.id)).where(ProductRecord.status=="pending")) or 0},
    "orders":{"total":db.scalar(select(func.count(OrderRecord.id))) or 0,"active":db.scalar(select(func.count(OrderRecord.id)).where(OrderRecord.status.not_in(["delivered","cancelled","refunded"]))) or 0,"today":(db.scalar(select(func.count(OrderRecord.id)).where(func.date(OrderRecord.created_at)==str(today))) or 0),"gross_sales_today":float(db.scalar(select(func.coalesce(func.sum(OrderRecord.total_amount),0)).where(func.date(OrderRecord.created_at)==str(today),OrderRecord.status!="cancelled")) or 0)},
    "recent_orders":[_order(o) for o in db.scalars(select(OrderRecord).order_by(desc(OrderRecord.created_at)).limit(6)).all()],
    "recent_audit":[{"admin_email":x.admin_email,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"created_at":x.created_at.isoformat()+"Z"} for x in db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(6)).all()],
    "operational_note":"Metrics represent this admin service database. Connect shared Vegz APIs for live production metrics."}


@app.get("/api/shops")
def list_shops(status_filter:str|None=None,q:str|None=Query(default=None,max_length=120),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(ShopRecord).order_by(desc(ShopRecord.created_at))
    if status_filter:query=query.where(ShopRecord.status==status_filter)
    if q:
        term="%"+q.strip()+"%";query=query.where(ShopRecord.name.ilike(term)|ShopRecord.owner_name.ilike(term)|ShopRecord.phone.ilike(term))
    return [_shop(x) for x in db.scalars(query.limit(500)).all()]
@app.post("/api/shops",status_code=201)
def create_shop(payload:ShopIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    if payload.status not in {"pending","approved","suspended","rejected"}:raise HTTPException(status_code=422,detail="Invalid shop status.")
    city=" ".join(payload.city.split()).title()
    duplicate=db.scalar(select(ShopRecord.id).where(func.lower(ShopRecord.city)==city.casefold(),ShopRecord.shop_type==payload.shop_type))
    if duplicate is not None:raise HTTPException(status_code=409,detail=f"A {payload.shop_type} shop is already registered for {city}.")
    values=payload.model_dump();values["city"]=city
    obj=ShopRecord(**values)
    if obj.status!="approved":obj.is_open=False;obj.accepts_orders=False
    db.add(obj);db.flush();_audit(db,admin,"create","shop",obj.id,"Created shop "+obj.name);db.commit();db.refresh(obj);return _shop(obj)
@app.patch("/api/shops/{shop_id}")
def patch_shop(shop_id:int,payload:dict[str,Any],admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"name","owner_name","phone","email","address","city","shop_type","status","is_open","accepts_orders","commission_pct","external_ref"}
    if not payload or set(payload)-allowed:raise HTTPException(status_code=422,detail="Provide only supported shop fields.")
    obj=db.get(ShopRecord,shop_id)
    if obj is None:raise HTTPException(status_code=404,detail="Shop not found.")
    if "status" in payload and payload["status"] not in {"pending","approved","suspended","rejected"}:
        raise HTTPException(status_code=422,detail="Invalid shop status.")
    if "commission_pct" in payload:
        try:
            pct=Decimal(str(payload["commission_pct"]))
            if pct<0 or pct>100: raise ValueError()
            payload["commission_pct"]=pct
        except Exception: raise HTTPException(status_code=422,detail="Commission must be between 0 and 100.")
    if "status" in payload and payload["status"] != obj.status:
        _sync_partner_approval("shop", obj.phone, payload["status"])
    for key,value in payload.items():setattr(obj,key,value)
    if obj.status!="approved":obj.is_open=False;obj.accepts_orders=False
    obj.updated_at=datetime.utcnow();_audit(db,admin,"update","shop",obj.id,"Updated fields="+",".join(payload.keys()));db.commit();db.refresh(obj);return _shop(obj)


@app.get("/api/agents")
def list_agents(status_filter:str|None=None,q:str|None=Query(default=None,max_length=120),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(AgentRecord).order_by(desc(AgentRecord.created_at))
    if status_filter:query=query.where(AgentRecord.status==status_filter)
    if q:
        term="%"+q.strip()+"%";query=query.where(AgentRecord.full_name.ilike(term)|AgentRecord.phone.ilike(term)|AgentRecord.vehicle_number.ilike(term))
    return [_agent(x) for x in db.scalars(query.limit(500)).all()]
@app.post("/api/agents",status_code=201)
def create_agent(payload:AgentIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    if payload.status not in {"pending","approved","suspended","rejected"}:raise HTTPException(status_code=422,detail="Invalid agent status.")
    values=payload.model_dump();values["city"]=" ".join(payload.city.split()).title()
    obj=AgentRecord(**values)
    if obj.status!="approved":obj.is_online=False
    db.add(obj);db.flush();_audit(db,admin,"create","agent",obj.id,"Created agent "+obj.full_name);db.commit();db.refresh(obj);return _agent(obj)
@app.patch("/api/agents/{agent_id}")
def patch_agent(agent_id:int,payload:dict[str,Any],admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"full_name","phone","email","vehicle_type","vehicle_number","city","status","is_online","external_ref"}
    if not payload or set(payload)-allowed:raise HTTPException(status_code=422,detail="Provide only supported agent fields.")
    obj=db.get(AgentRecord,agent_id)
    if obj is None:raise HTTPException(status_code=404,detail="Agent not found.")
    if "status" in payload and payload["status"] not in {"pending","approved","suspended","rejected"}:
        raise HTTPException(status_code=422,detail="Invalid agent status.")
    if "status" in payload and payload["status"] != obj.status:
        _sync_partner_approval("agent", obj.phone, payload["status"])
    for key,value in payload.items():setattr(obj,key,value)
    if obj.status!="approved":obj.is_online=False
    obj.updated_at=datetime.utcnow();_audit(db,admin,"update","agent",obj.id,"Updated fields="+",".join(payload.keys()));db.commit();db.refresh(obj);return _agent(obj)


@app.get("/api/products")
def list_products(status_filter:str|None=None,q:str|None=Query(default=None,max_length=120),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(ProductRecord).order_by(desc(ProductRecord.created_at))
    if status_filter:query=query.where(ProductRecord.status==status_filter)
    if q:query=query.where(ProductRecord.name.ilike("%"+q.strip()+"%"))
    return [_product(x) for x in db.scalars(query.limit(500)).all()]
@app.post("/api/products",status_code=201)
def create_product(payload:ProductIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    if payload.shop_id is not None and db.get(ShopRecord,payload.shop_id) is None:raise HTTPException(status_code=404,detail="Shop not found.")
    if payload.status not in {"pending","approved","blocked"}:raise HTTPException(status_code=422,detail="Invalid product status.")
    obj=ProductRecord(**payload.model_dump());db.add(obj);db.flush();_audit(db,admin,"create","product",obj.id,"Created product "+obj.name);db.commit();db.refresh(obj);return _product(obj)
@app.patch("/api/products/{product_id}")
def patch_product(product_id:int,payload:dict[str,Any],admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"name","category","shop_id","price","stock_qty","status","external_ref"}
    if not payload or set(payload)-allowed:raise HTTPException(status_code=422,detail="Provide only supported product fields.")
    obj=db.get(ProductRecord,product_id)
    if obj is None:raise HTTPException(status_code=404,detail="Product not found.")
    if "status" in payload and payload["status"] not in {"pending","approved","blocked"}:
        raise HTTPException(status_code=422,detail="Invalid product status.")
    if "shop_id" in payload and payload["shop_id"] is not None and db.get(ShopRecord,payload["shop_id"]) is None:
        raise HTTPException(status_code=404,detail="Shop not found.")
    if "price" in payload:
        try:
            price=Decimal(str(payload["price"]))
            if price<=0 or price>Decimal("1000000"): raise ValueError()
            payload["price"]=price
        except Exception: raise HTTPException(status_code=422,detail="Product price must be positive and within the allowed range.")
    if "stock_qty" in payload and (not isinstance(payload["stock_qty"],int) or payload["stock_qty"]<0 or payload["stock_qty"]>10000000):
        raise HTTPException(status_code=422,detail="Stock quantity must be a non-negative whole number.")
    for key,value in payload.items():setattr(obj,key,value)
    obj.updated_at=datetime.utcnow();_audit(db,admin,"update","product",obj.id,"Updated fields="+",".join(payload.keys()));db.commit();db.refresh(obj);return _product(obj)


@app.get("/api/orders")
def list_orders(status_filter:str|None=None,q:str|None=Query(default=None,max_length=120),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(OrderRecord).order_by(desc(OrderRecord.created_at))
    if status_filter:query=query.where(OrderRecord.status==status_filter)
    if q:query=query.where(OrderRecord.public_code.ilike("%"+q.strip()+"%")|OrderRecord.customer_name.ilike("%"+q.strip()+"%"))
    return [_order(x) for x in db.scalars(query.limit(1000)).all()]
@app.post("/api/orders",status_code=201)
def create_order(payload:OrderIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    if db.scalar(select(OrderRecord.id).where(OrderRecord.public_code==payload.public_code)) is not None:raise HTTPException(status_code=409,detail="Order code already exists.")
    if payload.shop_id is not None and db.get(ShopRecord,payload.shop_id) is None:raise HTTPException(status_code=404,detail="Shop not found.")
    if payload.agent_id is not None:
        agent=db.get(AgentRecord,payload.agent_id)
        if agent is None or agent.status!="approved":raise HTTPException(status_code=422,detail="Assigned agent must exist and be approved.")
    if payload.payment_status not in {"pending","paid","failed","refunded"}:raise HTTPException(status_code=422,detail="Invalid payment status.")
    if payload.status not in {"placed","confirmed","preparing","ready_for_pickup","assigned","picked_up","out_for_delivery","delivered","delivery_failed","cancelled","refunded"}:raise HTTPException(status_code=422,detail="Invalid order status.")
    if payload.status=="assigned" and payload.agent_id is None:raise HTTPException(status_code=422,detail="Assigned orders must have an agent.")
    obj=OrderRecord(**payload.model_dump());db.add(obj);db.flush();_audit(db,admin,"create","order",obj.id,"Created order "+obj.public_code);db.commit();db.refresh(obj);return _order(obj)
@app.patch("/api/orders/{order_id}")
def patch_order(order_id:int,payload:dict[str,Any],admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed_fields={"customer_name","customer_phone","shop_id","agent_id","address","city","total_amount","payment_status","status","source","external_ref"}
    if not payload or set(payload)-allowed_fields:
        raise HTTPException(status_code=422,detail="Provide only supported order fields; use the status endpoint for workflow transitions.")
    obj=db.get(OrderRecord,order_id)
    if obj is None: raise HTTPException(status_code=404,detail="Order not found.")
    if "shop_id" in payload and payload["shop_id"] is not None and db.get(ShopRecord,payload["shop_id"]) is None:
        raise HTTPException(status_code=404,detail="Shop not found.")
    if "agent_id" in payload and payload["agent_id"] is not None:
        candidate=db.get(AgentRecord,payload["agent_id"])
        if candidate is None or candidate.status!="approved":
            raise HTTPException(status_code=422,detail="Assigned agent must exist and be approved.")
    if "total_amount" in payload:
        try:
            value=Decimal(str(payload["total_amount"]))
            if value<0 or value>Decimal("10000000"): raise ValueError()
            payload["total_amount"]=value
        except Exception:
            raise HTTPException(status_code=422,detail="Order total is outside the allowed range.")
    if "payment_status" in payload and payload["payment_status"] not in {"pending","paid","failed","refunded"}:
        raise HTTPException(status_code=422,detail="Invalid payment status.")
    if "status" in payload:
        transitions={"placed":{"confirmed","cancelled"},"confirmed":{"preparing","cancelled"},"preparing":{"ready_for_pickup","cancelled"},"ready_for_pickup":{"cancelled"},"assigned":{"picked_up","cancelled"},"picked_up":{"out_for_delivery","cancelled"},"out_for_delivery":{"delivered","delivery_failed"},"delivery_failed":{"cancelled"},"delivered":{"refunded"},"cancelled":set(),"refunded":set()}
        desired=str(payload["status"]).strip().lower()
        if desired != obj.status and desired not in transitions.get(obj.status,set()):
            raise HTTPException(status_code=409,detail=f"Cannot transition {obj.status} to {desired}.")
        payload["status"]=desired
    for key,value in payload.items(): setattr(obj,key,value)
    obj.updated_at=datetime.utcnow()
    _audit(db,admin,"update","order",obj.id,"Updated fields="+",".join(payload.keys()))
    db.commit();db.refresh(obj);return _order(obj)


@app.patch("/api/orders/{order_id}/status")
def patch_order_status(order_id:int,payload:EntityStatus,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"placed":{"confirmed","cancelled"},"confirmed":{"preparing","cancelled"},"preparing":{"ready_for_pickup","cancelled"},"ready_for_pickup":{"cancelled"},"assigned":{"picked_up","cancelled"},"picked_up":{"out_for_delivery","cancelled"},"out_for_delivery":{"delivered","delivery_failed"},"delivery_failed":{"cancelled"},"delivered":{"refunded"},"cancelled":set(),"refunded":set()}
    obj=db.get(OrderRecord,order_id)
    if obj is None:raise HTTPException(status_code=404,detail="Order not found.")
    nxt=payload.status.strip().lower()
    if nxt not in allowed.get(obj.status,set()):raise HTTPException(status_code=409,detail=f"Cannot transition {obj.status} to {nxt}.")
    old=obj.status;obj.status=nxt;obj.updated_at=datetime.utcnow();_audit(db,admin,"status_change","order",obj.id,f"{old} -> {nxt}");db.commit();db.refresh(obj);return _order(obj)
@app.post("/api/orders/{order_id}/assign")
def assign_order(order_id:int,payload:AssignmentIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    obj=db.get(OrderRecord,order_id);agent=db.get(AgentRecord,payload.agent_id)
    if obj is None:raise HTTPException(status_code=404,detail="Order not found.")
    if agent is None or agent.status!="approved":raise HTTPException(status_code=422,detail="Agent must be approved before receiving orders.")
    if not agent.is_online:raise HTTPException(status_code=409,detail="Only an online agent can receive a delivery assignment.")
    if "city" in obj.__dict__ and "city" in agent.__dict__ and " ".join(agent.city.split()).casefold() != " ".join(obj.city.split()).casefold():
        raise HTTPException(status_code=409,detail="Agent and order must belong to the same city.")
    if obj.status not in {"ready_for_pickup","delivery_failed","assigned"}:raise HTTPException(status_code=409,detail="Order must be ready for pickup or awaiting reassignment.")
    old=obj.agent_id;obj.agent_id=agent.id;obj.status="assigned";obj.updated_at=datetime.utcnow();_audit(db,admin,"assign","order",obj.id,f"Agent {old} -> {agent.id}");db.commit();db.refresh(obj);return _order(obj)


@app.get("/api/customers")
def list_customers(q:str|None=Query(default=None,max_length=120),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    query=select(CustomerRecord).order_by(desc(CustomerRecord.created_at))
    if q:
        term="%"+q.strip()+"%";query=query.where(CustomerRecord.full_name.ilike(term)|CustomerRecord.phone.ilike(term)|CustomerRecord.email.ilike(term))
    return [_customer(x) for x in db.scalars(query.limit(1000)).all()]
@app.post("/api/customers",status_code=201)
def create_customer(payload:CustomerIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    obj=CustomerRecord(**payload.model_dump());db.add(obj);db.flush();_audit(db,admin,"create","customer",obj.id,"Created customer record");db.commit();db.refresh(obj);return _customer(obj)
@app.patch("/api/customers/{customer_id}")
def patch_customer(customer_id:int,payload:dict[str,Any],admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"full_name","phone","email","status","external_ref"}
    if not payload or set(payload)-allowed:raise HTTPException(status_code=422,detail="Provide only supported customer fields.")
    obj=db.get(CustomerRecord,customer_id)
    if obj is None:raise HTTPException(status_code=404,detail="Customer not found.")
    if "status" in payload and payload["status"] not in {"active","suspended","blocked"}:
        raise HTTPException(status_code=422,detail="Invalid customer status.")
    for key,value in payload.items():setattr(obj,key,value)
    _audit(db,admin,"update","customer",obj.id,"Updated fields="+",".join(payload.keys()));db.commit();db.refresh(obj);return _customer(obj)


@app.get("/api/settings")
def list_settings(admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    return [{"key":x.key,"value":x.value,"description":x.description,"updated_at":x.updated_at.isoformat()+"Z"} for x in db.scalars(select(SystemSetting).order_by(SystemSetting.key)).all()]
@app.patch("/api/settings/{key}")
def update_setting(key:str,payload:SettingIn,admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    allowed={"delivery_fee","free_delivery_minimum","platform_commission_pct","maintenance_mode","support_email","max_order_value"}
    if key not in allowed:raise HTTPException(status_code=404,detail="Setting not found or not editable.")
    obj=db.scalar(select(SystemSetting).where(SystemSetting.key==key))
    if obj is None:raise HTTPException(status_code=404,detail="Setting not found.")
    if key in {"delivery_fee","free_delivery_minimum","platform_commission_pct","max_order_value"}:
        try:
            value=Decimal(payload.value)
            if value<0 or (key=="platform_commission_pct" and value>100):raise ValueError()
        except Exception:raise HTTPException(status_code=422,detail="Enter a valid non-negative numeric value.")
    if key=="maintenance_mode" and payload.value.lower() not in {"true","false"}:raise HTTPException(status_code=422,detail="Use true or false.")
    old=obj.value;obj.value=payload.value.strip();obj.updated_at=datetime.utcnow();_audit(db,admin,"setting_change","setting",key,f"{old} -> {obj.value}");db.commit();db.refresh(obj)
    return {"key":obj.key,"value":obj.value,"description":obj.description,"updated_at":obj.updated_at.isoformat()+"Z"}


@app.get("/api/audit")
def list_audit(limit:int=Query(default=100,ge=1,le=500),admin:AdminUser=Depends(require_admin),db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)).all()
    return [{"id":x.id,"admin_email":x.admin_email,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"detail":x.detail,"ip_address":x.ip_address,"created_at":x.created_at.isoformat()+"Z"} for x in rows]
@app.get("/api/admin-users")
def list_admin_users(admin:AdminUser=Depends(require_super_admin),db:Session=Depends(get_db)):
    return [_admin_user(x) for x in db.scalars(select(AdminUser).order_by(AdminUser.email)).all()]
@app.post("/api/admin-users",status_code=201)
def create_admin_user(payload:AdminUserIn,admin:AdminUser=Depends(require_super_admin),db:Session=Depends(get_db)):
    if payload.role not in {"operations","support","finance","admin"}:raise HTTPException(status_code=422,detail="Invalid subordinate admin role.")
    email=str(payload.email).lower()
    if db.scalar(select(AdminUser.id).where(AdminUser.email==email)) is not None:raise HTTPException(status_code=409,detail="Administrator email already exists.")
    obj=AdminUser(email=email,full_name=payload.full_name,password_hash=_hash_password(payload.password),role=payload.role,is_active=True);db.add(obj);db.flush();_audit(db,admin,"create","admin_user",obj.id,f"Created {payload.role} account");db.commit();db.refresh(obj);return _admin_user(obj)
@app.patch("/api/admin-users/{user_id}/active")
def set_admin_user_active(user_id:int,payload:dict[str,bool],admin:AdminUser=Depends(require_super_admin),db:Session=Depends(get_db)):
    if set(payload)!={"is_active"}:raise HTTPException(status_code=422,detail="Provide is_active only.")
    obj=db.get(AdminUser,user_id)
    if obj is None:raise HTTPException(status_code=404,detail="Administrator not found.")
    if obj.id==admin.id and not payload["is_active"]:raise HTTPException(status_code=409,detail="You cannot deactivate your own account.")
    obj.is_active=payload["is_active"];_audit(db,admin,"admin_activation","admin_user",obj.id,f"is_active={obj.is_active}");db.commit();db.refresh(obj);return _admin_user(obj)


@app.post("/api/dev/seed")
def seed_demo_data(admin:AdminUser=Depends(require_super_admin),db:Session=Depends(get_db)):
    if db.scalar(select(ShopRecord.id).limit(1)) is not None:return {"message":"Demo records already exist."}
    shop1=ShopRecord(name="Green Basket Market",owner_name="Ramesh Patil",phone="+919900000001",address="12 Market Road, Main Bazaar",status="approved",is_open=True,accepts_orders=True)
    shop2=ShopRecord(name="Daily Fresh Vegetables",owner_name="Sonal Kulkarni",phone="+919900000002",address="5 Station Cross, Vegetable Market",status="pending")
    agent1=AgentRecord(full_name="Rahul Delivery",phone="+919900000011",vehicle_type="Bike",vehicle_number="KA 01 AB 1234",status="approved",is_online=True)
    agent2=AgentRecord(full_name="Priya Courier",phone="+919900000012",vehicle_type="Scooter",status="pending")
    customer=CustomerRecord(full_name="Ananya Rao",phone="+919900000021",status="active")
    db.add_all([shop1,shop2,agent1,agent2,customer]);db.flush()
    db.add_all([ProductRecord(shop_id=shop1.id,name="Tomato",category="Daily essentials",price=Decimal("32.00"),stock_qty=40,status="approved"),ProductRecord(shop_id=shop1.id,name="Fresh Spinach",category="Leafy greens",price=Decimal("20.00"),stock_qty=0,status="pending")])
    db.add_all([OrderRecord(public_code="VGZ-ADMIN-DEMO-1001",customer_name=customer.full_name,customer_phone=customer.phone,shop_id=shop1.id,agent_id=agent1.id,address="24 Lake View Street, Ward 3",total_amount=Decimal("168.00"),payment_status="pending",status="out_for_delivery",source="admin_demo"),OrderRecord(public_code="VGZ-ADMIN-DEMO-1002",customer_name="Rahul Patil",customer_phone="+919900000022",shop_id=shop2.id,address="Flat 3B, Shanti Residency",total_amount=Decimal("92.00"),payment_status="pending",status="placed",source="admin_demo")])
    _audit(db,admin,"seed_demo","system","demo","Created sample shops, agents, products, customers and orders");db.commit();return {"message":"Sample operational records created."}


frontend_dir=Path(__file__).resolve().parents[2]/"frontend"
if frontend_dir.exists():app.mount("/",StaticFiles(directory=str(frontend_dir),html=True),name="frontend")
