"""
Transform step: turns the normalized OLTP DataFrames into the star
schema - four dimension tables plus one fact table.
"""

import pandas as pd


class Transformer:
    """Builds the star-schema dimension and fact tables from raw OLTP data."""

    def build_dim_date(self, orders_df):
        """One row per distinct order date, broken down into day/month/quarter/etc."""
        unique_dates = pd.to_datetime(orders_df["order_date"]).dt.normalize().unique()
        unique_dates = sorted(unique_dates)

        rows = []
        for raw_date in unique_dates:
            date_value = pd.Timestamp(raw_date)
            date_key = int(date_value.strftime("%Y%m%d"))
            rows.append(
                {
                    "date_key": date_key,
                    "full_date": date_value.date(),
                    "day": date_value.day,
                    "month": date_value.month,
                    "month_name": date_value.strftime("%B"),
                    "quarter": date_value.quarter,
                    "year": date_value.year,
                    "weekday": date_value.strftime("%A"),
                }
            )
        return pd.DataFrame(rows)

    def build_dim_product(self, products_df, categories_df):
        # denormalize: copy the category name onto the product row
        categories_renamed = categories_df.rename(columns={"name": "category"})
        merged = products_df.merge(categories_renamed, on="category_id", how="left")

        dim_product = merged[["product_id", "sku", "name", "category", "unit_cost", "price"]].copy()
        dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))
        return dim_product

    def build_dim_customer(self, customers_df):
        dim_customer = customers_df[["customer_id", "name", "city", "country"]].copy()
        dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))
        return dim_customer

    def build_dim_channel(self, channels_df):
        dim_channel = channels_df[["channel_id", "name"]].copy()
        dim_channel.insert(0, "channel_key", range(1, len(dim_channel) + 1))
        return dim_channel

    def build_fact_sales(self, order_items_df, orders_df, dim_date, dim_product, dim_customer, dim_channel):
        # only completed orders count as sales
        completed_orders = orders_df[orders_df["status"] == "completed"]
        fact = order_items_df.merge(completed_orders, on="order_id", how="inner")

        fact["date_key"] = pd.to_datetime(fact["order_date"]).dt.strftime("%Y%m%d").astype(int)

        fact = fact.merge(dim_product[["product_id", "product_key", "unit_cost"]], on="product_id", how="left")
        fact = fact.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
        fact = fact.merge(dim_channel[["channel_id", "channel_key"]], on="channel_id", how="left")

        fact["gross_amount"] = fact["quantity"] * fact["unit_price"]
        fact["discount_amount"] = fact["gross_amount"] * fact["discount"]
        fact["net_amount"] = fact["gross_amount"] - fact["discount_amount"]
        fact["cost_amount"] = fact["quantity"] * fact["unit_cost"]
        fact["margin"] = fact["net_amount"] - fact["cost_amount"]

        money_columns = ["gross_amount", "discount_amount", "net_amount", "cost_amount", "margin"]
        fact[money_columns] = fact[money_columns].round(2)

        fact = fact.sort_values("order_item_id").reset_index(drop=True)
        fact.insert(0, "sale_key", range(1, len(fact) + 1))

        final_columns = [
            "sale_key",
            "date_key",
            "product_key",
            "customer_key",
            "channel_key",
            "quantity",
            "gross_amount",
            "discount_amount",
            "net_amount",
            "cost_amount",
            "margin",
        ]
        return fact[final_columns]
