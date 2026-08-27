"""
Asks Claude to summarize the warehouse's analytics queries in plain English.

Runs every query in sql/analytics_queries.sql against warehouse.duckdb,
sends the results to the Anthropic API, and saves the written summary.

Run with: python -m src.ai_insights
Requires the ANTHROPIC_API_KEY environment variable to be set.
"""

import os
from datetime import date

import anthropic
import duckdb

from src.config import ANALYTICS_QUERIES_PATH, DUCKDB_PATH, INSIGHTS_DIR

MODEL = "claude-sonnet-4-6"
MAX_ROWS_PER_QUERY = 40


def load_queries():
    """Parse analytics_queries.sql into a list of (label, sql) pairs.

    Queries in the file are separated by a blank line before and after, so
    splitting on a double blank line gives one block per query. The file's
    own header comment (no SQL in it) has no SELECT and gets skipped.
    """
    text = ANALYTICS_QUERIES_PATH.read_text()
    blocks = [block.strip() for block in text.split("\n\n\n") if block.strip()]

    queries = []
    for block in blocks:
        lines = block.splitlines()
        comment_lines = [line for line in lines if line.strip().startswith("--")]
        sql_lines = [line for line in lines if not line.strip().startswith("--")]
        sql = "\n".join(sql_lines).strip()
        if not sql:
            continue
        label = comment_lines[0].lstrip("- ").strip() if comment_lines else "Query"
        queries.append((label, sql))
    return queries


def run_queries(connection, queries):
    """Run every query and turn its result into a readable text table."""
    results = []
    for label, sql in queries:
        result_df = connection.execute(sql).df()
        table_text = result_df.head(MAX_ROWS_PER_QUERY).to_string(index=False)
        results.append(f"### {label}\n\n{table_text}")
    return results


def build_prompt(results):
    """Combine all query results into one prompt asking for a short summary."""
    joined_results = "\n\n".join(results)
    return (
        "Below are the results of several SQL analytics queries run against "
        "an e-commerce data warehouse. Write a short summary as 5-8 bullet "
        "points, covering notable trends, the best and worst performers "
        "(products, channels, categories, customers), and anything that "
        "looks like an anomaly. Be concrete and cite numbers from the data. "
        "Do not restate the raw tables.\n\n"
        f"{joined_results}"
    )


def get_summary(prompt):
    """Send the prompt to Claude and return the plain-text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Get a key from console.anthropic.com "
            "and run: export ANTHROPIC_API_KEY=your-key-here"
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {DUCKDB_PATH}. Run 'python -m src.pipeline' first."
        )

    queries = load_queries()
    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        results = run_queries(connection, queries)
    finally:
        connection.close()

    prompt = build_prompt(results)
    summary = get_summary(prompt)

    print(summary)

    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = INSIGHTS_DIR / f"summary_{date.today().isoformat()}.md"
    output_path.write_text(summary)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
