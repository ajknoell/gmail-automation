import uuid
import re
import html as html_lib


class TrackingService:

    @staticmethod
    def get_base_url():
        """Return the public tracking base URL.

        Checks the database setting first (configurable via Settings UI),
        then falls back to the TRACKING_BASE_URL config/env variable.
        """
        from flask import current_app
        from app.models.settings import Settings
        db_url = Settings.get('tracking_base_url')
        if db_url:
            return db_url.rstrip('/')
        return current_app.config.get('TRACKING_BASE_URL', 'http://localhost:5001').rstrip('/')

    @staticmethod
    def generate_tracking_id():
        return str(uuid.uuid4())

    @staticmethod
    def plain_text_to_html(text):
        """Convert plain text email body to HTML, preserving formatting."""
        escaped = html_lib.escape(text)
        # Convert URLs to clickable links
        url_pattern = r'(https?://[^\s<>]+)'
        escaped = re.sub(url_pattern, r'<a href="\1">\1</a>', escaped)
        # Convert newlines to <br>
        escaped = escaped.replace('\n', '<br>\n')
        return (
            '<html><body style="font-family: sans-serif; font-size: 14px; '
            f'line-height: 1.5;">{escaped}</body></html>'
        )

    @classmethod
    def inject_tracking_pixel(cls, html_body, tracking_id, base_url):
        """Append a 1x1 tracking pixel to the HTML body."""
        pixel_url = f'{base_url}/t/o/{tracking_id}'
        pixel_tag = (
            f'<img src="{pixel_url}" width="1" height="1" '
            f'style="display:none" alt="" />'
        )
        if '</body>' in html_body.lower():
            # Insert before closing </body>
            idx = html_body.lower().rfind('</body>')
            return html_body[:idx] + pixel_tag + html_body[idx:]
        return html_body + pixel_tag

    @classmethod
    def rewrite_links(cls, html_body, tracking_id, base_url):
        """Rewrite <a href> links to route through click tracking.

        Returns (modified_html, link_map) where link_map is a dict
        of link_id -> original_url.
        """
        link_map = {}

        def replace_link(match):
            original_url = match.group(1)
            # Skip mailto and anchor links
            if original_url.startswith(('mailto:', '#', 'tel:')):
                return match.group(0)
            # Skip tracking pixel URL
            if '/t/o/' in original_url:
                return match.group(0)
            link_id = uuid.uuid4().hex[:8]
            link_map[link_id] = original_url
            tracked_url = f'{base_url}/t/c/{tracking_id}/{link_id}'
            return match.group(0).replace(original_url, tracked_url)

        pattern = r'href=["\']([^"\']+)["\']'
        modified = re.sub(pattern, replace_link, html_body, flags=re.IGNORECASE)
        return modified, link_map
