from app import db
from datetime import datetime
import hashlib
import re


class Listing(db.Model):
    __tablename__ = 'listings'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('monitored_sites.id'), nullable=False, index=True)

    title = db.Column(db.String(500))
    price = db.Column(db.String(100))       # Display string: "$500K", "Price on Request"
    price_numeric = db.Column(db.Float)      # Parsed asking price in dollars
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    category = db.Column(db.String(200))
    normalized_category = db.Column(db.String(200))  # Standardized category via normalizer
    source = db.Column(db.String(50), default='scraper')  # 'scraper', 'email', 'manual'
    url = db.Column(db.String(500))          # Link to listing detail page
    image_url = db.Column(db.String(500))

    # Financial metrics (parsed from listing, all in dollars)
    revenue = db.Column(db.Float)            # Annual gross revenue
    cash_flow = db.Column(db.Float)          # Seller's discretionary cash flow
    sde = db.Column(db.Float)               # Seller's Discretionary Earnings
    ebitda = db.Column(db.Float)            # Earnings before interest, taxes, depreciation, amortization
    net_profit = db.Column(db.Float)        # Net profit / net income

    # Display strings for financial metrics
    revenue_str = db.Column(db.String(100))
    cash_flow_str = db.Column(db.String(100))
    sde_str = db.Column(db.String(100))
    ebitda_str = db.Column(db.String(100))
    net_profit_str = db.Column(db.String(100))

    # Deduplication
    content_hash = db.Column(db.String(64), index=True)

    # Status tracking
    is_new = db.Column(db.Boolean, default=True)
    first_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    removed_at = db.Column(db.DateTime)

    notes = db.Column(db.Text)

    @staticmethod
    def compute_hash(title, url):
        """Create a content hash for deduplication."""
        raw = f"{(title or '').strip().lower()}|{(url or '').strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def parse_price(price_str):
        """Parse a price string into a numeric dollar value.

        Handles: $500,000 | $1.2M | $500K | $250k | Price on Request → None
        """
        if not price_str:
            return None
        s = price_str.strip().replace(',', '')
        m = re.search(r'\$\s*([\d.]+)\s*([KkMmBb])?', s)
        if not m:
            return None
        value = float(m.group(1))
        suffix = (m.group(2) or '').upper()
        if suffix == 'K':
            value *= 1_000
        elif suffix == 'M':
            value *= 1_000_000
        elif suffix == 'B':
            value *= 1_000_000_000
        return value

    @staticmethod
    def parse_financials(text):
        """Extract financial metrics from listing text/description.

        Returns dict with keys: revenue, cash_flow, sde, ebitda, net_profit
        Each key maps to { 'value': float, 'str': display_string } or None.
        """
        if not text:
            return {}

        results = {}
        # Patterns: "Label: $X" or "Label $X" with various label names
        patterns = [
            (r'(?:gross\s+)?revenue\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'revenue'),
            (r'(?:annual\s+)?sales\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'revenue'),
            (r'cash\s*flow\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'cash_flow'),
            (r'(?:seller.?s?\s+)?discretionary\s+(?:earnings|cash\s*flow)\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'sde'),
            (r'\bSDE\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'sde'),
            (r'\bSDCF\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'sde'),
            (r'\bEBITDA\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'ebitda'),
            (r'net\s+(?:profit|income)\s*[:\s]*\$([\d,.]+)\s*([KkMmBb])?', 'net_profit'),
        ]

        for pattern, key in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and key not in results:
                raw_val = m.group(1).replace(',', '')
                value = float(raw_val)
                suffix = (m.group(2) or '').upper()
                if suffix == 'K':
                    value *= 1_000
                elif suffix == 'M':
                    value *= 1_000_000
                elif suffix == 'B':
                    value *= 1_000_000_000

                # Build display string
                if value >= 1_000_000:
                    display = f'${value / 1_000_000:.1f}M'
                elif value >= 1_000:
                    display = f'${value / 1_000:.0f}K'
                else:
                    display = f'${value:,.0f}'

                results[key] = {'value': value, 'str': display}

        return results

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'title': self.title,
            'price': self.price,
            'price_numeric': self.price_numeric,
            'description': self.description,
            'location': self.location,
            'category': self.category,
            'normalized_category': self.normalized_category,
            'source': self.source or 'scraper',
            'url': self.url,
            'image_url': self.image_url,
            'revenue': self.revenue,
            'revenue_str': self.revenue_str,
            'cash_flow': self.cash_flow,
            'cash_flow_str': self.cash_flow_str,
            'sde': self.sde,
            'sde_str': self.sde_str,
            'ebitda': self.ebitda,
            'ebitda_str': self.ebitda_str,
            'net_profit': self.net_profit,
            'net_profit_str': self.net_profit_str,
            'is_new': self.is_new,
            'first_seen_at': self.first_seen_at.isoformat() if self.first_seen_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'removed_at': self.removed_at.isoformat() if self.removed_at else None,
            'notes': self.notes,
        }
