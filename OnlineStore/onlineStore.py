import pymongo, datetime, time, hashlib, binascii, os, json
from flask import Flask, jsonify, session, render_template, request, redirect, url_for, make_response
from bson import BSON, json_util
from bson.objectid import ObjectId
from decimal import Decimal
from datetime import datetime

def hash_password(password):
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
    password_hash = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, 100000)
    password_hash = binascii.hexlify(password_hash)
    return salt.decode("ascii"), password_hash.decode("ascii")

def check_password(salt, password_hash, password):
    hash = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt.encode("ascii"), 100000)
    hash = binascii.hexlify(hash).decode("ascii")
    return password_hash == hash

client = pymongo.MongoClient("mongodb+srv://DefaultUser:parksandrec1@cluster0-yyziz.mongodb.net/test?retryWrites=true&w=majority")
database = client["OnlineStore"]
customers_col = database["Customers"]
products_col = database["Products"]
sales_col = database["Sales"]

app = Flask(__name__)

@app.route('/')
def homepage():
    # On incoming request check if the user has any cookies
    if(request):
        if request.cookies.get("username") != None:
            return render_template("home.html", userdata=[request.cookies.get("username")])
        else:
            return render_template("home.html")
    # Catchall return
    return render_template("home.html")

@app.route('/', methods=['GET', 'POST'])
def login():
    # Get username and password entered
    if(request.form.get("form") == "login"):
        username = request.form.get("username")
        password = request.form.get("password")
        # Check if username exists in database
        if(customers_col.count_documents({"_id": username}, limit=1) != 0):
            userinfo = customers_col.find_one({"_id": username})
            # Check if the password matches
            if check_password(userinfo["salt"], userinfo["hash"], password):
                # Log in
                response = make_response(render_template("home.html", userdata=[username]))
                response.set_cookie("username", username)
                return response
        return homepage()
    else:
        return homepage()

# Force username cookie to expire
@app.route('/logout')
def logout():
    response = make_response(render_template("home.html"))
    response.set_cookie("username", "", expires=0)
    return response

@app.route('/getInventory', methods=["GET"])
def getInventory():
    if(request.method == "GET"):
        # Get all products listed
        products = products_col.find()
        json_data_list = []
        # Add them to an array and respond
        for product in products:
            doc = json.dumps(product, default=json_util.default)
            json_data_list.append(doc)
        return json.dumps(json_data_list)

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("Running register")
    #On form submission
    if(request.form.get("form") == "register"):
        # Get the registration data
        firstName = request.form.get("firstname")
        lastName = request.form.get("lastname")
        username = request.form.get("username")
        password = request.form.get("password")
        confirmPassword = request.form.get("confirmpassword")
        # Check if the password was entered correctly both times
        if(password == confirmPassword):
            # Check if that username is available
            if(customers_col.count_documents({"_id": username}, limit=1) != 0):
                print("Username already taken.")
                return render_template("register.html")
            else:
                print("Username available")
                # Create password hash
                password_hash = hash_password(password)
                # Create document for the user
                newCustomerDoc =\
                {\
                "_id": username,\
                "salt": password_hash[0],\
                "hash": password_hash[1],\
                "first_name": firstName,\
                "last_name": lastName,\
                "address_list": [],\
                "payment_option": [],\
                "cart": {"item": [], "quantity": []}
                }
                # Insert the user document into the collection
                customers_col.insert_one(newCustomerDoc)

                # Send the user to the main page
                return redirect('/')
    # Display page before form submission
    return render_template("register.html")

@app.route("/account", methods=["POST", "GET"])
def account():
    # Find the customer that is logged in
    username = request.cookies.get("username")
    # Get the orders that match their username
    orderList = sales_col.find({"customer_id": username})
    orderNames = []
    orderQuantities = []
    orderPrices = []
    orderShipping = []
    orderPayment = []
    # Go through each order and add the information to the lists
    for order in orderList:
        thisOrdersNames = []
        thisOrdersQuantities = []
        thisOrdersPrices = []
        thisOrdersShipping = order["address"]["firstname"] + " " + order["address"]["lastname"] + " " + order["address"]["street"] + " " + order["address"]["city"] + ", " + order["address"]["state"] + " " + order["address"]["country"]
        thisOrdersPayment = order["payment"]["creditcard"][-4:]
        for suborder in order["products"]:
            thisItem = products_col.find_one({"_id": suborder["_id"]})
            thisOrdersNames.append(thisItem["product_name"])
            thisOrdersPrices.append(suborder["price"])
            thisOrdersQuantities.append(suborder["quantity"])
        orderNames.append(thisOrdersNames)
        orderQuantities.append(thisOrdersQuantities)
        orderPrices.append(thisOrdersPrices)
        orderShipping.append(thisOrdersShipping)
        orderPayment.append(thisOrdersPayment)
    
    # Get the information for payment options and shipping addresses
    shippingInfo = []
    paymentInfo = []
    customerShippingInfo = customers_col.find_one({"_id": request.cookies.get("username")})["address_list"]
    customerPaymentInfo = customers_col.find_one({"_id": request.cookies.get("username")})["payment_option"]

    for address in customerShippingInfo:
        shippingInfo.append(address["firstname"] + " " + address["lastname"] + " " + address["street"] + " " + address["city"] + ", " + address["state"] + " " + address["country"])

    for payment in customerPaymentInfo:
        paymentInfo.append("Card ending in " + payment["creditcard"][-4:])

    # Render the page with all this information
    return render_template("account.html", orderNames=orderNames, orderQuantities=orderQuantities, orderShipping=orderShipping, orderPayment=orderPayment, orderPrices=orderPrices, shippingInfo=shippingInfo, paymentInfo=paymentInfo)

@app.route("/addPaymentInfo", methods=["GET", "POST"])
def addPaymentInfo():
    # Get form data from page and add it into the user's document
    if request.method=="POST":
        paymentDoc = {"firstname": request.form.get("firstname"),\
            "lastname":request.form.get("lastname"),\
            "creditcard":request.form.get("creditcard"),\
            "cvv":request.form.get("cvv"),\
            "month": request.form.get("month"),\
            "year": request.form.get("year")}
        customers_col.update_one({"_id": request.cookies.get("username")}, {"$push": {"payment_option" : paymentDoc}})
        # Redirect the user to their account page
        return redirect(url_for("account"))
    # Render page before form submission
    return render_template("paymentInfo.html")

# A lot like addPaymentInfo(), just reference that
@app.route("/addShippingInfo", methods=["GET", "POST"])
def addShippingInfo():
    if request.method=="POST":
        addressDoc = {"firstname": request.form.get("firstname"),\
            "lastname":request.form.get("lastname"),\
            "street":request.form.get("street"),\
            "city":request.form.get("city"),\
            "state":request.form.get("state"),\
            "country":request.form.get("country")}
        customers_col.update_one({"_id": request.cookies.get("username")}, {"$push": {"address_list" : addressDoc}})
        return redirect(url_for("account"))
    return render_template("shippingInfo.html")

# Render dynamic page for the given item ID
@app.route("/item/<itemID>", methods=["POST", "GET"])
def itemPage(itemID):
    # Find the item to be displayed
    item = products_col.find_one({"_id" : ObjectId(itemID)})
    # Form submission for adding item to cart
    if(request.method == "POST"):
        # Check to see if item is already in cart
        checkItems = customers_col.find_one({"_id": request.cookies.get("username")})["cart"]["item"]
        for index, item in enumerate(checkItems):
            # If it is, update the quantity in the cart and redirect
            if item == itemID:
                oldQuant = int(customers_col.find_one({"_id": request.cookies.get("username")})["cart"]["quantity"][index])
                customers_col.update_one({"_id": request.cookies.get("username")}, {"$set": {"cart.quantity." + str(index) : (int(oldQuant) + int(request.form.get("quantity")))}})
                return redirect(url_for("homepage"), code=302)
        # If it isn't in the cart, add it to the cart with the quantity selected and redirect
        customers_col.update_one({"_id": request.cookies.get("username")}, {"$push": {"cart.item" : itemID, "cart.quantity": int(request.form.get("quantity"))}})
        return redirect(url_for("homepage"), code=302)
    else:
        # Display item information before form submission
        description = ""
        try:
            description = item["description"]
        except:
            description = "No description available for this item. Please check back at a later time."
        return render_template("itemPage.html", itemID=itemID, itemName=item["product_name"], itemPrice="{:.2f}".format(float(item["price"])), itemDescription=description)

# Get item information and add it to the database
@app.route("/addItem", methods=["GET", "POST"])
def addItem():
    if(request.method == "POST"):
        # Get info and add it to the doc
        newItemDoc = { "product_name": request.form.get("itemName"), \
            "price": request.form.get("price"), \
            "product_weight": request.form.get("weight"), \
            "weight_scale": request.form.get("weightOption"), \
            "description": request.form.get("itemDesc")}
        # Add document to the database and redirect
        products_col.insert_one(newItemDoc)
        return redirect(url_for("homepage"), code=302)
    return render_template("addItem.html")

# View user cart
@app.route("/cart")
def userCart():
    # Find the cart of the user logged in
    cart = customers_col.find_one({"_id": request.cookies.get("username")})["cart"]
    itemIDs = customers_col.find_one({"_id": request.cookies.get("username")})["cart"]["item"]
    itemNames = []
    itemPrices = []
    # Get the information on the items
    for itemID in itemIDs:
        itemDoc = products_col.find_one({"_id": ObjectId(itemID)})
        itemNames.append(itemDoc["product_name"])
        itemPrices.append(itemDoc["price"])
    
    # Get user shipping and payment info for user selection on checkout
    shippingInfo = []
    paymentInfo = []
    customerShippingInfo = customers_col.find_one({"_id": request.cookies.get("username")})["address_list"]
    customerPaymentInfo = customers_col.find_one({"_id": request.cookies.get("username")})["payment_option"]

    # Append data to lists
    for address in customerShippingInfo:
        shippingInfo.append(address["firstname"] + " " + address["lastname"] + " " + address["street"] + " " + address["city"] + ", " + address["state"] + " " + address["country"])

    for payment in customerPaymentInfo:
        # Only send last 4 digits of Credit Card
        paymentInfo.append(payment["creditcard"][-4:]) 
    # display page with information
    return render_template("cart.html", username=request.cookies.get("username"), items=cart["item"], itemNames=itemNames, itemPrices=itemPrices, quantity=cart["quantity"], count=len(itemNames), shippingInfo=shippingInfo, paymentInfo=paymentInfo)

# Clear the cart in the database and redirect the user
@app.route("/cart/clear", methods=["GET", "POST"])
def clearCart():
    customers_col.update_one({"_id": request.cookies.get("username")},  {"$set": {"cart.item" : [], "cart.quantity": []}})
    return redirect(url_for("userCart"), code=302)

# Checkout items in user cart
@app.route("/cart/checkout", methods=["GET", "POST"])
def checkout():
    # Get the items that are in the user cart as well as their quantities
    itemIDs = customers_col.find_one({"_id": request.cookies.get("username")})["cart"]["item"]
    itemQuantities = customers_col.find_one({"_id": request.cookies.get("username")})["cart"]["quantity"]
    itemDocs = []
    # Get the payment and shipping info that was entered
    paymentUsed = customers_col.find_one({"_id": request.cookies.get("username")})["payment_option"][int(request.form.get("card"))]
    addressUsed = customers_col.find_one({"_id": request.cookies.get("username")})["address_list"][int(request.form.get("address"))]
    # Create and fill date of purchase and the customers ID, address and payment info
    orderDoc = {"date_of_purchase": datetime.now(), "customer_id": request.cookies.get("username"), "address": addressUsed, "payment": paymentUsed, "products": []}
    # Append the items to the products array in the order
    for index, itemID in enumerate(itemIDs):
        itemDocs.append(products_col.find_one({"_id": ObjectId(itemID)}))
        orderDoc["products"].append({"_id": ObjectId(itemID), "price": float(itemDocs[index]["price"]), "quantity": itemQuantities[index]})
    # Insert the order into the sales collection
    sales_col.insert_one(orderDoc)
    # Clear the user's cart and redirect
    customers_col.update_one({"_id": request.cookies.get("username")},  {"$set": {"cart.item" : [], "cart.quantity": []}})
    return redirect(url_for("homepage"), code=302)

if __name__ == "__main__":
    app.run()

