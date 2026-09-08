"""
Dataclasses describing the columns of each star-schema table. Used as
documentation/reference - the pipeline itself moves data around as
pandas DataFrames, not instances of these classes.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class DimDate:
    date_key: int  # YYYYMMDD, e.g. 20250314
    full_date: date
    day: int
    month: int
    month_name: str
    quarter: int
    year: int
    weekday: str


@dataclass
class DimProduct:
    product_key: int  # surrogate key
    product_id: int  # original id from the OLTP source
    sku: str
    name: str
    category: str  # denormalized from the categories table
    unit_cost: float
    price: float


@dataclass
class DimCustomer:
    customer_key: int  # surrogate key
    customer_id: int
    name: str
    city: str
    country: str


@dataclass
class DimChannel:
    channel_key: int  # surrogate key
    channel_id: int
    name: str


@dataclass
class FactSale:
    """One row per order item - the fact table's grain."""

    sale_key: int
    date_key: int
    product_key: int
    customer_key: int
    channel_key: int
    quantity: int
    gross_amount: float  # quantity * unit_price
    discount_amount: float  # gross_amount * discount
    net_amount: float  # gross_amount - discount_amount
    cost_amount: float  # quantity * unit_cost
    margin: float  # net_amount - cost_amount
