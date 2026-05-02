import json
import libsql
from app.services.client import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

TURSO_URL = TURSO_DATABASE_URL
TURSO_TOKEN = TURSO_AUTH_TOKEN

conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

def init_db():
    """Creates the jobs table if it doesn't exist on startup."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT,
            scenes TEXT,
            video_url TEXT,
            error TEXT,
            niche TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

def create_job(job_id: str, status: str, scenes: list, niche: str):
    """Inserts a new job into the database."""
    scenes_json = json.dumps([s.model_dump() for s in scenes])
    
    conn.execute(
        "INSERT INTO jobs (job_id, status, scenes, niche) VALUES (?, ?, ?, ?)",
        (job_id, status, scenes_json, niche)
    )
    conn.commit()

def update_job_status(job_id: str, status: str, video_url: str = None, error: str = None):
    """Updates the status, video_url, or error of an existing job."""
    if video_url:
        conn.execute(
            "UPDATE jobs SET status = ?, video_url = ? WHERE job_id = ?", 
            (status, video_url, job_id)
        )
    elif error:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE job_id = ?", 
            (status, error, job_id)
        )
    else:
        conn.execute(
            "UPDATE jobs SET status = ? WHERE job_id = ?", 
            (status, job_id)
        )
    conn.commit()

def update_job_scenes(job_id: str, scenes: list):
    """Updates ONLY the scenes column so the frontend sees real-time progress."""
    scenes_json = json.dumps([s.model_dump() for s in scenes])
    conn.execute(
        "UPDATE jobs SET scenes = ? WHERE job_id = ?", 
        (scenes_json, job_id)
    )
    conn.commit()

def get_job(job_id: str) -> dict:
    """Fetches a single job by ID and formats it for FastAPI."""
    cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return {
        "job_id": row[0],
        "status": row[1],
        "scenes": json.loads(row[2]) if row[2] else [],
        "video_url": row[3],
        "error": row[4],
        "niche": row[5],
    }

def get_all_jobs() -> dict:
    """Fetches all jobs for the debug endpoint."""
    cursor = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    
    jobs_dict = {}
    for row in cursor.fetchall():
        jobs_dict[row[0]] = {
            "status": row[1],
            "niche": row[5],
            "video_url": row[3],
            "error": row[4],
            "scene_count": len(json.loads(row[2])) if row[2] else 0,
        }
    return jobs_dict