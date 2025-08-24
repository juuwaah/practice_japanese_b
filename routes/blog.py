from flask import Blueprint, render_template, request, abort
from google_drive_helper import get_blog_documents, get_document_content, search_blog_posts

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

@blog_bp.route('/')
def blog_index():
    """ブログ記事一覧ページ"""
    search_query = request.args.get('q', '')
    
    if search_query:
        blog_posts = search_blog_posts(search_query)
    else:
        blog_posts = get_blog_documents()
    
    return render_template('blog_index.html', 
                         blog_posts=blog_posts, 
                         search_query=search_query)

@blog_bp.route('/post/<document_id>')
def blog_post(document_id):
    """個別ブログ記事ページ"""
    document_content = get_document_content(document_id)
    
    if not document_content:
        abort(404)
    
    return render_template('blog_post.html', 
                         title=document_content['title'],
                         content=document_content['content'])