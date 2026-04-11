import os

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'zip', 'rar', '7z', 'mp3', 'wav', 'aac', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_icon(filename):
    """Get appropriate icon for file type"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']:
        return 'fa-video'
    elif ext in ['pdf']:
        return 'fa-file-pdf'
    elif ext in ['doc', 'docx', 'txt']:
        return 'fa-file-alt'
    elif ext in ['ppt', 'pptx']:
        return 'fa-file-powerpoint'
    elif ext in ['xls', 'xlsx']:
        return 'fa-file-excel'
    elif ext in ['zip', 'rar', '7z']:
        return 'fa-file-archive'
    elif ext in ['mp3', 'wav', 'aac', 'ogg']:
        return 'fa-file-audio'
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'svg']:
        return 'fa-file-image'
    else:
        return 'fa-file'
