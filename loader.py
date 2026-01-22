import pandas as pd
import sqlalchemy
from pathlib import Path
import re
import time
import io
from sqlalchemy import text


# -------------------------------
# Column name normalization
# -------------------------------
def normalize_column_name(name: str) -> str:
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    name = re.sub(r'\W+', '_', name)
    return name.lower().strip('_')


# -------------------------------
# Type inference
# -------------------------------
def map_dtype(series: pd.Series) -> str:
    series_non_null = series.dropna()

    if series_non_null.empty:
        return "VARCHAR(1)"

    as_str = series_non_null.astype(str)

    if as_str.str.lower().isin({"true", "false", "yes", "no"}).all():
        return "BOOLEAN"

    if as_str.str.contains(r"[-:]", regex=True).all():
        try:
            parsed = pd.to_datetime(as_str, errors="raise")

            if as_str.str.match(r"^\d{1,2}:\d{2}(:\d{2})?$").all():
                return "TIME"

            if (
                (parsed.dt.hour == 0)
                & (parsed.dt.minute == 0)
                & (parsed.dt.second == 0)
            ).all():
                return "DATE"

            return "TIMESTAMP"
        except Exception:
            pass

    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"

    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"

    max_len = max(len(str(v)) for v in as_str)
    return f"VARCHAR({max_len})"


# -------------------------------
# COPY helper
# -------------------------------
def copy_df_to_postgres(df: pd.DataFrame, table_name: str, engine):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.copy_expert(
            f'COPY "{table_name}" FROM STDIN WITH CSV',
            buffer
        )
        conn.commit()
    finally:
        conn.close()


# -------------------------------
# CSV → PostgreSQL
# -------------------------------
def upload_csv_to_postgres(csv_path: Path, engine):
    df = pd.read_csv(csv_path)

    table_name = normalize_column_name(csv_path.stem)

    # Normalize column names
    df = df.rename(
        columns={col: normalize_column_name(col) for col in df.columns}
    )

    # ---- CREATE TABLE ----
    with engine.begin() as conn:
        exists = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                )
            """),
            {"table_name": table_name},
        ).scalar()

        if exists:
            print(f"Table '{table_name}' already exists. Skipping.")
            return

        columns_ddl = []
        for col in df.columns:
            col_type = map_dtype(df[col])
            columns_ddl.append(f'"{col}" {col_type}')

        ddl = f'CREATE TABLE "{table_name}" ({", ".join(columns_ddl)});'
        conn.execute(text(ddl))

    # ---- COPY DATA ----
    copy_df_to_postgres(df, table_name, engine)

    print(f"Table '{table_name}' created and data inserted.")


# -------------------------------
# Wait for PostgreSQL
# -------------------------------
def wait_for_postgres(engine, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            time.sleep(2)
    raise TimeoutError("PostgreSQL is not available.")


# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    engine = sqlalchemy.create_engine(
        "postgresql+psycopg2://postgres:postgres@db:5432/postgres"
    )

    wait_for_postgres(engine)

    for path in Path("csv").glob("*.csv"):
        print(f"Uploading {path}")
        upload_csv_to_postgres(path, engine)

