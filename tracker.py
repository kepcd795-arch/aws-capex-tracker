import datetime
import os
import sqlite3
import boto3
import pandas as pd
import requests

DB_NAME = "aws_metrics.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS spot_prices (
            timestamp TEXT, instance_type TEXT, az TEXT, spot_price REAL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS odm_revenue (
            date TEXT, ticker TEXT, company_name TEXT, revenue_ntd_thousands INTEGER,
            PRIMARY KEY(date, ticker)
        )
    """
    )
    conn.commit()
    conn.close()


def fetch_aws_spot_prices():
    instance_types = ["c6i.xlarge", "c7g.xlarge", "p4d.24xlarge"]
    ec2 = boto3.client(
        "ec2",
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    end_time = datetime.datetime.now(datetime.timezone.utc)
    start_time = end_time - datetime.timedelta(days=7)

    records = []
    for itype in instance_types:
        try:
            response = ec2.describe_spot_price_history(
                InstanceTypes=[itype],
                ProductDescriptions=["Linux/UNIX"],
                StartTime=start_time,
                EndTime=end_time,
            )
            for item in response["SpotPriceHistory"]:
                records.append(
                    (
                        item["Timestamp"].isoformat(),
                        item["InstanceType"],
                        item["AvailabilityZone"],
                        float(item["SpotPrice"]),
                    )
                )
        except Exception as e:
            print(f"AWS EC2 Error for {itype}: {e}")

    if records:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO spot_prices VALUES (?, ?, ?, ?)", records
        )
        conn.commit()
        conn.close()
        print(f"Logged {len(records)} AWS spot pricing records.")
    else:
        print("No AWS spot pricing records retrieved.")


def fetch_odm_revenue(year, month):
    # Convert Gregorian year to Taiwan Minguo year (2026 -> 115)
    tw_year = year - 1911
    url = f"https://mops.twse.com.tw/nas/t21/sii/t21sc03_{tw_year}_{month}_0.html"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            tables = pd.read_html(response.text)
            odm_tickers = {
                "6669": "Wiwynn",
                "2317": "Foxconn",
                "2382": "Quanta",
            }
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            inserted_count = 0

            for df in tables:
                if "Company Code" in df.columns or "公司代號" in df.columns:
                    for _, row in df.iterrows():
                        code = str(row.iloc[0]).strip()
                        if code in odm_tickers:
                            try:
                                rev = int(str(row.iloc[2]).replace(",", ""))
                                date_str = f"{year}-{month:02d}-01"
                                cursor.execute(
                                    "INSERT OR REPLACE INTO odm_revenue VALUES (?, ?, ?, ?)",
                                    (date_str, code, odm_tickers[code], rev),
                                )
                                inserted_count += 1
                            except ValueError:
                                pass
            conn.commit()
            conn.close()
            print(f"Logged {inserted_count} ODM revenue entries for {year}-{month:02d}.")
        else:
            print(f"MOPS fetch returned status code: {response.status_code}")
    except Exception as e:
        print(f"ODM fetch error: {e}")


if __name__ == "__main__":
    init_db()
    fetch_aws_spot_prices()
    now = datetime.datetime.now(datetime.timezone.utc)
    fetch_odm_revenue(now.year, now.month - 1 if now.month > 1 else 12)


