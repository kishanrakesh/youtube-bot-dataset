from dotenv import load_dotenv
import os

# Load variables from .env into environment
load_dotenv()

# Access them
GCP_API_KEY = os.getenv("GCP_API_KEY")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCS_BUCKET_DATA = os.getenv("GCS_BUCKET_DATA")
REGION = os.getenv("REGION")