import os
import polars as pl
import numpy as np
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# First stage data in S3
#   aws s3 sync ./data s3://bucket/parquet-folder


# Function to generate random sales data
def generate_sales_data(n_rows: int, start_date: str) -> pl.DataFrame:
    # Random seed for reproducibility
    np.random.seed(42)

    # Generate dates
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [base_date + timedelta(days=i) for i in range(n_rows)]

    # Generate sample data
    data = {
        "transaction_id":
        np.arange(1, n_rows + 1),
        "sale_date":
        dates,
        "customer_id":
        np.random.randint(1000, 5000, n_rows),
        "product_name":
        np.random.choice(["Laptop", "Phone", "Tablet", "Monitor"], n_rows),
        "quantity":
        np.random.randint(1, 10, n_rows),
        "unit_price":
        np.random.uniform(50.0, 1000.0, n_rows).round(2),
        "region":
        np.random.choice(["North", "South", "East", "West"], n_rows),
    }

    # Create Polars DataFrame
    df = pl.DataFrame(data)
    df = df.with_columns(
        (pl.col("quantity") * pl.col("unit_price")).alias("total_amount"))

    return df


# Function to save DataFrame as partitioned Parquet files
def save_partitioned_parquet(df: pl.DataFrame, output_dir: Path):
    # Remove existing directory or file to avoid conflicts
    if os.path.exists(output_dir):
        if os.path.isfile(output_dir):
            os.remove(output_dir)  # Remove if it’s a file
        else:
            shutil.rmtree(output_dir)  # Remove if it’s a directory
    os.makedirs(output_dir, exist_ok=True)  # Create the directory

    df.write_parquet(output_dir,
                     compression="zstd",
                     partition_by=["product_name"])
    print(f"Parquet files saved to {output_dir}")


# Main execution
if __name__ == "__main__":
    # Parameters
    n_rows = 10000  # Number of rows to generate
    start_date = "2025-01-01"  # Starting date for sales data
    output_folder = Path(
        "./sample_data_store")  # Local folder to store Parquet files

    # Generate sample dataset
    print("Generating sample sales data...")
    sales_df = generate_sales_data(n_rows, start_date)

    # Preview the data
    print("Sample data preview:")
    print(sales_df.head())

    # Save as partitioned Parquet files
    print("Saving partitioned Parquet files...")
    save_partitioned_parquet(sales_df, output_folder)

    print("Done! Upload the folder to S3 for AWS Glue to process.")
    print(f"aws s3 sync ./{output_dir} s3://staging-data/sample-data/")
