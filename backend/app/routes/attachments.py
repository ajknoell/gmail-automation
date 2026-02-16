"""
Attachment Upload/Delete/Serve Routes

Files are stored in UPLOAD_FOLDER/attachments/{uuid}_{sanitized_name}
"""

import os
import uuid
import mimetypes
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename

attachments_bp = Blueprint('attachments', __name__)


def _attachments_dir():
    base = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'uploads'))
    d = os.path.join(base, 'attachments')
    os.makedirs(d, exist_ok=True)
    return d


@attachments_bp.route('/upload', methods=['POST'])
def upload_attachments():
    """
    POST /api/attachments/upload

    Accepts multipart/form-data with one or more files under the key 'files'.
    Returns a JSON array of uploaded file metadata.
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    results = []
    attach_dir = _attachments_dir()

    for f in files:
        if not f.filename:
            continue

        original_name = secure_filename(f.filename)
        file_id = str(uuid.uuid4())[:12]
        stored_name = f'{file_id}_{original_name}'
        filepath = os.path.join(attach_dir, stored_name)

        f.save(filepath)

        size = os.path.getsize(filepath)
        content_type = f.content_type or mimetypes.guess_type(original_name)[0] or 'application/octet-stream'

        results.append({
            'id': file_id,
            'filename': stored_name,
            'original_name': original_name,
            'size': size,
            'content_type': content_type,
        })

    return jsonify(results), 201


@attachments_bp.route('/<file_id>', methods=['DELETE'])
def delete_attachment(file_id):
    """Delete an uploaded attachment by its ID prefix."""
    attach_dir = _attachments_dir()

    # Find file matching this ID prefix
    for fname in os.listdir(attach_dir):
        if fname.startswith(file_id + '_'):
            filepath = os.path.join(attach_dir, fname)
            os.remove(filepath)
            return jsonify({'success': True})

    return jsonify({'error': 'File not found'}), 404


@attachments_bp.route('/<file_id>', methods=['GET'])
def serve_attachment(file_id):
    """Serve an uploaded attachment for preview/download."""
    attach_dir = _attachments_dir()

    for fname in os.listdir(attach_dir):
        if fname.startswith(file_id + '_'):
            return send_from_directory(attach_dir, fname, as_attachment=True)

    return jsonify({'error': 'File not found'}), 404
