import pandas as pd
import sqlalchemy
from pathlib import Path
import re
import time
from sqlalchemy import text


def normalize_column_name(name: str) -> str:
    """
    1. CamelCase -> snake_case
    2. \W+ -> _
    3. lowercase
    4. strip _
    """
    # CamelCase -> snake_case
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)

    # Non-word characters -> _
    name = re.sub(r'\W+', '_', name)

    return name.lower().strip('_')


def map_dtype(series: pd.Series) -> str:
    series_non_null = series.dropna().astype(str)

    # BOOLEAN
    if not series_non_null.empty and series_non_null.str.lower().isin(
        ["true", "false", "yes", "no"]
    ).all():
        return "BOOLEAN"

    # DATE / TIME / TIMESTAMP
    if not series_non_null.empty and series_non_null.str.contains(r"[-:]", regex=True).all():
        try:
            parsed = pd.to_datetime(series_non_null, errors="raise")
            if series_non_null.str.match(r"^\d{1,2}:\d{2}(:\d{2})?$").all():
                return "TIME"
            elif (
                (parsed.dt.hour == 0)
                & (parsed.dt.minute == 0)
                & (parsed.dt.second == 0)
            ).all():
                return "DATE"
            else:
                return "TIMESTAMP"
        except Exception:
            pass

    # INTEGER
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"

    # FLOAT
    if pd.api.types.is_float_dtype(series):
        return "FLOAT"

    # STRING
    max_len = max((len(str(v)) for v in series_non_null), default=1)
    return f"VARCHAR({max_len})"


def upload_csv_to_postgres(csv_path: Path, engine):
    df = pd.read_csv(csv_path)

    table_name = normalize_column_name(csv_path.stem)

    # нормализация имён колонок
    normalized_columns = {
        col: normalize_column_name(col)
        for col in df.columns
    }
    df = df.rename(columns=normalized_columns)

    with engine.begin() as conn:
        res = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = :table_name
                );
            """),
            {"table_name": table_name},
        )

        if res.scalar():
            print(f"Table '{table_name}' already exists. Skipping.")
            return

        columns_ddl = []
        for col in df.columns:
            col_type = map_dtype(df[col])
            columns_ddl.append(f'"{col}" {col_type}')

        ddl = f'CREATE TABLE "{table_name}" ({", ".join(columns_ddl)});'
        conn.execute(text(ddl))

        df.to_sql(
            table_name,
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
        )

        print(f"Table '{table_name}' created and data inserted.")


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


if __name__ == "__main__":
    engine = sqlalchemy.create_engine(
        "postgresql+psycopg2://postgres:postgres@db:5432/postgres"
    )

    wait_for_postgres(engine)

    for path in Path("csv").glob("*.csv"):
        print(f"Uploading {path}")
        upload_csv_to_postgres(path, engine)

