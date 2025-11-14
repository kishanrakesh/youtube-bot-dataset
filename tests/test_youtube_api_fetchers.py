# run_fetch_tests.py
from dotenv import load_dotenv; load_dotenv()
from app.youtube_api.fetch_channel_sections import fetch_channel_sections
from app.youtube_api.fetch_channels_by_id import fetch_channels_by_id
from app.youtube_api.fetch_comment_threads_by_video_id import fetch_comment_threads_by_video_id
from app.youtube_api.fetch_trending_videos_by_category import fetch_trending_videos_by_category
from app.youtube_api.fetch_trending_videos_general import fetch_trending_videos_general
from app.youtube_api.fetch_videos_by_channel import fetch_videos_by_channel
from app.youtube_api.fetch_videos_by_id import fetch_videos_by_id

# ✅ Sample IDs (replace with valid ones)
test_video_id = "dQw4w9WgXcQ"
test_channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
test_category_id = "10"  # Music
test_region = "US"

# ✅ Run all fetchers
if __name__ == "__main__":
    dry_run = False
    fetch_videos_by_id([test_video_id], dry_run=dry_run)
    fetch_trending_videos_by_category(test_region, test_category_id, dry_run=dry_run)
    fetch_trending_videos_general(test_region, dry_run=dry_run)
    fetch_comment_threads_by_video_id(test_video_id, dry_run=dry_run)
    fetch_channels_by_id([test_channel_id], dry_run=dry_run)
    fetch_videos_by_channel(test_channel_id, dry_run=dry_run, max_pages=2)
    fetch_channel_sections(test_channel_id, dry_run=dry_run)
