from app import db
from datetime import datetime


# Junction table for many-to-many relationship
contact_tags = db.Table(
    'contact_tags',
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), default='#6B7280')  # hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    contacts = db.relationship('Contact', secondary=contact_tags, back_populates='tags', lazy='dynamic')

    def to_dict(self, include_count=False):
        d = {
            'id': self.id,
            'name': self.name,
            'color': self.color,
        }
        if include_count:
            d['contact_count'] = self.contacts.count()
        return d
