import os
import time
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g, jsonify, abort, send_from_directory, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

from config import Config
from database import get_db, close_db, init_db
import models
from translations import get_text, TRANSLATIONS

app = Flask(__name__)
app.config.from_object(Config)

# Register database teardown
app.teardown_appcontext(close_db)

@app.template_filter('date_str')
def date_str_filter(val):
    if not val:
        return ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val)[:10]

# Ensure upload folders exist
os.makedirs(Config.REFERENCE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.ARTWORK_UPLOAD_FOLDER, exist_ok=True)

# Context processor to inject common settings and multi-language support into all templates
@app.context_processor
def inject_site_settings():
    settings = models.get_all_settings()
    # Format WhatsApp number for direct wa.me link
    raw_wa = settings.get('whatsapp_number', '919359096231')
    clean_wa = "".join(filter(str.isdigit, raw_wa))
    
    # Active language determination (session -> cookie -> default 'en')
    current_lang = session.get('lang') or request.cookies.get('site_lang') or 'en'
    if current_lang not in ['en', 'mr', 'hi']:
        current_lang = 'en'
        
    def translate(key, default=None):
        return get_text(current_lang, key, default)

    cats = models.get_all_categories()
    cat_names = [c['name'] for c in cats]

    return {
        'site_settings': settings,
        'clean_whatsapp': clean_wa,
        'current_year': time.strftime("%Y"),
        'current_lang': current_lang,
        '_': translate,
        'all_categories': cats,
        'artwork_categories': cat_names
    }

@app.route('/set-language/<lang_code>')
def set_language(lang_code):
    if lang_code not in ['en', 'mr', 'hi']:
        lang_code = 'en'
    session['lang'] = lang_code
    
    # Redirect back to referrer or home
    ref = request.referrer
    if not ref or request.path in ref:
        ref = url_for('home')
        
    resp = redirect(ref)
    resp.set_cookie('site_lang', lang_code, max_age=30*24*3600, samesite='Lax')
    return resp

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def validate_and_save_image(file_storage, folder):
    if not file_storage or file_storage.filename == '':
        return None
    if not allowed_file(file_storage.filename):
        return False
    
    orig_name = secure_filename(file_storage.filename)
    ext = orig_name.rsplit('.', 1)[1].lower()
    unique_name = f"{int(time.time())}_{os.urandom(4).hex()}.{ext}"
    target_path = os.path.join(folder, unique_name)

    try:
        file_storage.save(target_path)
        # Verify it's a real image
        with Image.open(target_path) as img:
            img.verify()
        return unique_name
    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)
        return False

# Admin Authentication Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in to access the admin area.', 'warning')
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# CUSTOMER FACING ROUTES
# ==========================================

@app.route('/')
def home():
    featured_artworks = models.get_featured_artworks(limit=6)
    reviews = models.get_approved_reviews(limit=4)
    homepage_images = models.get_homepage_images(only_active=True)
    categories = models.get_all_categories()
    return render_template(
        'index.html',
        featured_artworks=featured_artworks,
        reviews=reviews,
        homepage_images=homepage_images,
        categories=categories
    )

@app.route('/artworks')
def artworks():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '').strip()
    artwork_list = models.get_artworks(category=category, search=search, only_available=False)
    categories = models.get_all_categories()
    return render_template(
        'artworks.html',
        artworks=artwork_list,
        selected_category=category,
        search_query=search,
        categories=categories
    )

@app.route('/artworks/<int:artwork_id>')
def artwork_detail(artwork_id):
    artwork = models.get_artwork_by_id(artwork_id)
    if not artwork:
        abort(404)
    return render_template('artwork_detail.html', artwork=artwork)

@app.route('/order', methods=['GET', 'POST'])
def custom_order():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        category = request.form.get('category', '').strip()
        size_canvas = request.form.get('size_canvas', '').strip()
        num_faces = int(request.form.get('num_faces', 1) or 1)
        framing = request.form.get('framing', 'Unframed').strip()
        description = request.form.get('description', '').strip()
        instructions = request.form.get('instructions', '').strip()
        estimated_price_raw = request.form.get('estimated_price', '0')
        artwork_id_raw = request.form.get('artwork_id', None)

        artwork_id = int(artwork_id_raw) if artwork_id_raw and artwork_id_raw.isdigit() else None

        # Validation
        errors = []
        if not name or len(name) < 2:
            errors.append('Please provide your full name.')
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) < 10:
            errors.append('Please provide a valid 10-digit mobile number.')
        if not category:
            errors.append('Please select an artwork category.')
        if not size_canvas:
            errors.append('Please select a paper / canvas size.')
        if not description or len(description) < 10:
            errors.append('Please provide a brief description of what you would like (at least 10 characters).')

        reference_filename = None
        if 'reference_photo' in request.files:
            file = request.files['reference_photo']
            if file and file.filename != '':
                saved = validate_and_save_image(file, Config.REFERENCE_UPLOAD_FOLDER)
                if saved is False:
                    errors.append('Uploaded reference photo must be a valid image (PNG, JPG, JPEG, WEBP) under 16MB.')
                else:
                    reference_filename = saved

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('custom_order.html', form_data=request.form)

        try:
            estimated_price = float(estimated_price_raw) if estimated_price_raw else 1500.0
        except ValueError:
            estimated_price = 1500.0

        customer_id = models.find_or_create_customer(name, phone, email, address)
        order_id, order_code = models.create_order(
            customer_id=customer_id,
            category=category,
            size_canvas=size_canvas,
            num_faces=num_faces,
            framing=framing,
            description=description,
            instructions=instructions,
            reference_photo=reference_filename,
            estimated_price=estimated_price,
            artwork_id=artwork_id
        )

        flash(f'Your custom art request #{order_code} has been successfully submitted!', 'success')
        return redirect(url_for('order_confirmation', order_code=order_code))

    # Pre-select category or artwork if passed in query string
    pre_category = request.args.get('category', '')
    pre_artwork_id = request.args.get('artwork_id', '')
    pre_artwork = None
    if pre_artwork_id and pre_artwork_id.isdigit():
        pre_artwork = models.get_artwork_by_id(int(pre_artwork_id))
        if pre_artwork and not pre_category:
            pre_category = pre_artwork['category']

    return render_template(
        'custom_order.html',
        pre_category=pre_category,
        pre_artwork=pre_artwork
    )

@app.route('/order/confirmation/<order_code>')
def order_confirmation(order_code):
    db = get_db()
    order = db.execute("""
        SELECT o.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email, c.address as customer_address
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE UPPER(o.order_code) = UPPER(?)
    """, (order_code.strip(),)).fetchone()
    if not order:
        flash('Order not found.', 'warning')
        return redirect(url_for('track_order'))
    return render_template('order_confirmation.html', order=order)

@app.route('/track', methods=['GET', 'POST'])
def track_order():
    order = None
    progress_history = []
    has_searched = False
    order_code_input = request.args.get('order_code', '')
    phone_input = request.args.get('phone', '')

    if request.method == 'POST':
        order_code_input = request.form.get('order_code', '').strip()
        phone_input = request.form.get('phone', '').strip()
        has_searched = True

        if not order_code_input or not phone_input:
            flash('Please enter both your Order ID and registered mobile number.', 'warning')
        else:
            order = models.get_order_by_code_and_phone(order_code_input, phone_input)
            if not order:
                flash('No order found matching this Order ID and mobile number. Please double check your details.', 'danger')
            else:
                progress_history = models.get_order_progress(order['id'])
    elif order_code_input and phone_input:
        has_searched = True
        order = models.get_order_by_code_and_phone(order_code_input, phone_input)
        if order:
            progress_history = models.get_order_progress(order['id'])

    return render_template(
        'track_order.html',
        order=order,
        progress_history=progress_history,
        has_searched=has_searched,
        order_code_input=order_code_input,
        phone_input=phone_input
    )

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        rating_raw = request.form.get('rating', '5')
        category = request.form.get('category', '').strip()
        comment = request.form.get('comment', '').strip()
        order_code = request.form.get('order_code', '').strip()

        order_id = None
        if order_code:
            db = get_db()
            ord_row = db.execute("SELECT id FROM orders WHERE UPPER(order_code) = UPPER(?)", (order_code,)).fetchone()
            if ord_row:
                order_id = ord_row['id']

        if not customer_name or not comment:
            flash('Please provide your name and your review feedback.', 'danger')
        else:
            try:
                rating = max(1, min(5, int(rating_raw)))
            except ValueError:
                rating = 5
            models.create_review(customer_name, rating, category, comment, order_id=order_id)
            flash('Thank you for your review! It has been submitted and will be displayed once verified by Vinit.', 'success')
            return redirect(url_for('reviews'))

    approved_reviews = models.get_approved_reviews(limit=50)
    return render_template('reviews.html', reviews=approved_reviews)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Please fill in your name, email and message.', 'danger')
        else:
            models.create_inquiry(name, email, phone, subject, message)
            flash('Thank you! Your message has been sent to Vinit. We will reach out shortly.', 'success')
            return redirect(url_for('contact'))

    return render_template('contact.html')

# ==========================================
# ADMIN DASHBOARD ROUTES
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()

        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            session['admin_name'] = admin['name']
            flash(f"Welcome back, {admin['name']}!", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('admin_dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    stats = models.get_order_stats()
    recent_orders = models.get_all_orders(limit=None)[:7]
    pending_reviews = models.get_all_reviews(filter_status='pending')[:5]
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_orders=recent_orders,
        pending_reviews=pending_reviews
    )

# Manage Artworks
@app.route('/admin/artworks')
@admin_required
def admin_artworks():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '').strip()
    artworks = models.get_artworks(category=category, search=search, only_available=False)
    return render_template('admin/artworks.html', artworks=artworks, selected_category=category, search_query=search)

@app.route('/admin/artworks/new', methods=['GET', 'POST'])
@admin_required
def admin_artwork_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = float(request.form.get('price', 0) or 0)
        dimensions = request.form.get('dimensions', '').strip()
        medium = request.form.get('medium', '').strip()
        is_featured = 1 if request.form.get('is_featured') else 0
        is_available = 1 if request.form.get('is_available') else 0
        show_price = 1 if request.form.get('show_price') else 0

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                saved = validate_and_save_image(file, Config.ARTWORK_UPLOAD_FOLDER)
                if saved:
                    image_path = f"uploads/artworks/{saved}"
                else:
                    flash('Invalid image file. Please upload PNG, JPG, or WEBP.', 'danger')
                    return render_template('admin/artwork_form.html', artwork=None)

        if not image_path:
            # Fallback to demo image placeholder if no file uploaded
            image_path = "images/demo/other_art_1.jpg"

        models.create_artwork(
            title=title,
            category=category,
            description=description,
            price=price,
            dimensions=dimensions,
            medium=medium,
            image_path=image_path,
            is_featured=is_featured,
            is_available=is_available,
            show_price=show_price
        )
        flash('New artwork added to catalog successfully!', 'success')
        return redirect(url_for('admin_artworks'))

    return render_template('admin/artwork_form.html', artwork=None)

@app.route('/admin/artworks/edit/<int:artwork_id>', methods=['GET', 'POST'])
@admin_required
def admin_artwork_edit(artwork_id):
    artwork = models.get_artwork_by_id(artwork_id)
    if not artwork:
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = float(request.form.get('price', 0) or 0)
        dimensions = request.form.get('dimensions', '').strip()
        medium = request.form.get('medium', '').strip()
        is_featured = 1 if request.form.get('is_featured') else 0
        is_available = 1 if request.form.get('is_available') else 0
        show_price = 1 if request.form.get('show_price') else 0

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                saved = validate_and_save_image(file, Config.ARTWORK_UPLOAD_FOLDER)
                if saved:
                    image_path = f"uploads/artworks/{saved}"

        models.update_artwork(
            artwork_id=artwork_id,
            title=title,
            category=category,
            description=description,
            price=price,
            dimensions=dimensions,
            medium=medium,
            image_path=image_path,
            is_featured=is_featured,
            is_available=is_available,
            show_price=show_price
        )
        flash('Artwork details updated successfully!', 'success')
        return redirect(url_for('admin_artworks'))

    return render_template('admin/artwork_form.html', artwork=artwork)

@app.route('/admin/artworks/delete/<int:artwork_id>', methods=['POST'])
@admin_required
def admin_artwork_delete(artwork_id):
    models.delete_artwork(artwork_id)
    flash('Artwork deleted from catalog.', 'info')
    return redirect(url_for('admin_artworks'))

# Manage Orders
@app.route('/admin/orders')
@admin_required
def admin_orders():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    orders = models.get_all_orders(status_filter=status, search=search)
    stats = models.get_order_stats()
    return render_template('admin/orders.html', orders=orders, current_status=status, search_query=search, stats=stats)

@app.route('/admin/orders/<int:order_id>', methods=['GET', 'POST'])
@admin_required
def admin_order_detail(order_id):
    order = models.get_order_by_id(order_id)
    if not order:
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_details':
            status = request.form.get('status')
            payment_status = request.form.get('payment_status')
            final_price = float(request.form.get('final_price') or order['estimated_price'] or 0)
            est_date = request.form.get('estimated_completion_date', '')
            admin_notes = request.form.get('admin_notes', '')

            models.update_order_details(
                order_id=order_id,
                status=status,
                payment_status=payment_status,
                final_price=final_price,
                est_date=est_date,
                admin_notes=admin_notes
            )
            flash('Order specifications and status updated successfully!', 'success')
        elif action == 'add_progress':
            stage = request.form.get('stage')
            notes = request.form.get('notes')
            progress_image_path = None
            if 'progress_image' in request.files:
                file = request.files['progress_image']
                if file and file.filename != '':
                    saved = validate_and_save_image(file, Config.ARTWORK_UPLOAD_FOLDER)
                    if saved:
                        progress_image_path = f"uploads/artworks/{saved}"

            if stage:
                models.add_order_progress(
                    order_id=order_id,
                    stage=stage,
                    notes=notes,
                    image_path=progress_image_path,
                    updated_by=session.get('admin_name', 'Vinit Mhatre')
                )
                flash(f'New milestone "{stage}" with progress update recorded.', 'success')

        return redirect(url_for('admin_order_detail', order_id=order_id))

    progress = models.get_order_progress(order_id)
    return render_template('admin/order_detail.html', order=order, progress=progress)

# Manage Customers
@app.route('/admin/customers')
@admin_required
def admin_customers():
    customers = models.get_all_customers_with_summary()
    return render_template('admin/customers.html', customers=customers)

@app.route('/admin/customers/<int:customer_id>')
@admin_required
def admin_customer_detail(customer_id):
    customer, orders = models.get_customer_with_orders(customer_id)
    if not customer:
        abort(404)
    return render_template('admin/customer_detail.html', customer=customer, orders=orders)

# Manage Reviews
@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    status = request.args.get('status', 'all')
    reviews = models.get_all_reviews(filter_status=status)
    return render_template('admin/reviews.html', reviews=reviews, current_status=status)

@app.route('/admin/reviews/action/<int:review_id>/<action>', methods=['POST'])
@admin_required
def admin_review_action(review_id, action):
    if action == 'approve':
        models.update_review_status(review_id, 1)
        flash('Review approved and published on website!', 'success')
    elif action == 'reject':
        models.update_review_status(review_id, -1)
        flash('Review marked as rejected.', 'warning')
    elif action == 'delete':
        models.delete_review(review_id)
        flash('Review deleted permanently.', 'info')
    return redirect(url_for('admin_reviews'))

# Website Settings
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        fields = [
            'artist_name', 'artist_role', 'tagline', 'short_bio', 'about_story',
            'creative_process', 'whatsapp_number', 'instagram_url', 'contact_email',
            'contact_phone', 'studio_address', 'upi_id',
            'starting_price_pencil', 'starting_price_colour', 'starting_price_rangoli',
            'starting_price_watercolour', 'starting_price_fabric', 'starting_price_decorative',
            'starting_price_other'
        ]
        updates = {f: request.form.get(f, '') for f in fields}
        models.update_settings_dict(updates)
        flash('Website settings and pricing matrix updated successfully!', 'success')
        return redirect(url_for('admin_settings'))

    settings = models.get_all_settings()
    return render_template('admin/settings.html', settings=settings)

# Inquiries
@app.route('/admin/inquiries')
@admin_required
def admin_inquiries():
    inquiries = models.get_inquiries()
    return render_template('admin/inquiries.html', inquiries=inquiries)

# ==========================================
# DYNAMIC CATEGORY MANAGEMENT
# ==========================================
@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', '🎨').strip()
        display_order = int(request.form.get('display_order', 0) or 0)
        
        if not name:
            flash('Category name is required.', 'danger')
        else:
            existing = models.get_category_by_name(name)
            if existing:
                flash(f'Category "{name}" already exists.', 'warning')
            else:
                models.create_category(name, description, icon, display_order)
                flash(f'Category "{name}" created successfully and now available across the site!', 'success')
        return redirect(url_for('admin_categories'))

    categories = models.get_all_categories()
    db = get_db()
    cat_counts = {}
    for row in db.execute("SELECT category, COUNT(*) as c FROM artworks GROUP BY category").fetchall():
        cat_counts[row['category']] = row['c']

    return render_template('admin/categories.html', categories=categories, cat_counts=cat_counts)

@app.route('/admin/categories/edit/<int:category_id>', methods=['POST'])
@admin_required
def admin_category_edit(category_id):
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '🎨').strip()
    display_order = int(request.form.get('display_order', 0) or 0)

    if not name:
        flash('Category name cannot be empty.', 'danger')
    else:
        models.update_category(category_id, name, description, icon, display_order)
        flash(f'Category "{name}" updated successfully! Catalog and filters updated.', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_category_delete(category_id):
    cat = models.get_category_by_id(category_id)
    if cat:
        models.delete_category(category_id)
        flash(f'Category "{cat["name"]}" deleted.', 'info')
    return redirect(url_for('admin_categories'))

# ==========================================
# DYNAMIC HOMEPAGE IMAGE MANAGEMENT
# ==========================================
@app.route('/admin/homepage-images', methods=['GET', 'POST'])
@admin_required
def admin_homepage_images():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        badge_text = request.form.get('badge_text', '').strip()
        link_url = request.form.get('link_url', '').strip()
        sort_order = int(request.form.get('sort_order', 0) or 0)
        is_active = 1 if request.form.get('is_active') else 0

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                saved = validate_and_save_image(file, Config.ARTWORK_UPLOAD_FOLDER)
                if saved:
                    image_path = f"uploads/artworks/{saved}"
                else:
                    flash('Invalid image file. Please upload PNG, JPG, or WEBP.', 'danger')
                    return redirect(url_for('admin_homepage_images'))

        if not image_path:
            flash('Please upload an image file for the home page.', 'danger')
            return redirect(url_for('admin_homepage_images'))

        models.create_homepage_image(
            title=title,
            description=description,
            image_path=image_path,
            badge_text=badge_text,
            link_url=link_url,
            sort_order=sort_order,
            is_active=is_active
        )
        flash('New homepage showcase image added successfully!', 'success')
        return redirect(url_for('admin_homepage_images'))

    images = models.get_all_homepage_images()
    return render_template('admin/homepage_images.html', images=images)

@app.route('/admin/homepage-images/edit/<int:image_id>', methods=['POST'])
@admin_required
def admin_homepage_image_edit(image_id):
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    badge_text = request.form.get('badge_text', '').strip()
    link_url = request.form.get('link_url', '').strip()
    sort_order = int(request.form.get('sort_order', 0) or 0)
    is_active = 1 if request.form.get('is_active') else 0

    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            saved = validate_and_save_image(file, Config.ARTWORK_UPLOAD_FOLDER)
            if saved:
                image_path = f"uploads/artworks/{saved}"

    models.update_homepage_image(
        img_id=image_id,
        title=title,
        description=description,
        image_path=image_path,
        badge_text=badge_text,
        link_url=link_url,
        sort_order=sort_order,
        is_active=is_active
    )
    flash('Homepage image details updated successfully!', 'success')
    return redirect(url_for('admin_homepage_images'))

@app.route('/admin/homepage-images/delete/<int:image_id>', methods=['POST'])
@admin_required
def admin_homepage_image_delete(image_id):
    models.delete_homepage_image(image_id)
    flash('Homepage image removed.', 'info')
    return redirect(url_for('admin_homepage_images'))

# ==========================================
# ABOUT SECTION MANAGEMENT (NO PHOTO)
# ==========================================
@app.route('/admin/about', methods=['GET', 'POST'])
@admin_required
def admin_about():
    if request.method == 'POST':
        fields = [
            'about_name', 'about_title', 'about_intro', 'about_bio',
            'about_experience', 'about_skills', 'about_artwork_description',
            'creative_process'
        ]
        updates = {f: request.form.get(f, '') for f in fields}
        models.update_settings_dict(updates)
        flash("About section details updated successfully! No photo is displayed in the About section.", 'success')
        return redirect(url_for('admin_about'))

    settings = models.get_all_settings()
    return render_template('admin/about_mgmt.html', settings=settings)

# ==========================================
# MULTI-LANGUAGE MANAGEMENT
# ==========================================
@app.route('/admin/languages')
@admin_required
def admin_languages():
    languages = [
        {'code': 'en', 'name': 'English', 'native': 'English', 'default': True, 'keys': len(TRANSLATIONS.get('en', {}))},
        {'code': 'mr', 'name': 'Marathi', 'native': 'मराठी', 'default': False, 'keys': len(TRANSLATIONS.get('mr', {}))},
        {'code': 'hi', 'name': 'Hindi', 'native': 'हिंदी', 'default': False, 'keys': len(TRANSLATIONS.get('hi', {}))},
    ]
    return render_template('admin/languages.html', languages=languages)

# ==========================================
# ADMIN ACCOUNT CREDENTIALS MANAGEMENT
# ==========================================
@app.route('/admin/account', methods=['GET', 'POST'])
@admin_required
def admin_account():
    admin = models.get_admin_by_id(session['admin_id'])
    if not admin:
        flash('Admin session expired. Please log in again.', 'danger')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_username = request.form.get('username', '').strip()
        new_name = request.form.get('name', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Verify current password
        if not check_password_hash(admin['password_hash'], current_password):
            flash('Current password is incorrect. Please re-enter your current password.', 'danger')
            return render_template('admin/account.html', admin=admin)

        if not new_username:
            flash('Username cannot be empty.', 'danger')
            return render_template('admin/account.html', admin=admin)

        new_hash = None
        if new_password:
            if len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'danger')
                return render_template('admin/account.html', admin=admin)
            if new_password != confirm_password:
                flash('New password and confirmation do not match.', 'danger')
                return render_template('admin/account.html', admin=admin)
            new_hash = generate_password_hash(new_password)

        models.update_admin_profile(admin['id'], new_username, new_hash, new_name)
        session['admin_username'] = new_username
        if new_name:
            session['admin_name'] = new_name

        flash('Admin credentials updated successfully!', 'success')
        return redirect(url_for('admin_account'))

    return render_template('admin/account.html', admin=admin)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
