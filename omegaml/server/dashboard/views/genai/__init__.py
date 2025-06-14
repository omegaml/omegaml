import mimetypes
import os
import time
from datetime import timezone
from flask import render_template, jsonify, abort
from pathlib import Path
from werkzeug.utils import secure_filename

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView
from omegaml.server.util import datatables_ajax
from omegaml.util import utcnow


class GenAIView(BaseView):
    @fv.route('/{self.segment}')
    def index(self):
        om = self.om
        models = om.models.list(kind=['genai.text', 'genai.llm'], raw=True)
        indices = om.datasets.list(kind='pgvector.conx', raw=True)
        return render_template('dashboard/genai/conversations.html',
                               default=models[0] if models else None,
                               models=models,
                               indices=indices,
                               segment=self.segment)

    @fv.route('/{self.segment}/chat/<string:name>')
    def chat(self, name):
        return render_template('dashboard/genai/conversations.html',
                               name=name,
                               segment=self.segment)

    @fv.route('/{self.segment}/docs')
    def documents(self):
        om = self.om
        indices = om.datasets.list(kind='pgvector.conx', raw=True)
        return render_template('dashboard/genai/documents.html',
                               indices=indices,
                               segment=self.segment)

    @fv.route('/{self.segment}/chat/<path:name>/<string:conversation_id>')
    def modelchat(self, name, conversation_id=None):
        om = self.om
        model = om.models.metadata(name, data_store=om.datasets)
        return render_template('dashboard/genai/chat.html',
                               default=model,
                               models=None,
                               conversation_id=conversation_id,
                               segment=self.segment)

    @fv.route('/{self.segment}/docs/<path:name>')
    def api_list_documents(self, name):
        om = self.om
        draw = int(self.request.args.get('draw', 0))
        index = om.datasets.get(name, model_store=om.models)
        members = [{
            'id': item.get('id'),
            'name': Path(item.get('source') or '').name,
            'size': item.get('size', 0),
            'type': (item.get('source') or '').split('.')[-1].lower(),
            'excerpt': item.get('excerpt', ''),
        } for item in index.list()]
        return datatables_ajax(members, draw=draw)

    @fv.route('/{self.segment}/docs/<path:name>/<string:doc_id>', methods=['DELETE'])
    def api_delete_document(self, name, doc_id):
        """Delete index, or a document from the index"""
        om = self.om
        doc_id = int(doc_id) if doc_id.isdigit() else doc_id
        om.datasets.drop(name, obj=doc_id)  # Remove from the index
        return jsonify({'success': True}), 204

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
        index.insert(file_path)
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

    @fv.route('/{self.segment}/chat/history/<path:name>')
    def api_conversations(self, name):
        """List conversations for a given model"""
        om = self.om
        model = om.models.get(name, data_store=om.datasets)
        messages = model.conversation(run='*')
        messages.drop_duplicates(['key'], inplace=True, keep='first')
        return {'conversations': [
            {
                'id': msg.get('key'),
                'timestamp': msg.get('dt').replace(tzinfo=timezone.utc).isoformat() if msg.get('dt') else None,
                'title': msg.get('title', msg.get('content')),
                'tags': msg.get('tags', []),
            } for msg in messages.to_dict(orient='records')
        ]}

    @fv.route('/{self.segment}/chat/history/<path:name>/<string:conversation_id>')
    def api_conversation_history(self, name, conversation_id):
        """Get messages for a specific conversation"""
        om = self.om
        model = om.models.get(name, data_store=om.datasets)
        messages = model.conversation(conversation_id=conversation_id, raw=True)
        return {'messages': [
            {
                'role': msg.get('role'),
                'text': msg.get('content'),
            } for msg in messages
        ]}


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
