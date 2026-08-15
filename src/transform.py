"""
Transform step of the ETL pipeline: turns the normalized OLTP DataFrames
into the denormalized star schema (four dimension tables + one fact
table), computing surrogate keys and sales measures along the way.
"""

import pandas as pd


class Transformer:
    """Builds the star-schema dimension tables and fact table from raw OLTP data."""

    def build_dim_date(self, orders_df):
        """
        Build dim_date from every distinct date that appears in orders.

        Each date is broken down into the parts (day, month, quarter, ...)
        that analytical queries commonly group or filter by, so that a
        query never has to re-derive "which quarter is this?" itself.
        """
        # Turn the order_date text column into real dates, then keep only
        # the distinct ones, sorted from earliest to latest.
        unique_dates = pd.to_datetime(orders_df["order_date"]).dt.normalize().unique()
        unique_dates = sorted(unique_dates)

        rows = []
        for raw_date in unique_dates:
            date_value = pd.Timestamp(raw_date)
            date_key = int(date_value.strftime("%Y%m%d"))  # e.g. 20250314
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
        """
        Build dim_product, pulling the category NAME onto each product row.

        This is the denormalization step: the OLTP "products" table only
        stores a category_id (a foreign key), and you would need a JOIN
        against "categories" to know the category's name. Here we do that
        join once, up front, and store the resulting name directly on the
        product row - so later, analytical queries can group sales by
        category with no JOIN at all.
        """
        categories_renamed = categories_df.rename(columns={"name": "category"})
        merged = products_df.merge(categories_renamed, on="category_id", how="left")

        dim_product = merged[["product_id", "sku", "name", "category", "unit_cost", "price"]].copy()
        dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))
        return dim_product

    def build_dim_customer(self, customers_df):
        """Build dim_customer by adding a surrogate key to the customer rows."""
        dim_customer = customers_df[["customer_id", "name", "city", "country"]].copy()
        dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))
        return dim_customer

    def build_dim_channel(self, channels_df):
        """Build dim_channel by adding a surrogate key to the channel rows."""
        dim_channel = channels_df[["channel_id", "name"]].copy()
        dim_channel.insert(0, "channel_key", range(1, len(dim_channel) + 1))
        return dim_channel

    def build_fact_sales(self, order_items_df, orders_df, dim_date, dim_product, dim_customer, dim_channel):
        """
        Build fact_sales: one row per order_item, carrying the surrogate
        keys of its four dimensions plus the sales measures.

        Business rule: only orders with status == "completed" count as
        real sales. Pending orders have not been paid for yet, and
        cancelled orders were reversed, so including them would overstate
        revenue and margin.
        """
        completed_orders = orders_df[orders_df["status"] == "completed"]

        # Bring customer_id, channel_id and order_date onto each order_item.
        # Using how="inner" also drops any order_item whose order was not
        # completed, since inner join only keeps matching rows.
        fact = order_items_df.merge(completed_orders, on="order_id", how="inner")

        # Turn order_date into the same YYYYMMDD integer used as dim_date's key.
        fact["date_key"] = pd.to_datetime(fact["order_date"]).dt.strftime("%Y%m%d").astype(int)

        # Look up each dimension's surrogate key by joining on its natural
        # (original OLTP) id. We also grab unit_cost from dim_product here,
        # since we need it below to compute cost_amount and margin.
        fact = fact.merge(dim_product[["product_id", "product_key", "unit_cost"]], on="product_id", how="left")
        fact = fact.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
        fact = fact.merge(dim_channel[["channel_id", "channel_key"]], on="channel_id", how="left")

        # --- Measures, as defined in the project spec ---
        fact["gross_amount"] = fact["quantity"] * fact["unit_price"]
        fact["discount_amount"] = fact["gross_amount"] * fact["discount"]
        fact["net_amount"] = fact["gross_amount"] - fact["discount_amount"]
        fact["cost_amount"] = fact["quantity"] * fact["unit_cost"]
        fact["margin"] = fact["net_amount"] - fact["cost_amount"]

        money_columns = ["gross_amount", "discount_amount", "net_amount", "cost_amount", "margin"]
        fact[money_columns] = fact[money_columns].round(2)

        # Keep the original order_item order, then add the fact table's own
        # surrogate key (sale_key).
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
