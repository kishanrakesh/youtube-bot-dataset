# ───── Configurable defaults ─────
TRENDING_REGION = US
CATEGORY = 27
DATE = $(shell date -u +%F)
TRENDING_PAGES = 50
COMMENT_PAGES = 20
SCREENSHOT_LIMIT = 200
REVIEW_LIMIT = 100

# ───── Pipeline commands ─────

.PHONY: fetch-trending
fetch-trending:
	@echo "🌎 Fetching trending videos..."
	python -m app.pipeline.fetch_trending \
		--region $(TRENDING_REGION) \
		--category $(CATEGORY) \
		--date $(DATE) \
		--max-pages $(TRENDING_PAGES)

.PHONY: load-trending
load-trending:
	@echo "📥 Loading trending results..."
	python -m app.pipeline.load_trending \
		--region $(TRENDING_REGION) \
		--category $(CATEGORY) \
		--date $(DATE) \
		--max-pages $(TRENDING_PAGES)

.PHONY: fetch-comments
fetch-comments:
	@echo "🗨️ Fetching comments for trending videos..."
	python -m app.pipeline.fetch_video_comments \
		--region $(TRENDING_REGION) \
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

.PHONY: register-capture
register-capture: register-commenters capture-screenshots

.PHONY: register-capture-loop
register-capture-loop:
	@echo "🔁 Starting repeated register-capture runs..."
	for i in $$(seq 1 10); do \
		echo "▶️ Run $$i at $$(date -u)"; \
		make register-capture; \
		echo "✅ Finished run $$i"; \
		sleep 60; \
	done

.PHONY: all-categories
all-categories:
	@echo "🎬 Running trending-to-comments for multiple categories..."
	for cat in 1 2 10 15 17 20 22 23 24 25 26; do \
		echo "📈 Processing category $$cat ($(DATE))..."; \
		make trending-to-comments CATEGORY=$$cat; \
		echo "✅ Finished category $$cat"; \
	done
	@echo "🚀 All categories complete. Starting register-capture-loop..."
	make register-capture-loop
