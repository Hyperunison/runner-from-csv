import pandas as pd
import sqlalchemy
from pathlib import Path
import time
from sqlalchemy import text


def map_dtype(series):
    series_non_null = series.dropna().astype(str)

    # BOOLEAN (true/false/yes/no)
    if series_non_null.str.lower().isin(["true", "false", "yes", "no"]).all():
        return "BOOLEAN"

    # DATE / TIMESTAMP — если строки содержат '-' или ':' и могут быть распознаны как даты
    if series_non_null.str.contains(r"[-:]", regex=True).all():
        try:
            parsed = pd.to_datetime(series_non_null, errors='raise')
            if (parsed.dt.hour == 0).all() and (parsed.dt.minute == 0).all() and (parsed.dt.second == 0).all():
                return "DATE"
            else:
                return "TIMESTAMP"
        except Exception:
            pass

    # INTEGER
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"

    # FLOAT
    if pd.api.types.is_float_dtype(series):
        return "FLOAT"

    # STRING (varchar)
    max_len = max([len(str(v)) for v in series_non_null], default=1)
    return f"VARCHAR({max_len})"


def upload_csv_to_postgres(csv_path, engine):
    df = pd.read_csv(csv_path)
    table_name = csv_path.stem.lower()

    with engine.begin() as conn:
        res = conn.execute(
            text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');")
        )
        if res.scalar():
            print(f"Table '{table_name}' already exists. Skipping.")
            return

        # Автоопределение типов
        columns = []
        for col in df.columns:
            col_type = map_dtype(df[col])
            columns.append(f'"{col}" {col_type}')

        ddl = text(f'CREATE TABLE "{table_name}" ({", ".join(columns)});')
        conn.execute(ddl)
        df.to_sql(table_name, con=conn, if_exists='append', index=False, method='multi')
        print(f"Table '{table_name}' created and data inserted.")

def wait_for_postgres(engine, timeout=5):
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            time.sleep(2)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    raise TimeoutError("PostgreSQL is not available.")

if __name__ == "__main__":
    engine = sqlalchemy.create_engine("postgresql+psycopg2://postgres:postgres@db:5432/postgres")
    wait_for_postgres(engine)
    for path in Path("csv").glob("*.csv"):
        upload_csv_to_postgres(path, engine)
