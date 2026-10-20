import sqlite3
import time
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# In-memory database connection holder
db_conn = None
MAX_RECORDS = 200
EXTERNAL_API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def init_db():
    global db_conn
    db_conn = sqlite3.connect("file:memdb1?mode=memory&cache=shared", check_same_thread=False)
    cursor = db_conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            issueNumber TEXT PRIMARY KEY,
            number TEXT,
            color TEXT,
            premium TEXT,
            sum INTEGER
        )
    """)
    db_conn.commit()

def fetch_and_save_data():
    try:
        response = requests.get(EXTERNAL_API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            items = json_data.get("data", {}).get("list", [])

            cursor = db_conn.cursor()

            for item in items:
                cursor.execute("""
                    INSERT OR IGNORE INTO results (issueNumber, number, color, premium, sum)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(item.get("issueNumber")),
                    str(item.get("number")),
                    str(item.get("color")),
                    str(item.get("premium")),
                    int(item.get("sum", 0))
                ))

            cursor.execute(f"""
                DELETE FROM results
                WHERE issueNumber NOT IN (
                    SELECT issueNumber FROM results
                    ORDER BY issueNumber DESC
                    LIMIT {MAX_RECORDS}
                )
            """)

            db_conn.commit()
            print(f"[{time.strftime('%X')}] Clock synced fetch done.")
    except Exception as e:
        print(f"[{time.strftime('%X')}] Error fetching data: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_save_data, CronTrigger(second=2))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    fetch_and_save_data()
    scheduler.start()
    yield
    scheduler.shutdown()
    if db_conn:
        db_conn.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "API server live.", "endpoint": "/api/results"}

@app.get("/api/results")
def get_all_results():
    cursor = db_conn.cursor()
    cursor.execute(f"SELECT issueNumber, number, color, premium, sum FROM results ORDER BY issueNumber DESC LIMIT {MAX_RECORDS}")
    rows = cursor.fetchall()

    result_list = [
        {
            "issueNumber": row[0],
            "number": row[1],
            "color": row[2],
            "premium": row[3],
            "sum": row[4]
        }
        for row in rows
    ]

    return {
        "data": {
            "list": result_list,
            "pageNo": 1,
            "totalPage": 1,
            "totalCount": len(result_list)
        },
        "code": 0,
        "msg": "Succeed",
        "msgCode": 0,
        "serviceTime": int(time.time() * 1000)
    }

# YAHAN SE SERVER START HOTA HAI
if __name__ == "__main__":
    # JustRunMy.App dynamic port assign karta hai, isliye $PORT get karna zaroori hai
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)