"""ORM models mirroring database/schema.sql.

These exist so ETL and analytics code can work with typed Python objects
and so the schema can be created from the app when no DBA is around
(Base.metadata.create_all). schema.sql remains the source of truth for
indexes, roles and constraints that SQLAlchemy expresses less clearly.
"""
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey,
                        Integer, Numeric, SmallInteger, String, Text,
                        UniqueConstraint, BigInteger, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class UploadBatch(Base):
    __tablename__ = "upload_batch"
    batch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="pending")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EtlLog(Base):
    __tablename__ = "etl_log"
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batch.batch_id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppUser(Base):
    __tablename__ = "app_user"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DimDate(Base):
    __tablename__ = "dim_date"
    date_key: Mapped[int] = mapped_column(Integer, primary_key=True)  # yyyymmdd
    full_date: Mapped[Date] = mapped_column(Date, nullable=False, unique=True)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month_name: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    day_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)


class DimCustomer(Base):
    __tablename__ = "dim_customer"
    customer_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    segment: Mapped[str | None] = mapped_column(Text)


class DimProduct(Base):
    __tablename__ = "dim_product"
    product_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    sub_category: Mapped[str | None] = mapped_column(Text)


class DimLocation(Base):
    __tablename__ = "dim_location"
    __table_args__ = (UniqueConstraint("city", "state", "region", "country", name="uq_location"),)
    location_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, default="India")


class FactSales(Base):
    __tablename__ = "fact_sales"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_qty"),
        CheckConstraint("unit_price >= 0", name="ck_price"),
    )
    sales_key: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"), nullable=False)
    customer_key: Mapped[int] = mapped_column(ForeignKey("dim_customer.customer_key"), nullable=False)
    product_key: Mapped[int] = mapped_column(ForeignKey("dim_product.product_key"), nullable=False)
    location_key: Mapped[int] = mapped_column(ForeignKey("dim_location.location_key"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batch.batch_id", ondelete="CASCADE"))
    order_id: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price = mapped_column(Numeric(12, 2), nullable=False)
    discount = mapped_column(Numeric(5, 4), default=0)
    revenue = mapped_column(Numeric(14, 2), nullable=False)
    cost = mapped_column(Numeric(14, 2), default=0)
    profit = mapped_column(Numeric(14, 2), nullable=False)
