from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from utils import turkce_format
from dotenv import load_dotenv
import os, time, random

load_dotenv()

app= Flask(__name__)
app.secret_key= os.getenv('SECRET_KEY')
app.config["SQLALCHEMY_DATABASE_URI"]= os.getenv('DATABASE_URL')
app.config['IMAGE_UPLOAD_FOLDER']= 'static/uploads/images'
app.config['VIDEO_UPLOAD_FOLDER']= 'static/uploads/videos'

app.config["MAIL_SERVER"]= 'smtp.gmail.com'
app.config["MAIL_PORT"]= 587
app.config["MAIL_USE_TLS"]= True
app.config["MAIL_USERNAME"]= 'app.expertshop@gmail.com'
app.config["MAIL_PASSWORD"]= os.getenv('MAIL_PASSWORD')
mail= Mail(app)

login_manager= LoginManager()
login_manager.init_app(app)
login_manager.login_view= 'login'

@login_manager.user_loader
def load_user(user_id):
    if not user_id or user_id == "None":
        return None

    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

db = SQLAlchemy(app)

image_extensions_allowed= {'png', 'jpg', 'jpeg'}
video_extensions_allowed= {'mp4', 'avi', 'mov', 'webm'}
category_fullnames= {
    "dekorasyon": "Ev & Dekorasyon",
    "elektronik": "Elektronik",
    "spor": "Spor & Outdoor",
    "giyim": "Giyim",
    "kitaplar": "Kitap & Kırtasiye",
    "kozmetik": "Kişisel Bakım & Kozmetik",
    "evcilhayvan": "Evcil Hayvan Ürünleri",
    "diger": "Diğer"
}

EMAIL_VERIFICATION_ENABLED = False

# ----------------------------------------------------- Sınıflar -----------------------------------------------------

class User(db.Model, UserMixin):
    id= db.Column(db.Integer, primary_key=True)
    username= db.Column(db.String, unique=True, nullable=False)
    email= db.Column(db.String, nullable=False)
    password= db.Column(db.String, nullable=False)
    role= db.Column(db.String, default="user")

class Product(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    name= db.Column(db.Text, nullable=False)
    description= db.Column(db.String, nullable=False)
    price= db.Column(db.Float, nullable=False)
    category_id= db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    seller_id= db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image= db.Column(db.String, nullable=True)
    video= db.Column(db.String, nullable=True)
    sales= db.Column(db.Integer, nullable=False, default=0)
    total_earnings= db.Column(db.Float, nullable=False, default=0)
    stocks= db.Column(db.Integer, nullable=False, default=10)

    comments= db.relationship('Comment', backref="product", cascade="all, delete-orphan", lazy=True)

class Category(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    name= db.Column(db.String(50), nullable=False)

    products= db.relationship('Product', backref="category", lazy=True)

class Cart(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    user_id= db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id= db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity= db.Column(db.Integer, default=1)
    
    user= db.relationship("User", backref="cart_products")
    product= db.relationship("Product", backref="cart_items")

class Comment(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    user_id= db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id= db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    content= db.Column(db.String(300), nullable=False)
    created_at= db.Column(db.String, nullable=False)

    user= db.relationship("User", backref="comments", lazy=True)

class Update(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    title= db.Column(db.String, nullable=False)
    date= db.Column(db.String, nullable=False)
    content= db.Column(db.String(500), nullable=False)

# ----------------------------------------------------- Anasayfa -----------------------------------------------------

@app.route('/')
def home():
    user= None
    if current_user.is_authenticated:
        user= User.query.get(current_user.id)
    products= Product.query.all()
    return render_template("home.html", user=user, products=products)

@app.route('/arama', methods=["GET"])
def search():
    query= request.args.get('search-box', '')
    if query:
        products= Product.query.filter(Product.name.ilike(f"%{query}%")).all()
    else:
        products= []
    return render_template("search_results.html", products=products, query=query)

@app.route('/kategori/<string:category_name>')
def category(category_name):
    category= Category.query.filter_by(name=category_name).first()
    if not category:
        category= Category(name=category_name)
        db.session.add(category)
        db.session.commit()

    category_fullname= category_fullnames[category_name]
    products= Product.query.filter_by(category_id=category.id).all()
    return render_template('category_filter.html', category_name=category_name, category_fullname=category_fullname, products=products)

# ----------------------------------------------------- Alışveriş -----------------------------------------------------

@app.route('/sepet')
@login_required
def cart():
    cart_products= Cart.query.filter_by(user_id=current_user.id).all()

    total_price= 0
    for item in cart_products:
        total_price+= item.product.price* item.quantity

    return render_template("cart.html", cart_products=cart_products, total_price=total_price)

@app.route('/sepete_ekle/<int:product_id>')
@login_required
def add_to_cart(product_id):
    user_id= current_user.id
    cart_product= Cart.query.filter_by(user_id=user_id, product_id=product_id).first()
    if cart_product:
        cart_product.quantity+=1
    else:
        new_cart_product=Cart(user_id=user_id, product_id=product_id, quantity=1)
        db.session.add(new_cart_product)
    
    db.session.commit()
    flash("Ürün sepete eklendi!", "success")
    return redirect(url_for("cart"))

@app.route('/sepetten_sil/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    cart_product= Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    db.session.delete(cart_product)
    db.session.commit()

    flash("Ürün sepetten silindi.", "success")
    return redirect(url_for("cart"))


@app.route('/sepeti_bosalt')
@login_required
def empty_cart():
    cart_products= Cart.query.filter_by(user_id=current_user.id).all()

    if not cart_products:
        flash("Sepetiniz boş!", "danger")
        return redirect(url_for("cart"))

    for item in cart_products:
        db.session.delete(item)
    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/urunsayisi_azalt/<int:product_id>')
@login_required
def decrease_quantity(product_id):
    cart_item= Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        if cart_item.quantity> 1:
            cart_item.quantity-= 1
        else:
            db.session.delete(cart_item)
        db.session.commit()
    return redirect(url_for('cart'))

@app.route('/urunsayisi_arttir/<int:product_id>')
def increase_quantity(product_id):
    cart_item= Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity+=1
    db.session.commit()
    return redirect(url_for("cart"))

# ----------------------------------------------------- Ödeme -----------------------------------------------------

@app.route('/odemeyap', methods=["GET", "POST"])
@login_required
def payment():
    cart_products= Cart.query.filter_by(user_id= current_user.id)
    total_price=0
    for item in cart_products:
        total_price+= item.product.price* item.quantity

    if request.method== "POST":
        cardnumber= request.form.get('cardnumber')
        expiry_date= request.form.get('expirydate')
        cvc= request.form.get('cvc')

        if not cardnumber or not expiry_date or not cvc:
            flash("Eksik giriş yaptınız!", "danger")
            return redirect(url_for('payment'))

        flash("Ödeme başarılı!", "success")
        return redirect(url_for('complete_purchase'))
    return render_template("payment.html", total_price=total_price)

@app.route('/alisverisi_tamamla')
@login_required
def complete_purchase():
    cart_products= Cart.query.filter_by(user_id=current_user.id).all()

    if not cart_products:
        flash("Sepetiniz boş!", "danger")
        return redirect(url_for("cart"))
    
    for item in cart_products:
        product= Product.query.get(item.product_id)
        if product:
            product.sales+= item.quantity
            product.total_earnings+= item.quantity* product.price
            product.stocks-= item.quantity
            db.session.delete(item)
        db.session.commit()

    return redirect(url_for('cart'))

# ----------------------------------------------------- Cüzdan -----------------------------------------------------

# İleride eklenecek

# ----------------------------------------------------- Ürünler -----------------------------------------------------

@app.route('/urun_ekle', methods=["GET", "POST"])
@login_required
def add_product():
    user= User.query.get(current_user.id)
    if not user or user.role != "seller":
        return abort(403)

    if request.method== "POST":
        name= request.form.get("product_name")
        description= request.form.get("product_desc")
        price= request.form.get("product_price")
        image= request.files.get("product_img")
        video= request.files.get("product_vid")
        category_name= request.form.get("product_category")

        category= Category.query.filter_by(name=category_name).first()
        if not category:
            category= Category(name=category_name)
            db.session.add(category)
            db.session.commit()
        if not name or not description or not price:
            flash("Form'daki tüm alanları doldurun!", "danger")
            return redirect(url_for("add_product"))

        price= float(price)

        product= Product(name= name,
        description=description,
        category_id=category.id,
        price=price,
        seller_id= user.id)

        db.session.add(product)
        db.session.commit()

        image_filename= None
        if image:
            file_ext= image.filename.rsplit('.', 1)[-1].lower()
            if file_ext in image_extensions_allowed:
                image_filename= f"{product.id}.{file_ext}"
                image.save(os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], image_filename))
                product.image= image_filename
                db.session.commit()
            else:
                flash("Bu uzantı uygun değil!", "danger")
                db.session.delete(product)
                db.session.commit()
                return redirect(url_for("add_product"))

        video_filename= None
        if video:
            file_ext= video.filename.rsplit('.', 1)[-1].lower()
            if file_ext in video_extensions_allowed:
                video_filename= f"{product.id}.{file_ext}"
                video.save(os.path.join(app.config['VIDEO_UPLOAD_FOLDER'], video_filename))
                product.video= video_filename
                db.session.commit()
            else:
                flash("Bu uzantı uygun değil!", "danger")
                db.session.delete(product)
                db.session.commit()

                return redirect(url_for("add_product"))
        flash("Ürün başarıyla eklendi!", "success")
        return redirect(url_for("my_shop"))
    return render_template("add_product.html", user=user)

@app.route('/urun/<int:product_id>')
def product_detail(product_id):
    product= Product.query.get_or_404(product_id)
    comments= Comment.query.filter_by(product_id=product.id).all()
    user=None
    if current_user.is_authenticated:
        user_id= current_user.id
        user= User.query.filter_by(id= user_id)
    return render_template("product_details.html", product=product, comments=comments, user=user)

@app.route('/urun_sil/<int:product_id>')
@login_required
def delete_product(product_id):
    user= User.query.get(current_user.id)
    product= Product.query.get_or_404(product_id)
    if not user or user.role!= "seller" or user.id!= product.seller_id:
        return abort(403)
    
    if product.image:
        image_location= os.path.join(app.config['UPLOAD_FOLDER'], product.image)
        os.remove(image_location)
    
    Cart.query.filter_by(product_id=product.id).delete()
    
    db.session.delete(product)
    db.session.commit()
    flash("Ürün silindi.", "success")
    return redirect(url_for('my_shop'))

@app.route('/magazam')
@login_required
def my_shop():
    user= User.query.get(current_user.id)
    if not user or user.role!= "seller":
        return abort(403)
    
    products= Product.query.filter_by(seller_id=current_user.id).all()
    total_revenue= sum([product.total_earnings for product in products])
    return render_template("dashboard.html", products=products, total_revenue=total_revenue)


@app.route('/stok_arttir/<int:product_id>')
@login_required
def increase_quantity_stocks(product_id):
    
    user_id= current_user.id
    product= Product.query.filter_by(seller_id= user_id, id= product_id).first()
    product.stocks+=1
    db.session.commit()
    return redirect(url_for("my_shop", user_id=user_id, product_id=product_id))

@app.route('/stok_azalt/<int:product_id>')
@login_required
def decrease_quantity_stocks(product_id):

    user_id= current_user.id
    product= Product.query.filter_by(seller_id=user_id, id=product_id).first()

    product.stocks-=1
    db.session.commit()
    return redirect(url_for("my_shop"))

# ----------------------------------------------------- Yorumlar -----------------------------------------------------

@app.route('/yorum_ekle', methods=["POST"])
@login_required
def add_comment():
    user_id= current_user.id
    product_id= request.form.get("product_id")

    content= request.form.get("add-comment")

    created_at= turkce_format(datetime.now())

    comment= Comment(
        user_id= user_id,
        product_id= product_id,
        content= content,
        created_at=created_at
    )
    
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('product_detail', product_id=product_id))

# ----------------------------------------------------- Güncellemeler -----------------------------------------------------

@app.route('/guncellemeler')
def updates():
    user=None
    if current_user.is_authenticated:
        user= User.query.get(current_user.id)
    
    updates= Update.query.all()

    return render_template("update.html", user=user, updates=updates)

@app.route('/guncelleme_ekle', methods=["GET", "POST"])
@login_required
def add_update():
    user= User.query.get(current_user.id)
    if user.role=="user" or user.role=="seller":
        return abort(403)

    if request.method== "POST":
        content= request.form.get("update_content")
        title= request.form.get("update_title")
        date= turkce_format(datetime.now())
        new_update= Update(
            title=title,
            date= date,
            content=content
        )

        db.session.add(new_update)
        db.session.commit()
        flash("Güncelleme notu eklendi!", "success")
        return redirect(url_for('updates'))

    return render_template("add_update.html")

# ----------------------------------------------------- Giriş ve Kayıt -----------------------------------------------------

@app.route('/giris', methods=['GET', 'POST'])
def login():
    if request.method== 'POST':
        username= request.form['username']
        password= request.form['password']
        user= User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f"Hoş geldiniz, {username}!", "success")
            return redirect(url_for('home'))
        flash("Kullanıcı adı veya şifre hatalı!", "danger")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/kayit', methods=["GET", "POST"])
def register():
    if request.method== "POST":
        username= request.form.get("username")
        password= request.form.get("password")
        email= request.form.get("email")
        role= request.form.get("role")
        
        if not username or not password or not role or not email:
            flash("Kullanıcı adı veya şifre boş olamaz!", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Bu kullanıcı adı zaten alınmış!", "danger")
            return redirect(url_for('register'))
        
        if not EMAIL_VERIFICATION_ENABLED:
            new_user = User(
                username=username,
                password=generate_password_hash(password),
                email=email,
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("home"))
        
        # Şifre güvenliği
        hashed_password= generate_password_hash(password)
        code= str(random.randint(100000, 999999))

        session["pending_user"]= {
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': role
        }
        session["verification_code"]=code
        session["code_time"]= time.time()
        msg= Message("Kayıt Doğrulama Kodu", sender="MAIL_USERNAME", recipients=[email])
        msg.html= render_template('email_verification.html', code=code)

        try:
            mail.send(msg)
            flash("Doğrulama kodu e-posta adresinize gönderildi!", "success")
            return redirect(url_for('verify_email'))
        except Exception as error:
            flash(f"E-posta gönderilirken bir hata oluştu!", "danger")
            print(f"E-posta gönderilirken hata oluştu: {error}")

    return render_template('register.html')

@app.route('/dogrulama', methods=["GET", "POST"])
def verify_email():
    if request.method== "POST":
        code= request.form.get("full_code")
        real_code= session.get("verification_code")
        if not code or not real_code:
            flash(f"Kodunuzun süresi dolmuş veya geçersiz! {real_code}", "danger")
            return redirect(url_for('verify_email'))
        
        if time.time()- session.get("code_time")> 5*60: # 5 dakika
            flash("Kodunuzun süresi dolmuş!", "danger")
            session.pop("pending_user", None)
            session.pop("verification_code", None)
            session.pop("code_time", None)
            return redirect(url_for('verify_email'))

        if code== real_code:
            pending= session.get("pending_user")
            if pending:
                new_user= User(
                    username= pending["username"],
                    email= pending["email"],
                    password= pending["password"],
                    role= pending["role"]
                )

                db.session.add(new_user)
                db.session.commit()
                session.pop("pending_user", None)
                session.pop("verification_code", None)
                session.pop("code_time", None)
                current_user.id= new_user.id
                flash(f"Kayıt başarılı! Hoşgeldiniz {new_user.username}", "success")
                return redirect(url_for('home'))
        else:
            flash("Kodunuz geçersiz!", "danger")
            return redirect(url_for('verify_email'))
    return render_template("verify.html")

@app.route('/cikis')
def logout():
    logout_user()
    return redirect(url_for('home'))

# ----------------------------------------------------- Özel komutlar -----------------------------------------------------

@app.route('/admin', methods=["GET", "POST"])
@login_required
def admin():
    user_id= current_user.id
    user= User.query.filter_by(id= user_id).first()

    if not user or user.role== "saler" or user.role=="user":
        return abort(403)

    users= User.query.all()
    products= Product.query.all()
    comments= Comment.query.all()

    if request.method== "POST":
        command= request.form.get("command").lower()
        action= request.form.get("action")
        if action== "banuser":
            target_user= User.query.get(command)
            if not target_user:
                flash(f"{command} id'sine sahip bir kullanıcı yok!", "danger")
                return redirect(url_for('admin'))
            
            user_products= Product.query.filter_by(seller_id= target_user.id).all()
            user_comments= Comment.query.filter_by(user_id= target_user.id).all()
            
            for user_comment in user_comments:
                db.session.delete(user_comment)

            for user_product in user_products:
                cart_items= Cart.query.filter_by(product_id= user_product.id).all()
                for item in cart_items:
                    db.session.delete(item)

                db.session.delete(user_product)

            db.session.delete(target_user)
            db.session.commit()
            flash("Kullanıcı engellendi!", "success")
            return redirect(url_for('admin'))                
        elif action== "deleteproduct":
            target_product= Product.query.get(command)
            if not target_product:
                flash(f"{command} sahip bir ürün yok!", "danger")
                return redirect(url_for('admin'))
            cart_items= Cart.query.filter_by(product_id=target_product.id).all()
            for item in cart_items:
                db.session.delete(item)
            db.session.delete(target_product)
            db.session.commit()
            flash("Ürün silindi!", "success")
            return redirect(url_for('admin'))
        elif action== "deletecomment":
            comment= Comment.query.get(command)
            if not comment:
                flash(f"{command} id'sine sahip bir yorum yok!", "danger")
                return redirect(url_for('admin'))
            
            db.session.delete(comment)
            db.session.commit()
            flash("Yorum silindi!", "success")
            return redirect(url_for('admin'))
        elif action== "giveadminrole":
            user= User.query.get(command)
            if not user:
                flash(f"{command} id'sine sahip bir kullanıcı yok!", "danger")
                return redirect(url_for('admin'))
            
            if user.role== "admin":
                flash(f"{user.username} zaten admin rolüne sahip", "success")
                return redirect(url_for('admin'))
            
            
            user.role= "admin"
            user_products= Product.query.filter_by(seller_id= user.id).all()
            db.session.commit()
            flash(f"{user.username} kullanıcısına admin rolü verildi! Rol: {user.role}", "success")
            return redirect(url_for('admin'))
        else:
            if command in ["products", "users", "comments"]:
                if command=="products":
                    for product in products:
                        cart_items= Cart.query.filter_by(product_id=product.id).all()
                        for item in cart_items:
                            db.session.delete(item)
                        db.session.delete(product)

                    db.session.commit()
                    flash("Tüm ürünler silindi!", "success")
                    return redirect(url_for('admin'))
                elif command=="users":
                    users= User.query.all()
                    for user in users:
                        if user.role== "admin":
                            continue
                            
                        user_comments= Comment.query.filter_by(user_id=user.id).all()
                        for user_comment in user_comments:
                            db.session.delete(user_comment)

                        user_products= Product.query.filter_by(seller_id=user.id).all()
                        for user_product in user_products:
                            cart_items= Cart.query.filter_by(product_id=user_product.id).all()
                            for item in cart_items:
                                db.session.delete(item)
                            db.session.delete(user_product)

                        db.session.delete(user)
                    db.session.commit()
                    flash("Tüm kullanıcılar silindi!", "success")
                    return redirect(url_for('admin'))
                else:
                    for comment in comments:
                        db.session.delete(comment)
                    db.session.commit()
                    flash("Tüm yorumlar silindi!", "success")
                    return redirect(url_for('admin'))
            else:
                flash("Bu komut geçersiz", "danger")    
                return redirect(url_for('admin'))
    
    return render_template("admin.html", users=users, products=products, comments=comments)

# ----------------------------------------------------- Hata Sayfaları -----------------------------------------------------
@app.errorhandler(404)
def page_not_found(error):
    return render_template("errors/error404.html"), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/error403.html"), 403

@app.errorhandler(500)
def internal_server_error(error):
    return render_template("errors/error500.html"), 500

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
