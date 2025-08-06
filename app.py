# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth as admin_auth, firestore
import os
import traceback
import datetime
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import re
from markupsafe import escape, Markup
import math

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')

app.config['TEMPLATES_AUTO_RELOAD'] = True

app.secret_key = os.environ.get('FLASK_SECRET_KEY')
cloudinary.config(cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'), api_key=os.environ.get('CLOUDINARY_API_KEY'), api_secret=os.environ.get('CLOUDINARY_API_SECRET'), secure=True)
db = None
try:
    cred = credentials.Certificate(os.path.join(os.path.dirname(__file__), 'nissahub-firebase-service-account.json'))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK and Firestore Client Initialized Successfully.")
except Exception as e:
    print(f"CRITICAL ERROR initializing Firebase Admin SDK: {e}")

SKILL_CATEGORIES = [ "Handicrafts", "Fashion & Design", "Culinary Arts", "Arts & Crafts", "Digital Arts", "Beauty", "Other" ]

PRODUCT_CATEGORIES = [
    "Apparel & Fashion", "Home Goods", "Jewelry & Accessories", "Art & Collectibles",
    "Beauty & Personal Care", "Craft Supplies", "Digital Products", "Other"
]

@app.context_processor
def utility_processor():
    return dict(floor=math.floor, ceil=math.ceil)

@app.template_filter('format_datetime')
def format_datetime(timestamp):
    if isinstance(timestamp, datetime.datetime):
        return timestamp.strftime('%b %d, %Y')
    return timestamp # Fallback for unexpected types

@app.context_processor
def inject_user_data():
    if 'user_id' in session:
        try:
            user_ref = db.collection('users').document(session['user_id'])
            user_doc = user_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_data['uid'] = session['user_id']
                user_data['isAdmin'] = user_data.get('isAdmin', False) 
                return dict(current_user=user_data)
        except Exception:
            return dict(current_user=None)
    return dict(current_user=None)
    
@app.template_filter()
def nl2br(value): return Markup(re.sub(r'\r\n|\r|\n', '<br>\n', escape(value))) if isinstance(value, str) else value
    
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: 
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Authentication required.'}), 401
            return redirect(url_for('login_page', next=request.url))
        if request.endpoint not in ['select_role_page', 'session_logout', 'static'] and 'role' not in session:
            flash("Please complete your profile by selecting a role.", "info"); return redirect(url_for('select_role_page'))
        return f(*args, **kwargs)
    return decorated_function

def guest_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' in session: return redirect(url_for('dashboard_page'))
        return f(*args, **kwargs)
    return decorated_function
    
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user_ref = db.collection('users').document(session['user_id'])
        user_doc = user_ref.get()
        if not user_doc.exists or not user_doc.to_dict().get('isAdmin'):
            flash("Permission denied. You must be an administrator to view this page.", "error")
            return redirect(url_for('dashboard_page'))
        return f(*args, **kwargs)
    return decorated_function

def get_public_id_from_url(url):
    try:
        parts = url.split("/"); filename = parts[-1]; folder = parts[-2]
        return f"{folder}/{filename.rsplit('.', 1)[0]}"
    except: return None

def generate_search_tokens(text):
    if not text: return []
    text_lower = text.lower(); words = set(re.findall(r'\b\w+\b', text_lower)); tokens = set()
    for word in words:
        for i in range(1, len(word) + 1):
            tokens.add(word[:i])
    return list(tokens)

@app.route('/')
@login_required
def home():
    featured_skills, recent_skills = [], []
    try:
        featured_query = db.collection('skills').where(filter=firestore.FieldFilter('isPublished', '==', True)).where(filter=firestore.FieldFilter('isFeatured', '==', True)).order_by('created_at', direction=firestore.Query.DESCENDING).limit(6)
        featured_skills = [{'id': doc.id, **doc.to_dict()} for doc in featured_query.stream()]
        recent_query = db.collection('skills').where(filter=firestore.FieldFilter('isPublished', '==', True)).where(filter=firestore.FieldFilter('isFeatured', '==', False)).order_by('created_at', direction=firestore.Query.DESCENDING).limit(6)
        recent_skills = [{'id': doc.id, **doc.to_dict()} for doc in recent_query.stream()]
    except Exception: flash("Could not load courses. An admin may need to configure database indexes.", "error"); traceback.print_exc()
    return render_template('index.html', featured_skills=featured_skills, recent_skills=recent_skills)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard_page(): return render_template('admin/dashboard.html', page_title="Admin Dashboard")

@app.route('/admin/users')
@admin_required
def manage_users_page():
    try:
        users_query = db.collection('users').order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
        return render_template('admin/manage_users.html', page_title="Manage Users", users=[{'uid': doc.id, **doc.to_dict()} for doc in users_query])
    except Exception: flash("Failed to load users.", "error"); traceback.print_exc(); return render_template('admin/manage_users.html', page_title="Manage Users", users=[])

@app.route('/admin/user/<string:user_id>/toggle_admin', methods=['POST'])
@admin_required
def toggle_admin_status(user_id):
    if user_id == session['user_id']: flash("You cannot change your own admin status.", "error"); return redirect(url_for('manage_users_page'))
    try:
        user_ref = db.collection('users').document(user_id); user_doc = user_ref.get()
        if user_doc.exists: user_ref.update({'isAdmin': not user_doc.to_dict().get('isAdmin', False)}); flash(f"Admin status updated.", "success")
        else: flash("User not found.", "error")
    except Exception: flash("An error occurred.", "error"); traceback.print_exc()
    return redirect(url_for('manage_users_page'))

@app.route('/admin/user/<string:user_id>/toggle_disable', methods=['POST'])
@admin_required
def toggle_disable_status(user_id):
    if user_id == session['user_id']: flash("You cannot disable your own account.", "error"); return redirect(url_for('manage_users_page'))
    try:
        user_ref = db.collection('users').document(user_id); user_doc = user_ref.get()
        if user_doc.exists:
            new_status = not user_doc.to_dict().get('isDisabled', False); user_ref.update({'isDisabled': new_status})
            flash(f"Account has been {'disabled' if new_status else 'enabled'}.", "success")
        else: flash("User not found.", "error")
    except Exception: flash("An error occurred.", "error"); traceback.print_exc()
    return redirect(url_for('manage_users_page'))

@app.route('/admin/courses')
@admin_required
def manage_courses_page():
    try:
        courses_query = db.collection('skills').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        courses_list = []; users_cache = {}
        for course_doc in courses_query:
            course_data = {'id': course_doc.id, **course_doc.to_dict()}
            author_id = course_data.get('author_id')
            if author_id not in users_cache:
                author_doc = db.collection('users').document(author_id).get(); users_cache[author_id] = author_doc.to_dict() if author_doc.exists else {}
            course_data['author_name'] = users_cache.get(author_id, {}).get('displayName', 'Unknown'); courses_list.append(course_data)
        return render_template('admin/manage_courses.html', page_title="Manage Courses", courses=courses_list)
    except Exception: flash("Failed to load courses.", "error"); traceback.print_exc(); return render_template('admin/manage_courses.html', page_title="Manage Courses", courses=[])

def toggle_course_status(skill_id, field_name):
    try:
        skill_ref, skill_doc = db.collection('skills').document(skill_id), db.collection('skills').document(skill_id).get()
        if skill_doc.exists:
            new_status = not skill_doc.to_dict().get(field_name, False); skill_ref.update({field_name: new_status})
            action = "Featured" if new_status else "Unfeatured" if field_name == 'isFeatured' else "Published" if new_status else "Unpublished"
            flash(f"Course '{skill_doc.to_dict().get('name')}' has been {action}.", "success")
        else: flash("Course not found.", "error")
    except Exception: flash("An error occurred.", "error"); traceback.print_exc()
    return redirect(url_for('manage_courses_page'))

@app.route('/admin/course/<string:skill_id>/toggle_feature', methods=['POST'])
@admin_required
def toggle_feature_status(skill_id): return toggle_course_status(skill_id, 'isFeatured')

@app.route('/admin/course/<string:skill_id>/toggle_publish', methods=['POST'])
@admin_required
def toggle_publish_status(skill_id): return toggle_course_status(skill_id, 'isPublished')

@app.route('/marketplace')
@login_required
def marketplace_page():
    try:
        products_list, users_cache = [], {} 
        products_query = db.collection('products').where(filter=firestore.FieldFilter('isPublished', '==', True)).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        for doc in products_query:
            product_data = {'id': doc.id, **doc.to_dict()}; author_id = product_data.get('author_id')
            if author_id and author_id not in users_cache:
                author_doc = db.collection('users').document(author_id).get(); users_cache[author_id] = author_doc.to_dict() if author_doc.exists else {}
            product_data['author'] = users_cache.get(author_id); products_list.append(product_data)
        return render_template('products/marketplace.html', products=products_list, page_title="Marketplace")
    except Exception: traceback.print_exc(); flash("Could not load the marketplace.", "error"); return render_template('products/marketplace.html', products=[], page_title="Marketplace")

@app.route('/product/<string:product_id>')
@login_required
def product_detail_page(product_id):
    try:
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists: flash("Sorry, this product could not be found.", "error"); return redirect(url_for('marketplace_page'))
        product_data, current_user = {'id': product_doc.id, **product_doc.to_dict()}, inject_user_data().get('current_user', {})
        is_admin, is_author = current_user.get('isAdmin', False), product_data.get('author_id') == session.get('user_id')
        if not product_data.get('isPublished', False) and not (is_admin or is_author):
            flash("Sorry, this product is not currently available.", "error"); return redirect(url_for('marketplace_page'))
        author_data = {};
        if author_id := product_data.get('author_id'):
            author_doc = db.collection('users').document(author_id).get();
            if author_doc.exists: author_data = author_doc.to_dict()
        return render_template('products/product_detail.html', product=product_data, author=author_data, page_title=product_data.get('name'))
    except Exception: traceback.print_exc(); flash("An error occurred loading the product page.", "error"); return redirect(url_for('marketplace_page'))

@app.route('/skills')
@login_required
def skills_page():
    try:
        search_query, selected_category = request.args.get('query', '').strip().lower(), request.args.get('category', '').strip()
        query = db.collection('skills').where(filter=firestore.FieldFilter('isPublished', '==', True))
        if selected_category: query = query.where(filter=firestore.FieldFilter('category', '==', selected_category))
        if search_query: query = query.where(filter=firestore.FieldFilter('search_tokens', 'array_contains', search_query))
        docs = query.order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        return render_template('skills/skills.html', skills=[{'id': doc.id, **doc.to_dict()} for doc in docs], page_title="Explore Courses", search_query=search_query, categories=SKILL_CATEGORIES, selected_category=selected_category)
    except Exception: flash("An error occurred while loading courses.", "error"); traceback.print_exc(); return render_template('skills/skills.html', skills=[], page_title="Explore Courses", search_query="", categories=SKILL_CATEGORIES, selected_category="")

@app.route('/skill/<string:skill_id>', methods=['GET'])
@login_required
def skill_detail_page(skill_id):
    try:
        skill_ref = db.collection('skills').document(skill_id)
        skill_doc = skill_ref.get()

        if not skill_doc.exists:
            flash("Course could not be found.", "error"); return redirect(url_for('skills_page'))

        skill_data = {'id': skill_id, **skill_doc.to_dict()}
        current_user = inject_user_data().get('current_user') or {}
        is_admin, is_author = current_user.get('isAdmin', False), skill_data.get('author_id') == session.get('user_id')

        if not skill_data.get('isPublished', False) and not (is_admin or is_author):
            flash("Sorry, this course is not available.", "error"); return redirect(url_for('skills_page'))
            
        author_data = db.collection('users').document(skill_data.get('author_id')).get().to_dict() or {}
        lessons_list = sorted([{'id': doc.id, **doc.to_dict()} for doc in skill_ref.collection('lessons').stream()], key=lambda l: l.get('order', 0))
        
        # --- Robustly fetch and sort reviews ---
        temp_reviews_list = []
        total_rating = 0
        user_cache = {}
        for doc in skill_ref.collection('reviews').stream():
            review_data = {'id': doc.id, **doc.to_dict()}
            total_rating += review_data.get('rating', 0)
            user_id = review_data.get('user_id')
            if user_id:
                if user_id not in user_cache:
                    user_doc = db.collection('users').document(user_id).get()
                    user_cache[user_id] = user_doc.to_dict() if user_doc.exists else {}
                review_data['user_profile'] = user_cache[user_id]
            temp_reviews_list.append(review_data)
        reviews_list = sorted(temp_reviews_list, key=lambda r: r.get('created_at', datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)), reverse=True)
        review_summary = {"count": len(reviews_list), "average": round(total_rating / len(reviews_list), 1) if reviews_list else 0}

        temp_discussions_list = []
        discussion_posts_query = skill_ref.collection('discussions').stream()

        for post_doc in discussion_posts_query:
            post_data = {'id': post_doc.id, **post_doc.to_dict()}
            
            user_id = post_data.get('user_id')
            if user_id:
                if user_id not in user_cache:
                    user_doc = db.collection('users').document(user_id).get()
                    user_cache[user_id] = user_doc.to_dict() if user_doc.exists else {}
                post_data['user_profile'] = user_cache[user_id]
            
            temp_replies = []
            replies_query = post_doc.reference.collection('replies').stream()
            for reply_doc in replies_query:
                reply_data = {'id': reply_doc.id, **reply_doc.to_dict()}
                reply_user_id = reply_data.get('user_id')
                if reply_user_id:
                    if reply_user_id not in user_cache:
                        reply_user_doc = db.collection('users').document(reply_user_id).get()
                        user_cache[reply_user_id] = reply_user_doc.to_dict() if reply_user_doc.exists else {}
                    reply_data['user_profile'] = user_cache[reply_user_id]
                temp_replies.append(reply_data)
            
            post_data['replies'] = sorted(temp_replies, key=lambda r: r.get('created_at', datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)))
            temp_discussions_list.append(post_data)

        discussions_list = sorted(temp_discussions_list, key=lambda p: p.get('created_at', datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)))

        return render_template('skills/skill_detail.html', 
                                skill=skill_data, lessons=lessons_list, author=author_data, 
                                reviews=reviews_list, review_summary=review_summary, 
                                discussions=discussions_list, page_title=skill_data.get('name'), skill_id=skill_id)

    except Exception as e:
        traceback.print_exc()
        flash(f"An error occurred loading the course details: {e}", "error")
        return redirect(url_for('skills_page'))

@app.route('/skill/<string:skill_id>/review', methods=['POST'])
@login_required
def submit_review(skill_id):
    try:
        rating = request.form.get('rating'); review_text = request.form.get('review_text', '').strip()
        if not rating or not review_text: flash("Rating and review text are required.", "error")
        else:
            review_data = {
                'user_id': session['user_id'], 'rating': int(rating), 'text': review_text,
                'created_at': firestore.SERVER_TIMESTAMP, 'skill_id': skill_id
            }
            db.collection('skills').document(skill_id).collection('reviews').add(review_data)
            flash("Review submitted. Thank you!", "success")
    except Exception: flash("An error submitting your review.", "error"); traceback.print_exc()
    return redirect(url_for('skill_detail_page', skill_id=skill_id))

# --- START: NEW FUNCTION ---
@app.route('/skill/<string:skill_id>/review/<string:review_id>', methods=['DELETE'])
@login_required
def delete_review(skill_id, review_id):
    try:
        current_user_id = session['user_id']
        review_ref = db.collection('skills').document(skill_id).collection('reviews').document(review_id)
        review_doc = review_ref.get()

        if not review_doc.exists:
            return jsonify({'status': 'error', 'message': 'Review not found.'}), 404

        skill_doc = db.collection('skills').document(skill_id).get()
        if not skill_doc.exists:
            return jsonify({'status': 'error', 'message': 'Skill not found.'}), 404

        review_data = review_doc.to_dict()
        skill_data = skill_doc.to_dict()

        # Security Check: User must be the author of the review or the author of the skill
        if current_user_id == review_data.get('user_id') or current_user_id == skill_data.get('author_id'):
            review_ref.delete()
            return jsonify({'status': 'success', 'message': 'Review deleted successfully.'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'You do not have permission to delete this review.'}), 403

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500
# --- END: NEW FUNCTION ---
    
@app.route('/skill/<string:skill_id>/discussion', methods=['POST'])
@login_required
def create_discussion_post(skill_id):
    try:
        content = request.form.get('content', '').strip()
        if not content: return jsonify({'status': 'error', 'message': 'Content cannot be empty.'}), 400
        user_id = session['user_id']
        post_data = {'content': content, 'user_id': user_id, 'skill_id': skill_id, 'created_at': firestore.SERVER_TIMESTAMP}
        update_time, post_ref = db.collection('skills').document(skill_id).collection('discussions').add(post_data)
        
        new_post_for_js = {
            'id': post_ref.id,
            'content': content,
            'user_id': user_id,
            'created_at': datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        }
        user_profile = db.collection('users').document(user_id).get().to_dict() or {}
        return jsonify({'status': 'success', 'post': new_post_for_js, 'user_profile': user_profile})
    except Exception: traceback.print_exc(); return jsonify({'status': 'error', 'message': 'Internal error.'}), 500

@app.route('/skill/<string:skill_id>/discussion/<string:post_id>/reply', methods=['POST'])
@login_required
def create_discussion_reply(skill_id, post_id):
    try:
        content = request.form.get('content', '').strip()
        if not content: return jsonify({'status': 'error', 'message': 'Reply cannot be empty.'}), 400
        user_id = session['user_id']
        reply_data = {'content': content, 'user_id': user_id, 'post_id': post_id, 'created_at': firestore.SERVER_TIMESTAMP}
        update_time, reply_ref = db.collection('skills').document(skill_id).collection('discussions').document(post_id).collection('replies').add(reply_data)
        
        new_reply_for_js = {
            'id': reply_ref.id,
            'content': content,
            'user_id': user_id,
            'created_at': datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        }
        user_profile = db.collection('users').document(user_id).get().to_dict() or {}
        return jsonify({'status': 'success', 'reply': new_reply_for_js, 'user_profile': user_profile})
    except Exception: traceback.print_exc(); return jsonify({'status': 'error', 'message': 'Internal error.'}), 500

@app.route('/skill/<string:skill_id>/discussion/<string:post_id>', methods=['DELETE'])
@login_required
def delete_discussion_post(skill_id, post_id):
    try:
        post_ref = db.collection('skills').document(skill_id).collection('discussions').document(post_id)
        # Professional Delete: Must also delete all sub-collections (replies)
        replies = post_ref.collection('replies').stream()
        for reply in replies: reply.reference.delete()
        post_ref.delete()
        return jsonify({'status': 'success', 'message': 'Post and replies deleted.'})
    except Exception: return jsonify({'status': 'error', 'message': 'Failed to delete post.'}), 500
        
@app.route('/skill/<string:skill_id>/discussion/<string:post_id>/reply/<string:reply_id>', methods=['DELETE'])
@login_required
def delete_discussion_reply(skill_id, post_id, reply_id):
    try:
        db.collection('skills').document(skill_id).collection('discussions').document(post_id).collection('replies').document(reply_id).delete()
        return jsonify({'status': 'success', 'message': 'Reply deleted.'})
    except Exception: return jsonify({'status': 'error', 'message': 'Failed to delete reply.'}), 500

# ... (The rest of app.py is unchanged and can be omitted for brevity)
# Keep the full file from your end, I am just showing the changed parts here
# But for you, it is still a full copy-paste
# (all functions from creator_profile_page to the end are the same)
@app.route('/creator/<string:creator_id>')
@login_required
def creator_profile_page(creator_id):
    try:
        user_doc = db.collection('users').document(creator_id).get()
        if not user_doc.exists or user_doc.to_dict().get('role') != 'creator':
            flash("Creator profile not found.", "error"); return redirect(url_for('skills_page'))
        creator = user_doc.to_dict()
        skills_query = db.collection('skills').where(filter=firestore.FieldFilter('isPublished', '==', True)).where(filter=firestore.FieldFilter('author_id', '==', creator_id)).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        skills_list = [{'id': doc.id, **doc.to_dict()} for doc in skills_query]
        products_query = db.collection('products').where(filter=firestore.FieldFilter('isPublished', '==', True)).where(filter=firestore.FieldFilter('author_id', '==', creator_id)).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        products_list = [{'id': doc.id, **doc.to_dict()} for doc in products_query]
        return render_template('creators/profile_page.html', creator=creator, skills=skills_list, products=products_list, page_title=f"Storefront for {creator.get('displayName', creator.get('email'))}")
    except Exception: flash("Error loading creator profile.", "error"); traceback.print_exc(); return redirect(url_for('skills_page'))

@app.route('/profile/<string:user_id>')
@login_required
def customer_profile_page(user_id):
    try:
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            flash("This user profile does not exist.", "error"); return redirect(url_for('home'))
        profile_data = user_doc.to_dict()
        user_role = profile_data.get('role')
        if user_role == 'creator':
            return redirect(url_for('creator_profile_page', creator_id=user_id))
        if user_role == 'customer':
            try:
                reviews_query = db.collection_group('reviews').where(filter=firestore.FieldFilter('user_id', '==', user_id)).order_by('created_at', direction=firestore.Query.DESCENDING).limit(10).stream()
                reviews_list_from_query = list(reviews_query)
            except Exception:
                traceback.print_exc()
                flash("Could not sort activities. A database index may be building.", "warning")
                reviews_query = db.collection_group('reviews').where(filter=firestore.FieldFilter('user_id', '==', user_id)).limit(10).stream()
                reviews_list_from_query = list(reviews_query)
                if reviews_list_from_query:
                    reviews_list_from_query.sort(key=lambda x: x.to_dict().get('created_at'), reverse=True)
            activity_list, skill_cache = [], {}
            for review_doc in reviews_list_from_query:
                review_data = review_doc.to_dict(); skill_id = review_data.get('skill_id')
                if skill_id:
                    if skill_id not in skill_cache:
                        skill_doc = db.collection('skills').document(skill_id).get(); skill_cache[skill_id] = skill_doc.to_dict() if skill_doc.exists else None
                    if skill_cache[skill_id]:
                        activity_list.append({ 'type': 'review', 'skill': skill_cache[skill_id], 'skill_id': skill_id, 'review': review_data })
            return render_template('users/profile_page.html', profile_user=profile_data, activity=activity_list, page_title=f"Profile for {profile_data.get('displayName')}")
        flash("This user profile is not viewable.", "error"); return redirect(url_for('home'))
    except Exception as e:
        flash("Error loading profile.", "error"); traceback.print_exc(); return redirect(url_for('home'))

@app.route('/course/<string:skill_id>/lesson/<string:lesson_id>')
@login_required
def course_player_page(skill_id, lesson_id):
    try:
        skill_ref, skill_doc = db.collection('skills').document(skill_id), db.collection('skills').document(skill_id).get()
        if not skill_doc.exists: flash("Course not found.", "error"); return redirect(url_for('skills_page'))
        all_lessons_list = sorted([{'id': doc.id, **doc.to_dict()} for doc in skill_ref.collection('lessons').order_by('order').stream()], key=lambda l: l.get('order', 0))
        active_lesson_data, active_lesson_index = None, -1
        for i, lesson_data in enumerate(all_lessons_list):
            if lesson_data['id'] == lesson_id: active_lesson_data, active_lesson_index = lesson_data, i; break
        if not active_lesson_data: flash("Lesson not found in this course.", "error"); return redirect(url_for('skill_detail_page', skill_id=skill_id))
        previous_lesson, next_lesson = (all_lessons_list[active_lesson_index - 1] if active_lesson_index > 0 else None), (all_lessons_list[active_lesson_index + 1] if active_lesson_index < len(all_lessons_list) - 1 else None)
        return render_template('skills/course_player.html', skill=skill_doc.to_dict(), skill_id=skill_id, all_lessons=all_lessons_list, active_lesson=active_lesson_data, previous_lesson=previous_lesson, next_lesson=next_lesson)
    except Exception: traceback.print_exc(); flash("Error loading the course.", "error"); return redirect(url_for('skills_page'))

@app.route('/dashboard')
@login_required
def dashboard_page(): return render_template('dashboard.html', page_title="Dashboard")

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile_page():
    user_ref = db.collection('users').document(session['user_id'])
    if request.method == 'POST':
        updated_data = {'displayName': request.form.get('display_name'), 'bio': request.form.get('bio'), 'updatedAt': datetime.datetime.now(tz=datetime.timezone.utc)}
        if 'profile_image' in request.files and request.files['profile_image'].filename != '':
            image_file = request.files.get('profile_image')
            try:
                if old_url := user_ref.get().to_dict().get('avatar_url'):
                    if 'cloudinary' in old_url and (public_id := get_public_id_from_url(old_url)): cloudinary.uploader.destroy(public_id)
                upload_result = cloudinary.uploader.upload(image_file, folder="nissahub_avatars", transformation=[{'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'}])
                updated_data['avatar_url'] = upload_result.get('secure_url')
            except Exception: flash("Profile image upload failed.", "error"); return redirect(url_for('edit_profile_page'))
        user_ref.update(updated_data)
        flash("Your profile updated successfully!", "success"); return redirect(url_for('dashboard_page'))
    return render_template('auth/edit_profile.html', page_title="Edit Your Profile", user=user_ref.get().to_dict() or {})

def check_skill_ownership(skill_id, user_id):
    skill_ref, skill_doc = db.collection('skills').document(skill_id), db.collection('skills').document(skill_id).get()
    if not skill_doc.exists: flash("Course not found.", "error"); return None, None, redirect(url_for('my_skills_page'))
    skill_data = skill_doc.to_dict()
    if skill_data.get('author_id') != user_id: flash("You can only manage your own courses.", "error"); return None, None, redirect(url_for('my_skills_page'))
    return skill_ref, skill_data, None

def check_product_ownership(product_id, user_id):
    product_ref, product_doc = db.collection('products').document(product_id), db.collection('products').document(product_id).get()
    if not product_doc.exists: flash("Product not found.", "error"); return None, None, redirect(url_for('my_products_page'))
    product_data, product_data['id'] = product_doc.to_dict(), product_id 
    if product_data.get('author_id') != user_id: flash("You can only manage your own products.", "error"); return None, None, redirect(url_for('my_products_page'))
    return product_ref, product_data, None

@app.route('/my-skills')
@login_required
def my_skills_page():
    if session.get('role') != 'creator': flash("Permission denied.", "error"); return redirect(url_for('dashboard_page'))
    try:
        skills_query = db.collection('skills').where(filter=firestore.FieldFilter('author_id', '==', session['user_id'])).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        skills_list = []
        for doc in skills_query:
            skill_data = {'id': doc.id, **doc.to_dict()}; skill_data['lesson_count'] = len(list(doc.reference.collection('lessons').stream())); skill_data['review_count'] = len(list(doc.reference.collection('reviews').stream())); skills_list.append(skill_data)
        return render_template('skills/my_skills.html', skills=skills_list, page_title="Manage My Courses")
    except Exception: flash("Could not load your courses.", "error"); traceback.print_exc(); return render_template('skills/my_skills.html', skills=[], page_title="Manage My Courses")

@app.route('/skills/create', methods=['GET', 'POST'])
@login_required
def create_skill_page():
    if session.get('role') != 'creator': return redirect(url_for('dashboard_page'))
    if request.method == 'POST':
        is_published, name, desc, cat = request.form.get('is_published') == 'true', request.form.get('skill_name'), request.form.get('skill_description'), request.form.get('skill_category')
        if not all([name, desc, cat]): flash('All fields are required.', 'error'); return render_template('skills/skill_form.html', page_title="Create New Course", skill={}, categories=SKILL_CATEGORIES)
        image_url = 'img/skill_placeholder_default.jpg';
        if 'skill_image' in request.files and request.files['skill_image'].filename != '':
            image_file = request.files.get('skill_image');
            try: res = cloudinary.uploader.upload(image_file, folder="nissahub_skills", transformation=[{'width': 1000, 'height': 750, 'crop': 'limit'}]); image_url = res.get('secure_url')
            except Exception: flash("Image upload failed.", "error"); return render_template('skills/skill_form.html', page_title="Create New Course", skill={}, categories=SKILL_CATEGORIES)
        try:
            skill_data = { 'name': name, 'description': desc, 'category': cat, 'author_id': session['user_id'], 'author_email': session.get('email'), 'created_at': firestore.SERVER_TIMESTAMP, 'image_url': image_url, 'search_tokens': generate_search_tokens(f"{name} {desc}"), 'isPublished': is_published, 'isFeatured': False }
            db.collection('skills').add(skill_data)
            flash(f'Course "{name}" created successfully!', 'success'); return redirect(url_for('my_skills_page'))
        except Exception: flash('Error saving course.', 'error'); return render_template('skills/skill_form.html', page_title="Create New Course", skill={}, categories=SKILL_CATEGORIES)
    return render_template('skills/skill_form.html', page_title="Create New Course", skill={}, categories=SKILL_CATEGORIES)

@app.route('/skills/edit/<string:skill_id>', methods=['GET', 'POST'])
@login_required
def edit_skill_page(skill_id):
    if session.get('role') != 'creator': flash("Permission denied.", 'error'); return redirect(url_for('dashboard_page'))
    skill_ref, skill_data, error = check_skill_ownership(skill_id, session['user_id'])
    if error: return error
    if request.method == 'POST':
        updated_data = { 'name': request.form.get('skill_name'),'description': request.form.get('skill_description'), 'category': request.form.get('skill_category'), 'updated_at': firestore.SERVER_TIMESTAMP, 'search_tokens': generate_search_tokens(f"{request.form.get('skill_name')} {request.form.get('skill_description')}"), 'isPublished': request.form.get('is_published') == 'true' }
        if 'skill_image' in request.files and request.files['skill_image'].filename != '':
            image_file = request.files.get('skill_image')
            try:
                if old_url := skill_data.get('image_url'):
                    if 'cloudinary' in old_url and (pid := get_public_id_from_url(old_url)): cloudinary.uploader.destroy(pid)
                res = cloudinary.uploader.upload(image_file, folder="nissahub_skills", transformation=[{'width': 1000, 'height': 750, 'crop': 'limit'}]); updated_data['image_url'] = res.get('secure_url')
            except Exception: flash("Image upload failed.", "error"); return redirect(url_for('edit_skill_page', skill_id=skill_id))
        skill_ref.update(updated_data)
        flash(f'Skill "{updated_data["name"]}" updated successfully!', 'success'); return redirect(url_for('my_skills_page'))
    return render_template('skills/skill_form.html', page_title="Edit Course", skill=skill_data, skill_id=skill_id, categories=SKILL_CATEGORIES)

@app.route('/skills/delete/<string:skill_id>', methods=['POST'])
@login_required
def delete_skill(skill_id):
    if session.get('role') != 'creator': flash("Permission denied.", 'error'); return redirect(url_for('dashboard_page'))
    skill_ref, skill_data, error = check_skill_ownership(skill_id, session['user_id'])
    if error: return error
    if 'cloudinary' in (img := skill_data.get('image_url', '')) and (pid := get_public_id_from_url(img)): cloudinary.uploader.destroy(pid)
    skill_ref.delete(); flash(f"Skill '{skill_data.get('name')}' deleted.", 'success')
    return redirect(url_for('my_skills_page'))

@app.route('/my-products')
@login_required
def my_products_page():
    if session.get('role') != 'creator': flash("Permission denied.", "error"); return redirect(url_for('dashboard_page'))
    try:
        products_query = db.collection('products').where(filter=firestore.FieldFilter('author_id', '==', session['user_id'])).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        products_list = [{'id': doc.id, **doc.to_dict()} for doc in products_query]
        return render_template('products/my_products.html', products=products_list, page_title="Manage My Products")
    except Exception: traceback.print_exc(); flash("Could not load your products.", "error"); return render_template('products/my_products.html', products=[], page_title="Manage My Products")

@app.route('/products/create', methods=['GET', 'POST'])
@login_required
def create_product_page():
    if session.get('role') != 'creator': flash("You must be a creator to add products.", "error"); return redirect(url_for('dashboard_page'))
    if request.method == 'POST':
        form_data = { 'name': request.form.get('product_name'), 'description': request.form.get('product_description'), 'price': request.form.get('product_price'), 'category': request.form.get('product_category'), 'isPublished': request.form.get('is_published') == 'true' }
        if not all([form_data['name'], form_data['description'], form_data['price'], form_data['category']]):
            flash('All fields except image are required.', 'error'); return render_template('products/product_form.html', page_title="Add New Product", product=form_data, categories=PRODUCT_CATEGORIES, form_action=url_for('create_product_page'))
        image_url = 'img/skill_placeholder_default.jpg' 
        if 'product_image' in request.files and request.files['product_image'].filename != '':
            image_file = request.files['product_image'];
            try: upload_result = cloudinary.uploader.upload(image_file, folder="nissahub_products", transformation=[{'width': 1000, 'height': 1000, 'crop': 'limit'}]); image_url = upload_result.get('secure_url')
            except Exception: traceback.print_exc(); flash("Image upload failed.", "error"); return render_template('products/product_form.html', page_title="Add New Product", product=form_data, categories=PRODUCT_CATEGORIES, form_action=url_for('create_product_page'))
        try:
            new_product_data = {'name': form_data['name'], 'description': form_data['description'], 'price': float(form_data['price']), 'category': form_data['category'], 'isPublished': form_data['isPublished'], 'image_url': image_url, 'author_id': session['user_id'], 'author_email': session.get('email'), 'created_at': firestore.SERVER_TIMESTAMP, 'isFeatured': False }
            db.collection('products').add(new_product_data); flash(f'Product "{form_data["name"]}" added successfully!', 'success'); return redirect(url_for('my_products_page'))
        except Exception: traceback.print_exc(); flash('An unexpected error occurred.', 'error'); return render_template('products/product_form.html', page_title="Add New Product", product=form_data, categories=PRODUCT_CATEGORIES, form_action=url_for('create_product_page'))
    return render_template('products/product_form.html', page_title="Add New Product", product={}, categories=PRODUCT_CATEGORIES, form_action=url_for('create_product_page'))

@app.route('/products/edit/<string:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product_page(product_id):
    if session.get('role') != 'creator': flash("You are not authorized to edit products.", "error"); return redirect(url_for('dashboard_page'))
    product_ref, product_data, error_response = check_product_ownership(product_id, session['user_id'])
    if error_response: return error_response
    if request.method == 'POST':
        updated_data = { 'name': request.form.get('product_name'), 'description': request.form.get('product_description'), 'price': float(request.form.get('product_price')), 'category': request.form.get('product_category'), 'isPublished': request.form.get('is_published') == 'true', 'updated_at': firestore.SERVER_TIMESTAMP }
        if 'product_image' in request.files and request.files['product_image'].filename != '':
            image_file = request.files['product_image']
            try:
                if old_url := product_data.get('image_url'):
                    if 'cloudinary' in old_url and (pid := get_public_id_from_url(old_url)): cloudinary.uploader.destroy(pid)
                upload_result = cloudinary.uploader.upload(image_file, folder="nissahub_products", transformation=[{'width': 1000, 'height': 1000, 'crop': 'limit'}]); updated_data['image_url'] = upload_result.get('secure_url')
            except Exception: flash("Image upload failed.", "error"); return redirect(url_for('edit_product_page', product_id=product_id))
        product_ref.update(updated_data)
        flash(f'Product "{updated_data["name"]}" updated successfully!', 'success'); return redirect(url_for('my_products_page'))
    return render_template('products/product_form.html', page_title="Edit Product", product=product_data, categories=PRODUCT_CATEGORIES, form_action=url_for('edit_product_page', product_id=product_id))

@app.route('/products/delete/<string:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if session.get('role') != 'creator': flash("Permission denied.", 'error'); return redirect(url_for('dashboard_page'))
    product_ref, product_data, error = check_product_ownership(product_id, session['user_id'])
    if error: return error
    try:
        if 'cloudinary' in (img_url := product_data.get('image_url', '')) and (public_id := get_public_id_from_url(img_url)): cloudinary.uploader.destroy(public_id)
        product_ref.delete()
        flash(f"Product '{product_data.get('name')}' has been deleted successfully.", 'success')
    except Exception as e: traceback.print_exc(); flash("An error occurred while trying to delete the product.", 'error')
    return redirect(url_for('my_products_page'))

@app.route('/skills/<string:skill_id>/manage', methods=['GET', 'POST'])
@login_required
def manage_lessons_page(skill_id):
    skill_ref, skill_data, error = check_skill_ownership(skill_id, session['user_id']);
    if error: return error
    lessons_ref = skill_ref.collection('lessons')
    if request.method == 'POST':
        title, l_type = request.form.get('lesson_title'), request.form.get('lesson_type')
        if not title or not l_type: flash("Title and type required.", "error"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
        last_lesson = next(lessons_ref.order_by('order', direction=firestore.Query.DESCENDING).limit(1).stream(), None)
        next_order = last_lesson.to_dict().get('order', 0) + 1 if last_lesson else 1
        content = request.form.get('content_text', '') if l_type == "Text" else request.form.get('content_video', '')
        lessons_ref.add({'title': title, 'lesson_type': l_type, 'content': content, 'created_at': firestore.SERVER_TIMESTAMP, 'order': next_order})
        flash(f"Successfully added lesson: '{title}'", "success"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
    return render_template('skills/manage_lessons.html', skill=skill_data, skill_id=skill_id, lessons=sorted([{'id': doc.id, **doc.to_dict()} for doc in lessons_ref.stream()], key=lambda l: l.get('order', 0)))

@app.route('/skills/<string:skill_id>/lessons/<string:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lesson_page(skill_id, lesson_id):
    skill_ref, _, error = check_skill_ownership(skill_id, session['user_id']);
    if error: return error
    lesson_ref = skill_ref.collection('lessons').document(lesson_id); lesson_doc = lesson_ref.get()
    if not lesson_doc.exists: flash("Lesson not found.", "error"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
    if request.method == 'POST':
        title, l_type = request.form.get('lesson_title'), request.form.get('lesson_type')
        content = request.form.get('content_text', '') if l_type == "Text" else request.form.get('content_video', '')
        lesson_ref.update({'title': title, 'lesson_type': l_type, 'content': content, 'updated_at': firestore.SERVER_TIMESTAMP})
        flash("Lesson updated!", "success"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
    return render_template('skills/edit_lesson.html', skill_id=skill_id, lesson_id=lesson_id, lesson=lesson_doc.to_dict())

@app.route('/skills/<string:skill_id>/lessons/<string:lesson_id>/delete', methods=['POST'])
@login_required
def delete_lesson(skill_id, lesson_id):
    skill_ref, _, error = check_skill_ownership(skill_id, session['user_id']);
    if error: return error
    skill_ref.collection('lessons').document(lesson_id).delete(); flash("Lesson deleted.", "success")
    return redirect(url_for('manage_lessons_page', skill_id=skill_id))

@app.route('/skills/<string:skill_id>/lessons/<string:lesson_id>/reorder/<direction>')
@login_required
def reorder_lesson(skill_id, lesson_id, direction):
    skill_ref, _, error = check_skill_ownership(skill_id, session['user_id']);
    if error: return error
    if direction not in ['up', 'down']: flash("Invalid direction.", "error"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
    lessons_ref, current_lesson_ref = skill_ref.collection('lessons'), skill_ref.collection('lessons').document(lesson_id)
    current_order = current_lesson_ref.get().to_dict().get('order')
    op, order_dir = ('<', firestore.Query.DESCENDING) if direction == 'up' else ('>', firestore.Query.ASCENDING)
    swap_doc = next(lessons_ref.where('order', op, current_order).order_by('order', direction=order_dir).limit(1).stream(), None)
    if not swap_doc: flash("Cannot move further.", "info"); return redirect(url_for('manage_lessons_page', skill_id=skill_id))
    swap_order = swap_doc.to_dict().get('order'); batch = db.batch(); batch.update(current_lesson_ref, {'order': swap_order}); batch.update(swap_doc.reference, {'order': current_order}); batch.commit()
    return redirect(url_for('manage_lessons_page', skill_id=skill_id))

@app.route('/login')
@guest_only
def login_page(): return render_template('auth/login.html', page_title="Login")

@app.route('/register')
@guest_only
def register_page(): return render_template('auth/register.html', page_title="Register")

@app.route('/forgot-password')
@guest_only
def forgot_password_page(): return render_template('auth/forgot_password.html', page_title="Reset Password")

@app.route('/select-role', methods=['GET', 'POST'])
@login_required
def select_role_page():
    if request.method == 'POST':
        role = request.form.get('role')
        if not role in ['customer', 'creator']: flash("Please select a role.", 'error'); return redirect(request.url)
        try:
            user_id, email = session.get('user_id'), session.get('email')
            user_data = {'uid': user_id, 'email': email, 'role': role, 'createdAt': firestore.SERVER_TIMESTAMP, 'displayName': f"user_{user_id[:6]}"}
            db.collection('users').document(user_id).set(user_data)
            session['role'] = role
            return redirect(url_for('dashboard_page'))
        except Exception: flash("An error occurred.", "error"); return redirect(request.url)
    return render_template('auth/select_role.html', page_title="Choose Your Role")

@app.route('/auth/session_login', methods=['POST'])
def session_login():
    try:
        id_token = request.headers.get('Authorization', '').split('Bearer ')[-1]
        decoded_token = admin_auth.verify_id_token(id_token)
        session.clear()
        session['user_id'], session['email'] = decoded_token['uid'], decoded_token.get('email')
        user_doc = db.collection('users').document(session['user_id']).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data.get('isDisabled', False): session.clear(); return jsonify({"error": "This account has been disabled."}), 403
            session['role'], session['isAdmin'] = user_data.get('role'), user_data.get('isAdmin', False)
        else: session['role'], session['isAdmin'] = None, False
        return jsonify({"status": "success", "redirect": '/dashboard' if session.get('role') else '/select-role'}), 200
    except admin_auth.InvalidIdTokenError: return jsonify({"error": "Invalid token, please log in again."}), 401
    except Exception: traceback.print_exc(); return jsonify({"error": "Authentication failed."}), 401

@app.route('/auth/session_logout', methods=['POST'])
def session_logout():
    session.clear(); return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)