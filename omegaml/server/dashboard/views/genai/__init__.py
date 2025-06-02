import mimetypes
import os
import time
from flask import render_template, jsonify, abort
from pathlib import Path
from werkzeug.utils import secure_filename

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView
from omegaml.util import utcnow


class GenAIView(BaseView):
    @fv.route('/{self.segment}')
    def index(self):
        om = self.om
        models = om.models.list(kind='genai.text', raw=True)
        return render_template('dashboard/genai/chat.html',
                               default=models[0] if models else None,
                               models=models,
                               segment=self.segment)

    @fv.route('/{self.segment}/chat/<path:name>')
    def modelchat(self, name):
        om = self.om
        model = om.models.metadata(name)
        return render_template('dashboard/genai/chat.html',
                               default=model,
                               models=None,
                               segment=self.segment)

    @fv.route('/{self.segment}/docs')
    def documents(self):
        om = self.om
        return render_template('dashboard/genai/documents.html',
                               segment=self.segment)

    @fv.route('/{self.segment}/docs/upload', methods=['POST'])
    def api_upload_document(self):
        """Handle file upload - supports both form and AJAX requests"""
        request = self.request
        om = self.om
        # Check if file is present in request
        if 'file' not in request.files:
            abort(400, 'No file part in the request')
        file = request.files['file']
        index_name = request.form.get('indexName', 'default')
        # Check if filename is empty
        if file.filename == '' or not allowed_file(file.filename):
            abort(400, 'Filename is empty or not a valid file')
        # Secure the filename
        filename = secure_filename(file.filename)
        # Generate unique filename to avoid conflicts
        timestamp = str(int(time.time()))
        unique_filename = f"{timestamp}_{filename}"
        # Save file
        file_path = Path(self.om.defaults.OMEGA_TMP) / '.uploads' / unique_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        file.save(file_path)
        # Get file information
        file_size = os.path.getsize(file_path)
        file_type = get_file_type(filename)
        # Create document record
        document = {
            'id': timestamp,
            'original_name': filename,
            'stored_name': unique_filename,
            'file_path': file_path,
            'size': file_size,
            'size_formatted': format_file_size(file_size),
            'type': file_type,
            'index_name': index_name,
            'upload_date': utcnow().isoformat(),
            'status': 'uploaded'
        }
        # add document to index
        index = om.datasets.get(index_name, model_store=om.models)
        index.insert(unique_filename)
        success_msg = f'File "{filename}" uploaded successfully!'
        # Return JSON response for AJAX requests
        return jsonify({
            'success': True,
            'message': success_msg,
            'document': {
                'id': document['id'],
                'name': document['original_name'],
                'size': document['size_formatted'],
                'type': document['type'],
                'index_name': document['index_name'],
                'upload_date': document['upload_date']
            }
        }), 201


def create_view(bp):
    view = GenAIView('ai')
    view.create_routes(bp)
    return


# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx',
    'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 'mp4', 'avi', 'mov'
}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"


def get_file_type(filename):
    """Determine file type from filename"""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('text/') or mime_type == 'application/pdf':
            return 'document'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif 'spreadsheet' in mime_type or 'excel' in mime_type:
            return 'spreadsheet'
        elif 'presentation' in mime_type or 'powerpoint' in mime_type:
            return 'presentation'

    # Fallback based on extension
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    file_types = {
        'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
        'pdf': 'document', 'doc': 'document', 'docx': 'document', 'txt': 'document',
        'xls': 'spreadsheet', 'xlsx': 'spreadsheet',
        'ppt': 'presentation', 'pptx': 'presentation',
        'mp4': 'video', 'avi': 'video', 'mov': 'video',
        'mp3': 'audio', 'wav': 'audio'
    }
    return file_types.get(ext, 'unknown')
