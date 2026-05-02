import uuid
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.logging_config import configure_logging
from app.services.scene_llm import LLMService
from app.services.audio_llm import AudioService
from app.services.image_llm import ImageService
from app.services.client import APP_BASE_URL, logger
from app.services.video_compiler import VideoCompilerService
from app.models.scene import SceneRequest, SceneResult
from app.database.db_jobs import init_db, create_job, update_job_status, get_job, get_all_jobs, update_job_scenes
from app.services.cleanup import cleanup_intermediate_assets, cleanup_old_files

configure_logging()
logger = logger

static_path = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_path, exist_ok=True)

# ── Lifespan: Startup, DB Init, and Scheduled Tasks ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database
    logger.info("Initializing Turso Database...")
    init_db()  
    logger.info("Database ready.")

    # 2. Run Tier 2 Janitor immediately on server startup
    logger.info("Running startup Janitor sweep...")
    # Using the event loop to run the blocking file-system scan safely
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cleanup_old_files, static_path, 48)

    # 3. Start the background scheduler (Runs every 12 hours)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cleanup_old_files, 
        'interval', 
        hours=12, 
        args=[static_path, 48],
        id='janitor_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Janitor scheduler started (runs every 12 hours).")

    yield  # The app is now running

    # 4. Graceful shutdown
    scheduler.shutdown()
    logger.info("Scheduler shut down safely.")

app = FastAPI(lifespan=lifespan)

MUSIC_PATH = os.path.join(static_path, "bg_music.mp3")

llm_service   = LLMService()
audio_service = AudioService(static_path=static_path)
image_service = ImageService(static_path=static_path)
video_service = VideoCompilerService(
    static_path=static_path,
    music_path=MUSIC_PATH if os.path.exists(MUSIC_PATH) else None,
)

app.mount("/static", StaticFiles(directory=static_path), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse(os.path.join(static_path, "index.html"))

@app.post("/process_scene")
async def process_scene(request: SceneRequest, background_tasks: BackgroundTasks):
    try:
        result: SceneResult = llm_service.process_scene(request=request)
        job_id = str(uuid.uuid4())
        
        create_job(
            job_id=job_id, 
            status="generating", 
            scenes=result.scenes, 
            niche=request.niche
        )

        background_tasks.add_task(
            _run_pipeline,
            job_id=job_id,
            result=result,
            niche=request.niche,
            voice=getattr(request, "voice", None),  
        )

        logger.info(
            "Job %s created in DB | niche: '%s' | scenes: %d | seed: %d",
            job_id, request.niche, len(result.scenes), result.style_bible.video_seed,
        )

        return {
            "job_id": job_id,
            "scenes":[s.model_dump() for s in result.scenes],
            "style_bible": result.style_bible.model_dump(),
        }

    except Exception as e:
        logger.exception("Scene processing failed")
        raise HTTPException(status_code=500, detail=str(e))

# Background pipeline
# Background task to sync memory state to SQLite every 2 seconds
async def _sync_progress(job_id: str, scenes: list):
    while True:
        await asyncio.sleep(2)
        update_job_scenes(job_id, scenes)

# Background pipeline
async def _run_pipeline(
    job_id: str,
    result: SceneResult,
    niche: str,
    voice: str = None,
):
    scenes      = result.scenes
    style_bible = result.style_bible

    try:
        # Start the background DB sync
        progress_task = asyncio.create_task(_sync_progress(job_id, scenes))
        
        try:
            # Phase 1: Generate images and audio
            await asyncio.gather(
                image_service.generate_all_images(scenes=scenes, style_bible=style_bible),
                audio_service.generate_all_audios(scenes=scenes, niche=niche, voice=voice),
            )
        finally:
            # Always stop the sync loop and do one final 100% save
            progress_task.cancel()
            update_job_scenes(job_id, scenes)

        # Phase 2: Compile video
        update_job_status(job_id=job_id, status="compiling")

        output_path = await video_service.compile(
            scenes=scenes,
            job_id=job_id,
            niche=niche,
        )

        # Phase 3: Update DB with success
        filename = os.path.basename(output_path)
        base_url = APP_BASE_URL
        video_url = f"{base_url}/static/generated_videos/{filename}"
        
        update_job_status(job_id=job_id, status="done", video_url=video_url) 
        logger.info("Job %s complete | video: %s", job_id, video_url)

        # Tier 1 Cleanup
        cleanup_intermediate_assets(scenes=scenes, static_path=static_path, job_id=job_id)

    except Exception as e:
        update_job_status(job_id=job_id, status="failed", error=str(e)) 
        logger.exception("Pipeline failed for job %s", job_id)

@app.get("/get_status/{job_id}")
async def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in database")

    return {
        "job_id":    job["job_id"],
        "status":    job["status"],   
        "scenes":    job["scenes"], 
        "video_url": job["video_url"],
        "error":     job["error"],
        "niche":     job["niche"],
    }

@app.get("/jobs")
async def list_jobs():
    return get_all_jobs()