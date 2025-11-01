# ───── Configurable defaults ─────
REGION ?= US
CATEGORY ?= 2
DATE ?= $(shell date -u +%F)
TRENDING_PAGES ?= 5
COMMENT_PAGES ?= 5
SCREENSHOT_LIMIT ?= 200
REVIEW_LIMIT ?= 500

# ───── Pipeline commands ─────

.PHONY: fetch-trending
fetch-trending:
	@echo "🌎 Fetching trending videos..."
	python -m app.pipeline.fetch_trending \
		--region $(REGION) \
		--category $(CATEGORY) \
		--date $(DATE) \
		--max-pages $(TRENDING_PAGES)

.PHONY: load-trending
load-trending:
	@echo "📥 Loading trending results..."
	python -m app.pipeline.load_trending \
		--region $(REGION) \
		--category $(CATEGORY) \
		--date $(DATE) \
		--max-pages $(TRENDING_PAGES)

.PHONY: fetch-comments
fetch-comments:
	@echo "🗨️ Fetching comments for trending videos..."
	python -m app.pipeline.fetch_video_comments \
		--region $(REGION) \
		--category $(CATEGORY) \
		--date $(DATE) \
		--max-pages $(TRENDING_PAGES) \
		--max-comment-pages $(COMMENT_PAGES)

.PHONY: register-commenters
register-commenters:
	@echo "📝 Registering commenter channels..."
	python -m app.pipeline.register_commenters \
		--limit $(REVIEW_LIMIT)

.PHONY: capture-screenshots
capture-screenshots:
	@echo "📸 Capturing channel screenshots..."
	python -m app.pipeline.capture_screenshots \
		--limit $(SCREENSHOT_LIMIT)

.PHONY: review
review:
	@echo "👀 Launching manual review UI..."
	python -m app.pipeline.review_channels \
		--limit $(REVIEW_LIMIT)

# ───── End-to-end workflows ─────

.PHONY: trending-to-comments
trending-to-comments: fetch-trending fetch-comments

.PHONY: annotate
annotate: register-commenters capture-screenshots review
