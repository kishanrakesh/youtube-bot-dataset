from google.cloud import bigquery

videos_schema = [
    bigquery.SchemaField("id", "STRING"),
    bigquery.SchemaField("uploader_channel_id", "STRING"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("published_at", "TIMESTAMP"),
    bigquery.SchemaField("category_id", "STRING"),
    bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
    bigquery.SchemaField("topic_categories", "STRING", mode="REPEATED"),
    bigquery.SchemaField("view_count", "INTEGER"),
    bigquery.SchemaField("like_count", "INTEGER"),
    bigquery.SchemaField("comment_count", "INTEGER"),
    bigquery.SchemaField("duration_seconds", "INTEGER"),
    bigquery.SchemaField("licensed_content", "BOOLEAN"),
    bigquery.SchemaField("thumbnail_url_default", "STRING"),
    bigquery.SchemaField("thumbnail_url_medium", "STRING"),
    bigquery.SchemaField("thumbnail_url_high", "STRING"),
    bigquery.SchemaField("thumbnail_url_standard", "STRING"),
    bigquery.SchemaField("thumbnail_url_maxres", "STRING"),
    bigquery.SchemaField("privacy_status", "STRING"),
    bigquery.SchemaField("embeddable", "BOOLEAN"),
    bigquery.SchemaField("made_for_kids", "BOOLEAN"),
    bigquery.SchemaField("license", "STRING"),
    bigquery.SchemaField("public_stats_viewable", "BOOLEAN")
]

channels_schema = [
    bigquery.SchemaField("id", "STRING"),
    bigquery.SchemaField("handle", "STRING"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("country", "STRING"),
    bigquery.SchemaField("published_at", "TIMESTAMP"),
    bigquery.SchemaField("thumbnail_url_default", "STRING"),
    bigquery.SchemaField("thumbnail_url_medium", "STRING"),
    bigquery.SchemaField("thumbnail_url_high", "STRING"),
    bigquery.SchemaField("banner_external_url", "STRING"),
    bigquery.SchemaField("view_count", "INTEGER"),
    bigquery.SchemaField("video_count", "INTEGER"),
    bigquery.SchemaField("subscriber_count", "INTEGER"),
    bigquery.SchemaField("is_subscriber_count_hidden", "BOOLEAN"),
    bigquery.SchemaField("topic_ids", "STRING", mode="REPEATED"),
    bigquery.SchemaField("topic_categories", "STRING", mode="REPEATED"),
    bigquery.SchemaField("keywords", "STRING"),
    bigquery.SchemaField("uploads_playlist_id", "STRING"),
    # bigquery.SchemaField("featured_channel_ids", "STRING", mode="REPEATED"),
    # bigquery.SchemaField("external_urls", "STRING", mode="REPEATED"),
    bigquery.SchemaField("is_linked", "BOOLEAN"),
    bigquery.SchemaField("is_made_for_kids", "BOOLEAN"),
    # bigquery.SchemaField("is_uploader", "BOOLEAN"),
    # bigquery.SchemaField("is_active", "BOOLEAN"),
    # bigquery.SchemaField("bot_status", "STRING"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP"),
    # bigquery.SchemaField("first_seen_deactivated_at", "TIMESTAMP"),
    bigquery.SchemaField("screenshot_gcs_uri", "STRING")
]

comments_schema = [
    bigquery.SchemaField("id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("video_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("uploader_channel_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("is_reply", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("parent_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("author_channel_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("author_display_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("author_profile_image_url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("author_channel_url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("text_display", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("text_original", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("like_count", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("total_reply_count", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("comment_thread_id", "STRING", mode="NULLABLE")
]

video_tags_schema = [
    bigquery.SchemaField("video_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("tag", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
]

video_topic_categories_schema = [
    bigquery.SchemaField("video_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("topic_category", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
]

featured_channels_schema = [
    bigquery.SchemaField("channel_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("featured_channel_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("channel_section_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("channel_section_title", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
]

domains_schema = [
    bigquery.SchemaField("domain", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("registrar", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("creation_date", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("expiration_date", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("updated_date", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("registrant_country", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("registrant_organization", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("registrant_email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("registrant_name", "STRING", mode="NULLABLE"),
    # bigquery.SchemaField("is_domain_active", "BOOLEAN", mode="NULLABLE"),
    # bigquery.SchemaField("is_domain_malicious", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
]

# dimension_video_categories_schema = [
#     bigquery.SchemaField("category_id", "STRING", mode="REQUIRED"),
#     bigquery.SchemaField("category_name", "STRING", mode="REQUIRED"),
#     bigquery.SchemaField("assignable", "BOOLEAN", mode="REQUIRED"),
#     bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
# ]

# channel_links_schema = [
#     bigquery.SchemaField("channel_id", "STRING", mode="REQUIRED"),
#     bigquery.SchemaField("external_url", "STRING", mode="REQUIRED"),
#     bigquery.SchemaField("normalized_domain", "STRING", mode="NULLABLE"),
#     bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED")
# ]

