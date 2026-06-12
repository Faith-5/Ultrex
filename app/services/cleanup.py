import os
import time
from typing import List
from app.models.scene import Scene
from app.services.client import logger

logger = logger

def cleanup_intermediate_assets(scenes: List[Scene], static_path: str, job_id: str):
    """
    Tier 1 Cleanup: Deletes raw images and audio files immediately 
    after a successful video compilation.
    """
    logger.info("T1 cleanup: job %s", job_id)
    
    for scene in scenes:
        # Delete image
        if scene.image_url:
            img_filename = scene.image_url.split("/")[-1]
            img_path = os.path.join(static_path, "generated_images", img_filename)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception as e:
                    logger.warning("Img del failed: %s", str(e)[:60])
        
        # Delete audio
        if scene.audio_url:
            aud_filename = scene.audio_url.split("/")[-1]
            aud_path = os.path.join(static_path, "generated_audios", aud_filename)
            if os.path.exists(aud_path):
                try:
                    os.remove(aud_path)
                except Exception as e:
                    logger.warning("Aud del failed: %s", str(e)[:60])
                    
    logger.info("T1 cleanup done")

def cleanup_old_files(static_path: str, hours_old: int = 48):
    """
    Tier 2 Cleanup: Scans all static directories and deletes files 
    (including final MP4s and leftover failed assets) older than X hours.
    """
    logger.info(f"Tier 2 Janitor: Scanning for files older than {hours_old} hours...")
    
    folders_to_check =[
        "generated_videos",
        "generated_images",
        "generated_audios",
        "temp_render"
    ]
    
    current_time = time.time()
    age_in_seconds = hours_old * 3600
    deleted_count = 0
    
    for folder in folders_to_check:
        folder_path = os.path.join(static_path, folder)
        if not os.path.exists(folder_path):
            continue
            
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            
            # Skip the background music file or any nested directories
            if not os.path.isfile(filepath) or filename == "bg_music.mp3":
                continue
                
            file_age = current_time - os.path.getmtime(filepath)
            
            if file_age > age_in_seconds:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Janitor failed to delete {filepath}: {e}")
                    
    if deleted_count > 0:
        logger.info(f"Tier 2 Janitor finished: Deleted {deleted_count} old files.")
    else:
        logger.info("Tier 2 Janitor finished: Space is clean.")