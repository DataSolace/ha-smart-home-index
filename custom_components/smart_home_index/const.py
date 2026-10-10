DOMAIN = "smart_home_index"
PANEL_URL = "smart-home-index"
STATIC_URL = "/smart_home_index_static"
CONF_PANEL = "show_panel"

# The public feed the integration polls once a day. Point it at a local copy of the app to test:
# scripts/deploy.sh --feed-url http://<host>:3000/api/catalog-lite rewrites this line in the deployed copy.
FEED_URL = "https://smarthomeindex.com/api/catalog-lite"
