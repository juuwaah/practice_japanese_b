from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for, flash
from flask_login import current_user, login_required
from google_drive_helper import get_blog_documents, get_document_content, search_blog_posts
from models import db, BlogComment, BlogFavorite
from datetime import datetime

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

@blog_bp.route('/api/latest')
def api_latest_posts():
    """最新のブログ記事10件をJSON形式で返すAPI"""
    try:
        blog_posts = get_blog_documents()
        if not blog_posts:
            return jsonify([])
        
        # 最新10件に絞る
        latest_posts = blog_posts[:10]
        
        # 必要な情報のみを含むレスポンス
        response_posts = []
        for post in latest_posts:
            response_posts.append({
                'document_id': post['id'],
                'title': post['name'],
                'created_time': post.get('createdTime', ''),
                'modified_time': post.get('modifiedTime', '')
            })
        
        return jsonify(response_posts)
    except Exception as e:
        print(f"Blog API error: {e}")
        return jsonify([])

@blog_bp.route('/')
def blog_index():
    """ブログ記事一覧ページ"""
    search_query = request.args.get('q', '')
    tag_filter = request.args.get('tag', '')
    
    if search_query:
        blog_posts = search_blog_posts(search_query)
    else:
        blog_posts = get_blog_documents()
    
    # 各記事にタグ情報を追加
    for post in blog_posts:
        doc_content = get_document_content(post['id'])
        if doc_content:
            post['tags'] = doc_content.get('tags', [])
        else:
            post['tags'] = []
    
    # タグでフィルタリング
    if tag_filter:
        blog_posts = [post for post in blog_posts if tag_filter in post.get('tags', [])]
    
    # 全てのタグを収集
    all_tags = set()
    for post in blog_posts:
        all_tags.update(post.get('tags', []))
    all_tags = sorted(list(all_tags))
    
    return render_template('blog_index.html', 
                         blog_posts=blog_posts, 
                         search_query=search_query,
                         tag_filter=tag_filter,
                         all_tags=all_tags)

@blog_bp.route('/post/<document_id>')
def blog_post(document_id):
    """個別ブログ記事ページ"""
    document_content = get_document_content(document_id)
    
    if not document_content:
        abort(404)
    
    # コメントを取得（返信の階層構造も含む）
    comments = BlogComment.query.filter_by(
        document_id=document_id, 
        parent_comment_id=None,
        is_deleted=False
    ).order_by(BlogComment.created_at.desc()).all()
    
    # お気に入り状態を確認
    is_favorited = False
    if current_user.is_authenticated:
        favorite = BlogFavorite.query.filter_by(
            user_id=current_user.id,
            document_id=document_id
        ).first()
        is_favorited = bool(favorite)
    
    # お気に入り総数
    favorite_count = BlogFavorite.query.filter_by(document_id=document_id).count()
    
    return render_template('blog_post.html', 
                         document_id=document_id,
                         title=document_content['title'],
                         content=document_content['content'],
                         tags=document_content.get('tags', []),
                         comments=comments,
                         is_favorited=is_favorited,
                         favorite_count=favorite_count)

@blog_bp.route('/post/<document_id>/comment', methods=['POST'])
@login_required
def add_comment(document_id):
    """コメントを追加"""
    content = request.form.get('content', '').strip()
    parent_comment_id = request.form.get('parent_comment_id')
    
    if not content:
        flash('コメント内容を入力してください', 'error')
        return redirect(url_for('blog.blog_post', document_id=document_id))
    
    # 管理者かどうかを確認
    is_admin_reply = current_user.is_admin
    
    comment = BlogComment(
        document_id=document_id,
        user_id=current_user.id,
        content=content,
        parent_comment_id=int(parent_comment_id) if parent_comment_id else None,
        is_admin_reply=is_admin_reply
    )
    
    db.session.add(comment)
    db.session.commit()
    
    flash('コメントを投稿しました', 'success')
    return redirect(url_for('blog.blog_post', document_id=document_id))

@blog_bp.route('/post/<document_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(document_id):
    """お気に入りのトグル"""
    favorite = BlogFavorite.query.filter_by(
        user_id=current_user.id,
        document_id=document_id
    ).first()
    
    if favorite:
        # お気に入り削除
        db.session.delete(favorite)
        is_favorited = False
        message = 'お気に入りを解除しました'
    else:
        # お気に入り追加
        favorite = BlogFavorite(
            user_id=current_user.id,
            document_id=document_id
        )
        db.session.add(favorite)
        is_favorited = True
        message = 'お気に入りに追加しました'
    
    db.session.commit()
    
    # お気に入り総数を取得
    favorite_count = BlogFavorite.query.filter_by(document_id=document_id).count()
    
    if request.is_json:
        return jsonify({
            'success': True,
            'is_favorited': is_favorited,
            'favorite_count': favorite_count,
            'message': message
        })
    else:
        flash(message, 'success')
        return redirect(url_for('blog.blog_post', document_id=document_id))

@blog_bp.route('/favorites')
@login_required
def user_favorites():
    """ユーザーのお気に入り記事一覧"""
    favorites = BlogFavorite.query.filter_by(user_id=current_user.id)\
                                .order_by(BlogFavorite.created_at.desc()).all()
    
    # お気に入り記事の情報を取得
    favorite_posts = []
    for favorite in favorites:
        doc_content = get_document_content(favorite.document_id)
        if doc_content:
            favorite_posts.append({
                'id': favorite.document_id,
                'title': doc_content['title'],
                'tags': doc_content.get('tags', []),
                'favorited_at': favorite.created_at
            })
    
    return render_template('blog_favorites.html', favorite_posts=favorite_posts)