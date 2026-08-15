"""
Dataclasses describing the shape of one row in each star-schema table.

These are NOT used to hold the actual data during the pipeline run (that
job is done by pandas DataFrames, which are much faster for thousands of
rows). Instead, they exist as clear, typed documentation: if you want to
know exactly which columns dim_product has and what type each one is,
read the DimProduct class below instead of hunting through transform.py.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class DimDate:
    """One calendar day, with the pre-computed parts (month, quarter, ...)
    that analytical queries group and filter by."""

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
    """One product, with its category NAME already attached (denormalized)
    so queries never need to join back to a separate categories table."""

    product_key: int  # surrogate key
    product_id: int  # original id from the OLTP source
    sku: str
    name: str
    category: str
    unit_cost: float
    price: float


@dataclass
class DimCustomer:
    """One customer."""

    customer_key: int  # surrogate key
    customer_id: int
    name: str
    city: str
    country: str


@dataclass
class DimChannel:
    """One sales channel (e.g. Web Store, Mobile App)."""

    channel_key: int  # surrogate key
    channel_id: int
    name: str


@dataclass
class FactSale:
    """
    One row per order item (the fact table's grain).

    Holds foreign keys pointing at the four dimensions, plus the measures
    (the numbers you sum/average in analytical queries).
    """

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
