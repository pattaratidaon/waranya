import os
from uuid import uuid4
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="template")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "simple-admin-secret-key"
app.config["UPLOAD_FOLDER"] = "static/uploads"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"
DEFAULT_IMAGE_URL = "/static/product-placeholder.svg"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
PRODUCT_IMAGE_MAP = {
	"กล้องดิจิทัล": "/static/product-images/camera.svg",
	"รองเท้าผ้าใบ": "/static/product-images/shoes.svg",
	"สมาร์ทวอทช์": "/static/product-images/smartwatch.svg",
	"กระเป๋าเป้": "/static/product-images/backpack.svg",
	"หูฟัง": "/static/product-images/headphones.svg",
	"ลำโพง": "/static/product-images/speaker.svg",
	"คอมพิวเตอร์": "/static/product-images/computer.svg",
	"โน๊ตบุ๊ค": "/static/product-images/laptop.svg",
}

db = SQLAlchemy(app)


def admin_required(view_func):
	@wraps(view_func)
	def wrapped_view(*args, **kwargs):
		if not session.get("is_admin"):
			return redirect(url_for("login"))
		return view_func(*args, **kwargs)

	return wrapped_view


class Product(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(200), nullable=False)
	price = db.Column(db.Float, nullable=False)
	image_url = db.Column(db.String(500), nullable=True)


def seed_products_if_empty():
	sample_products = [
		Product(
			name="กล้องดิจิทัล",
			price=4990.0,
			image_url=PRODUCT_IMAGE_MAP["กล้องดิจิทัล"],
		),
		Product(
			name="รองเท้าผ้าใบ",
			price=1290.0,
			image_url=PRODUCT_IMAGE_MAP["รองเท้าผ้าใบ"],
		),
		Product(
			name="สมาร์ทวอทช์",
			price=2490.0,
			image_url=PRODUCT_IMAGE_MAP["สมาร์ทวอทช์"],
		),
		Product(
			name="กระเป๋าเป้",
			price=990.0,
			image_url=PRODUCT_IMAGE_MAP["กระเป๋าเป้"],
		),
		Product(
			name="หูฟัง",
			price=790.0,
			image_url=PRODUCT_IMAGE_MAP["หูฟัง"],
		),
		Product(
			name="ลำโพง",
			price=1590.0,
			image_url=PRODUCT_IMAGE_MAP["ลำโพง"],
		),
		Product(
			name="คอมพิวเตอร์",
			price=22900.0,
			image_url=PRODUCT_IMAGE_MAP["คอมพิวเตอร์"],
		),
		Product(
			name="โน๊ตบุ๊ค",
			price=18900.0,
			image_url=PRODUCT_IMAGE_MAP["โน๊ตบุ๊ค"],
		),
	]

	existing_names = {product.name for product in Product.query.all()}
	products_to_add = [product for product in sample_products if product.name not in existing_names]

	if not products_to_add:
		return

	db.session.add_all(products_to_add)
	db.session.commit()


def apply_local_product_images():
	products = Product.query.all()
	has_changes = False

	for product in products:
		mapped_url = PRODUCT_IMAGE_MAP.get(product.name)
		if mapped_url and product.image_url != mapped_url:
			product.image_url = mapped_url
			has_changes = True

	if has_changes:
		db.session.commit()


def resolve_product_image(name, image_url):
	if image_url:
		return image_url

	mapped_url = PRODUCT_IMAGE_MAP.get(name)
	if mapped_url:
		return mapped_url

	return DEFAULT_IMAGE_URL


def is_allowed_image(filename):
	if "." not in filename:
		return False
	file_extension = filename.rsplit(".", 1)[1].lower()
	return file_extension in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage):
	if not file_storage or not file_storage.filename:
		return None

	if not is_allowed_image(file_storage.filename):
		return None

	filename = secure_filename(file_storage.filename)
	file_extension = filename.rsplit(".", 1)[1].lower()
	new_filename = f"{uuid4().hex}.{file_extension}"

	upload_folder = app.config["UPLOAD_FOLDER"]
	os.makedirs(upload_folder, exist_ok=True)
	save_path = os.path.join(upload_folder, new_filename)
	file_storage.save(save_path)

	return f"/static/uploads/{new_filename}"


@app.route("/")
def home():
	products = Product.query.all()
	return render_template("index.html", products=products, default_image_url=DEFAULT_IMAGE_URL)


@app.route("/api/products")
def api_products():
	products = Product.query.order_by(Product.id.asc()).all()
	result = []

	for product in products:
		result.append(
			{
				"id": product.id,
				"name": product.name,
				"price": product.price,
				"image_url": product.image_url or DEFAULT_IMAGE_URL,
			}
		)

	return jsonify(result)


@app.route("/login", methods=["GET", "POST"])
def login():
	if session.get("is_admin"):
		return redirect(url_for("admin_dashboard"))

	if request.method == "POST":
		username = request.form.get("username", "").strip()
		password = request.form.get("password", "").strip()

		if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
			session["is_admin"] = True
			return redirect(url_for("admin_dashboard"))

		return redirect(url_for("login", error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"))

	return render_template("login.html")


@app.route("/logout")
def logout():
	session.clear()
	return redirect(url_for("login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
	products = Product.query.order_by(Product.id.desc()).all()
	return render_template("admin.html", products=products, default_image_url=DEFAULT_IMAGE_URL)


@app.route("/admin/add", methods=["POST"])
@admin_required
def add_product():
	name = request.form.get("name", "").strip()
	price_text = request.form.get("price", "").strip()
	image_url = request.form.get("image_url", "").strip()
	image_file = request.files.get("image_file")

	if not name or not price_text:
		return redirect(url_for("admin_dashboard"))

	try:
		price = float(price_text)
	except ValueError:
		return redirect(url_for("admin_dashboard"))

	uploaded_image_url = save_uploaded_image(image_file)
	if uploaded_image_url:
		image_url = uploaded_image_url

	image_url = resolve_product_image(name, image_url)

	product = Product(name=name, price=price, image_url=image_url)
	db.session.add(product)
	db.session.commit()
	return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
	product = Product.query.get_or_404(product_id)
	db.session.delete(product)
	db.session.commit()
	return redirect(url_for("admin_dashboard"))


@app.route("/admin/update/<int:product_id>", methods=["POST"])
@admin_required
def update_product(product_id):
	product = Product.query.get_or_404(product_id)
	name = request.form.get("name", "").strip()
	price_text = request.form.get("price", "").strip()
	image_url = request.form.get("image_url", "").strip()
	image_file = request.files.get("image_file")

	if not name or not price_text:
		return redirect(url_for("admin_dashboard"))

	try:
		price = float(price_text)
	except ValueError:
		return redirect(url_for("admin_dashboard"))

	uploaded_image_url = save_uploaded_image(image_file)
	if uploaded_image_url:
		final_image_url = uploaded_image_url
	elif image_url:
		final_image_url = image_url
	else:
		final_image_url = product.image_url or resolve_product_image(name, "")

	product.name = name
	product.price = price
	product.image_url = final_image_url
	db.session.commit()
	return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
	with app.app_context():
		os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
		db.create_all()
		seed_products_if_empty()
		apply_local_product_images()
	app.run(debug=True)
