version = 1.0

DEBUG = False

source_directory = "World-Anvil-Export"
destination_directory = "/mnt/c/Users/rheyn/Documents/Obsidian/FateRealms/FateRealms/content"
obsidian_resource_folder = "/mnt/c/Users/rheyn/Documents/Obsidian/FateRealms/FateRealms/images"

attempt_bbcode = True
download_concurrency = 10
download_timeout_seconds = 30.0
its_theme_support = True
leaflet_plugin_support = True
templates_directory = "templates"

# Obsidian Leaflet plugin defaults.
leaflet_default_height = "500px"
leaflet_default_min_zoom = 1
leaflet_default_max_zoom = 10
leaflet_default_zoom = 5
leaflet_default_unit = "meters"
leaflet_default_scale = 1
leaflet_minimal_template = True

# Inline image fallback configuration (hardcoded by request).
inline_image_api_fallback_enabled = True
worldanvil_api_key = ""
worldanvil_world_id = ""
worldanvil_image_api_url_template = ""
worldanvil_api_auth_header = "x-auth-token"
worldanvil_api_timeout_seconds = 15.0
worldanvil_api_retries = 2

# Replace unresolved inline image tags with warning callouts.
missing_inline_image_placeholder_enabled = True

# Optional test hook: force specific image IDs to behave as missing.
force_missing_inline_image_ids = set()

# Fields we do not want to export to markdown sections.
ignored_fields = {
    "id", "slug", "state", "isWip", "isDraft", "entityClass", "icon", "url",
    "subscribergroups", "folderId", "updateDate", "position", "wordcount",
    "notificationDate", "likes", "views", "userMetadata", "articleMetadata",
    "cssClasses", "displayCss", "customArticleTemplate", "editor", "author",
    "world", "category", "portrait", "cover", "coverSource", "snippet", "seeded",
    "displaySidebar", "timeline", "prompt", "gallery", "block", "orgchart",
    "showSeeded", "webhookUpdate", "communityUpdate", "commentPlaceholder",
    "passcodecta", "metaTitle", "metaDescription", "coverIsMap",
    "isFeaturedArticle", "isAdultContent", "isLocked", "allowComments",
    "allowContentCopy", "showInToc", "isEmphasized", "displayAuthor",
    "displayChildrenUnder", "displayTitle", "displaySheet", "badge", "editURL",
    "isEditable", "success", "genres", "theme", "fans", "isBook", "displayBookTitle",
    "isCollapsed", "systemMeta", "pagecover", "bookcover", "parsedDescription", "redirectedCategories"
}

# Fields rendered by dedicated logic instead of generic field rendering.
handled_fields = {
    "title", "content", "templateType", "template", "tags",
    "articleParent", "parent", "articleNext", "articlePrevious",
    "creationDate", "publicationDate",
    "sidepanelcontenttop", "sidepanelcontent", "sidebarcontent", "sidebarcontentbottom", "sidepanelcontentbottom",
}
