from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.template import loader
from .models import *
from django.core import serializers
from datetime import datetime
from django.db.models import Q
from django.core.mail import send_mail
from threading import Thread
from network_simulator.sim import *
from random import randint
def async_send_emails(order):
    try:
        send_mail('[Amazon]: Your order is delivered!', 'Dear ' + order.user.username + ',\n\n    Your order ' + order.name +' has just been delivered, enjoy!\n\nRegards,\n\nAmazon Team', '2356184200@qq.com', [order.user.email], fail_silently=False,)
    except:
        print("Email connection refused")
def recv_order_status_change():
    global django_response_queue
    #TODO
    while True:
        resp = django_response_queue.get()
        if resp["status"] == "purchased":
            warehouse = WareHouse.objects.get(pk = resp["whnum"])
            product = Product.objects.get(pk = resp["productid"])
            inventory = Inventory.objects.filter(warehouse = warehouse).filter(product = product)[0]
            inventory.amount += resp["count"]
            inventory.save()
            continue
        order_id = resp["orderid"]
        status = resp["status"]
        order = Order.objects.get(pk = order_id)
        if order.status == "loading" and status == "packed":
            continue
        if order.status == "delivering" and status == "loaded":
            continue
        order.status = status
        if order.status == "delivered":
            t = Thread(target = async_send_emails, args = [order,])
            t.start()
        order.save()
#=====================Init===================
def init_database():
    #TODO
    
    for inventory in Inventory.objects.all():
        inventory.delete()
    if len(InitializedFlag.objects.all()) == 0:
        warehouse1 = WareHouse(address_x=0, address_y=0)
        warehouse1.save()
        warehouse2 = WareHouse(address_x=1, address_y=1)
        warehouse2.save()
        warehouse3 = WareHouse(address_x=2, address_y=2)
        warehouse3.save()
        warehouse4 = WareHouse(address_x=3, address_y=3)
        warehouse4.save()
        product1 = Product(name = "Sofa", description = "sit like a queen", img_url = "https://img.alicdn.com/bao/uploaded///gma.alicdn.com/bao/uploaded/i1/130610800/O1CN01y5uwe61HmRWQvQPdl_!!2-saturn_solar.png_400x400q90.jpg_.webp")
        product1.save()
        product2 = Product(name = "Bouquet", description = "smells like feet", img_url = "https://img.alicdn.com/bao/uploaded/i1/2208910042571/O1CN01ySsCJy1UrYvQLnKOK_!!0-item_pic.jpg_400x400q90.jpg_.webp")
        product2.save()
        product3 = Product(name = "Hot Dog", description = "made in 1983", img_url = "https://img.alicdn.com/bao/uploaded///asearch.alicdn.com/bao/uploaded//i1/2567904926/O1CN01aY46qm1mG9gxBOar6_!!2567904926.jpg_400x400q90.jpg_.webp")
        product3.save()
        product4 = Product(name = "Jacket", description = "made of pater", img_url = "https://gw.alicdn.com/bao/uploaded/i3/1601573157/O1CN01Uy4XAA1ZBx5BDhBVr_!!1601573157.jpg_220x10000Q75.jpg_.webp")
        product4.save()
        product5 = Product(name = "Sneakers", description = "run like a snail", img_url = "https://img.alicdn.com/bao/uploaded/i4/419602243/O1CN01NwtQR11SRL3b2UaZA_!!0-item_pic.jpg_400x400q90.jpg_.webp")
        product5.save()
        product6 = Product(name = "Eggtart Baker", description = "lighter than the air", img_url = "https://gw.alicdn.com/bao/uploaded/i2/2218626744/O1CN01FK3AsM1zgneSpZQlg_!!0-item_pic.jpg_220x10000Q75.jpg_.webp")
        product6.save()
        initializedFlag = InitializedFlag(initialized=True)
        initializedFlag.save()

def init_recv_thread():
    #TODO
    thread = Thread(target = recv_order_status_change)
    thread.start()
def init_django():
    init_database()
    init_recv_thread()

init_django()
print("Initialized Django Recv Thread!")




#==============Interact with World===================


def send_order(order):
    global django_request_queue
    req = {}
    req["orderid"] = req["shipid"] = req["packageid"] = order.pk
    req["whnum"] = order.warehouse.pk
    req["productid"] = order.product.pk
    req["description"] = order.product.description
    req["count"] = order.amount
    req["command"] = "APack"
    req["address_x"] = order.address_x
    req["address_y"] = order.address_y
    if order.ups_account_name != "":
        req["ups_account_name"] = order.ups_account_name

    if len(Inventory.objects.filter(warehouse = order.warehouse).filter(product = order.product)) == 0:
        inventory = Inventory(warehouse = order.warehouse, product = order.product, amount = 0)
        inventory.save()

    inventory = Inventory.objects.filter(warehouse = order.warehouse).filter(product = order.product)[0]
    inventory.amount -= order.amount
    if inventory.amount < 0:
        #overdraft, assume purchase always succeed
        req["command"] = "APending"
        django_request_queue.put(req)
        aux_req = {}
        aux_req["orderid"] = aux_req["shipid"] = aux_req["packageid"] = order.pk
        aux_req["whnum"] = order.warehouse.pk
        aux_req["productid"] = order.product.pk
        aux_req["description"] = order.product.description
        aux_req["count"] = 1000000
        aux_req["command"] = "APurchaseMore"
        django_request_queue.put(aux_req)
        inventory.save()
        return
    django_request_queue.put(req)
    inventory.save()


#===============Web Thingy=========================
def user_has_logged_in(request):
    return 'username' in request.session

def index(request):
    if user_has_logged_in(request):
        return redirect("main.html")
    return render(request, 'index.html')

def login_html(request):
    return render(request, 'login.html')

def signup_html(request):
    return render(request, 'signup.html')

def catalog_html(request):
    return render(request, 'catalog.html')

def orders_html(request):
    if not user_has_logged_in(request):
        return redirect("no_login.html")
    return render(request, "orders.html")

def account_html(request):
    return render(request, "account.html")

def aux_get_user_info(request):
    json = serializers.serialize('json', User.objects.filter(username = request.session['username']))
    return HttpResponse(json)

def signup(request, username, password, email):
    q = User.objects.filter(username = username)
    if len(q) != 0:
        return JsonResponse({'errorMsg': 'This username has been used.'})
    new_user = User(username = username, password = password, email = email)
    new_user.save()
    return HttpResponse(request)

def login(request, username, password):
    q = User.objects.filter(username = username)
    if len(q) == 0:
        return JsonResponse({'errorMsg' : 'Username does not exist.'})
    if q[0].password != password:
        return JsonResponse({'errorMsg' : 'Password authentication failed.'})
    request.session['username'] = username
    return HttpResponse(request)

def no_login_html(request):
    return render(request, "no_login.html")

def main_html(request):
    if not user_has_logged_in(request):
        return redirect("no_login.html")
    return render(request, "main.html")

def confirm_html(request):
    if not user_has_logged_in(request):
        return redirect("no_login.html")
    return render(request, "confirm.html")

def edit_order_html(request):
    if not user_has_logged_in(request):
        return redirect("no_login.html")
    return render(request, "edit_order.html")

def cart_html(request):
    if not user_has_logged_in(request):
        return redirect("no_login.html")
    return render(request, "cart.html")
def aux_get_buy_info(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    if not "buy" in request.session:
        return JsonResponse({"status_code": 2})
    items = Product.objects.filter(pk = request.session["buy"])
    json = serializers.serialize("json", items)
    return HttpResponse(json)
def aux_get_comments(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    if not "buy" in request.session:
        return JsonResponse({"status_code": 2})
    items = Product.objects.filter(pk = request.session["buy"])
    item = items[0]
    comments = Comment.objects.filter(product = item)
    json = serializers.serialize("json", comments)
    return HttpResponse(json)
def post(request, product_id, comment):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    if not "buy" in request.session:
        return JsonResponse({"status_code": 2})
    user = User.objects.get(username = request.session["username"])
    item = Product.objects.get(pk = product_id)
    new_comment = Comment(product = item, user = user, username = user.username, comment = comment)
    new_comment.save()
    return HttpResponse()
def aux_get_order_info(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    if not "order_to_be_edited" in request.session:
        return JsonResponse({"status_code": 2})
    orders = Order.objects.filter(pk = request.session["order_to_be_edited"])
    json = serializers.serialize("json", orders)
    return HttpResponse(json)
def change_order_info(request, order_id, amount, address_x, address_y, ups_account_name):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    user = User.objects.get(username = request.session["username"])
    orders = Order.objects.filter(user = user).filter(pk = order_id)
    if len(orders) == 0:
        return JsonResponse({"status_code": 2})
    if ups_account_name == "DEFAULT_NOT_SET":
        ups_account_name = ""
    order = orders[0]
    order.amount = amount
    order.address_x = address_x
    order.address_y = address_y
    order.ups_account_name = ups_account_name
    order.save()
    return HttpResponse()
def rate(request, order_id, rating):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    user = User.objects.get(username = request.session["username"])
    orders = Order.objects.filter(user = user).filter(pk = order_id)
    if len(orders) == 0:
        return JsonResponse({"status_code": 2})
    order = orders[0]
    order.rated = True
    order.product.num_rated += 1
    order.product.total_score += rating
    order.product.save()
    order.save()
    return HttpResponse()
def confirm(request, product_id, amount, address_x, address_y, ups_account_name):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    items = Product.objects.filter(pk = product_id)
    if len(items) == 0:
        return JsonResponse({"status_code": 2})
    item = items[0]
    item.num_bought += 1
    item.save()
    if ups_account_name == "DEFAULT_NOT_SET":   
        ups_account_name = ""
    user = User.objects.get(username = request.session["username"])
    shipid = len(Order.objects.all()) + 1
    warehouse = WareHouse.objects.get(pk = randint(9,11))
    #Note: thread-unsafe
    order = Order(status = "packing", user = user, address_x = address_x, address_y = address_y, shipid = shipid, name = item.name, description = item.description, product = item, amount = amount, warehouse = warehouse, ups_account_name = ups_account_name, img_url = item.img_url)
    order.save()
    order.shipid = order.pk
    order.save()
    send_order(order)
    return HttpResponse()
def add(request, product_id, amount, address_x, address_y, ups_account_name):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    items = Product.objects.filter(pk = product_id)
    if len(items) == 0:
        return JsonResponse({"status_code": 2})
    item = items[0]
    if ups_account_name == "DEFAULT_NOT_SET":   
        ups_account_name = ""
    user = User.objects.get(username = request.session["username"])
    shipid = len(Order.objects.all()) + 1
    warehouse = WareHouse.objects.get(pk = randint(9,11))
    #Note: thread-unsafe
    order = Order(status = "incart", user = user, address_x = address_x, address_y = address_y, shipid = shipid, name = item.name, description = item.description, product = item, amount = amount, warehouse = warehouse, ups_account_name = ups_account_name, img_url = item.img_url)
    order.save()
    order.shipid = order.pk
    order.save()
    return HttpResponse()
def checkout(request, order_id_strs):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    user = User.objects.get(username = request.session["username"])
    orders = []
    order_id_list = [int(s) for s in order_id_strs.split(",")]
    for order_id in order_id_list:
        order_query = Order.objects.filter(user = user).filter(pk = order_id)
        if len(order_query) == 0:
            return JsonResponse({"status_code": 2})
        orders.append(order_query[0])
    for order in orders:
        order.product.num_bought += 1
        order.product.save()
        order.status = "packing"
        order.save()
        send_order(order)
    return HttpResponse()

def remove_from_cart(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    user = User.objects.get(username = request.session["username"])
    orders = Order.objects.filter(user = user).filter(pk = order_id)
    if len(orders) == 0:
        return JsonResponse({"status_code": 2})
    order = orders[0]
    order.delete()
    return HttpResponse()

def edit(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code": 1})
    user = User.objects.get(username = request.session["username"])
    orders = Order.objects.filter(user = user).filter(pk = order_id)
    if len(orders) == 0:
        return JsonResponse({"status_code": 2})
    request.session["order_to_be_edited"] = order_id
    return HttpResponse()

def change_user_info(request, password, email):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    user.password = password
    user.email = email
    user.save()
    return HttpResponse()

def logout(request):
    del request.session['username']
    #del request.session['share_search_car_type']
    #del request.session['share_search_special_info']
    return redirect("index.html")

def catalog(request):
    if not user_has_logged_in(request):
        return JsonResponse({'errorMsg': 'Please log in first.'})
    items = Product.objects.all()
    json = serializers.serialize("json", items)
    return HttpResponse(json)

def search(request, name):
    if not user_has_logged_in(request):
        return JsonResponse({'errorMsg': 'Please log in first.'})
    items = Product.objects.filter(name = name)
    json = serializers.serialize("json", items)
    return HttpResponse(json)

def buy(request, product_id):
    if not user_has_logged_in(request):
        return JsonResponse({'status_code': 1})
    items = Product.objects.filter(pk = product_id)
    if len(items) == 0:
        return JsonResponse({'status_code': 2})
    request.session["buy"] = product_id
    return HttpResponse()


def orders(request):
    if not user_has_logged_in(request):
        return JsonResponse({'status_code': 1})
    user = User.objects.get(username = request.session["username"])
    user_orders = Order.objects.filter(user = user).exclude(status = "incart")
    json = serializers.serialize("json", user_orders)
    return HttpResponse(json)
def cart(request):
    if not user_has_logged_in(request):
        return JsonResponse({'status_code': 1})
    user = User.objects.get(username = request.session["username"])
    user_orders = Order.objects.filter(user = user).filter(status = "incart")
    json = serializers.serialize("json", user_orders)
    return HttpResponse(json)
    '''
    transactions = Transaction.objects.filter(user = User.objects.get(username = request.session['username'])).order_by('-request_time')
    # rides = Ride.objects.filter(id__in = [t.ride.id for t in transactions])
    rides = [t.ride for t in transactions if t.ride.status > 0 and t.ride.status <= 4]
    json = serializers.serialize("json", rides)
    
    ##TODO
    return HttpResponse(json)
    '''
    '''
def drive_search(request, destination, date):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    driver = Driver.objects.get(user_id = user.id)
    day = string_to_date(date)
    orders = Ride.objects.filter(destination = destination).filter(passenger_num__lte = driver.car_capacity).filter(arrival_time__day = day.day).filter(Q(special_info = "") | Q(special_info = driver.special_info)).filter(Q(car_type = "Unspecified") | Q(car_type = driver.car_type)).exclude(status__gt = 3).exclude(status = 0)
    self_transactions = Transaction.objects.filter(user = user)
    self_orders = [t.ride for t in self_transactions]
    orders = [o for o in orders if o not in self_orders]
    json = serializers.serialize("json", orders)
    return HttpResponse(json)
def join(request, order_id, passenger_num):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    ride = Ride.objects.get(pk = order_id)
    if ride.status > 3:
        return JsonResponse({"status_code":3})
    transaction = Transaction(user = user, ride = ride, role = True, request_time = datetime.now(), passenger_num = passenger_num)
    ride.status = 2
    ride.passenger_num += passenger_num
    if ride.car_type == 'Unspecified':
        ride.car_type = request.session['share_search_car_type']
    if ride.special_info == "":
        ride.special_info = request.session['share_search_special_info']
    ride.sharer_num += 1
    ride.save()
    transaction.save()
    return HttpResponse()
'''
'''
def confirm(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    ride = Ride.objects.get(pk = order_id)
    if ride.status > 3:
        return JsonResponse({"status_code"})
    driver = Driver.objects.get(user_id = user.id)
    driver.number_of_incomplete_orders += 1
    ride.status = 4
    ride.driver = driver
    transactions = Transaction.objects.filter(ride = ride)
    t = Thread(target = async_send_emails, args = [transactions,])
    t.start()
    #async_send_emails(transactions)
    ride.save()
    driver.save()
    return HttpResponse()


def complete(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    driver = Driver.objects.get(user = user)
    driver.number_of_incomplete_orders -= 1
    driver.save()
    ride = Ride.objects.get(pk = order_id)
    ride.status = 5
    ride.save()
    return HttpResponse()
def drive_orders(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    driver = Driver.objects.get(user_id = user.id)
    ride = Ride.objects.filter(driver = driver)
    json = serializers.serialize("json", ride)
    return HttpResponse(json)

def driver_register_with_special_info(request, real_name, licence_number, car_capacity, car_type, special_info):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if user.is_driver:
        return JsonResponse({"status_code":2})
    user.is_driver = True
    driver = Driver(user = user, car_type = car_type, car_capacity = car_capacity, real_name = real_name, licence_number = licence_number, special_info = special_info)
    driver.save()
    user.save()
    return HttpResponse()
def driver_register(request, real_name, licence_number, car_capacity, car_type):
    return driver_register_with_special_info(request, real_name, licence_number, car_capacity, car_type, "")
def share_search_with_special_info(request, destination, earliest_time, latest_time, passenger_num, car_type, special_info):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    request.session['share_search_car_type'] = car_type
    request.session['share_search_special_info'] = special_info
    user = User.objects.get(username = request.session['username'])
    earliest_datetime = string_to_datetime(earliest_time)
    latest_datetime = string_to_datetime(latest_time)
    orders = Ride.objects.filter(destination = destination).filter(is_exclusive = False).filter(arrival_time__gte = earliest_datetime).filter(arrival_time__lte = latest_datetime).exclude(status__gt = 2).exclude(status = 0)
    if special_info != "":
        orders = orders.filter(Q(special_info = "") | Q(special_info = special_info))
    if car_type != "Unspecified":
        orders = orders.filter(Q(car_type = "Unspecified") | Q(car_type = car_type))
    self_transactions = Transaction.objects.filter(user = user)
    self_orders = [t.ride for t in self_transactions]
    orders = [o for o in orders if o not in self_orders]
    json = serializers.serialize('json', orders)

    return HttpResponse(json)
def share_search(request, destination, earliest_time, latest_time, passenger_num, car_type):
    return share_search_with_special_info(request, destination, earliest_time, latest_time, passenger_num, car_type, "")
def request_with_special_info(request, destination, arrival_time, passenger_num, shared, car_type, special_info):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    ride = Ride(status = 1, passenger_num = passenger_num, destination = destination, arrival_time = string_to_datetime(arrival_time), is_exclusive = (shared == "No"), sharer_num = 0, special_info = special_info, car_type = car_type)
    transaction = Transaction(user = user, ride = ride, role = False, request_time = datetime.now(), passenger_num = passenger_num)
    ride.save()
    transaction.save()
    return JsonResponse({"status_code":0})
def edit(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    request.session['order_to_be_edited'] = order_id
    return HttpResponse()
def cancel(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    order = Ride.objects.get(pk = order_id)
    if order.status == 4:
        return JsonResponse({"status_code":3})
    if order.status == 0:
        return JsonResponse({"status_code":4})
    cancelled_transaction = Transaction.objects.get(user = user, ride = order)
    if cancelled_transaction.role:
        order.sharer_num -= 1
        order.passenger_num -= cancelled_transaction.passenger_num
        order.save()
        cancelled_transaction.delete()
        return HttpResponse()
    transactions = Transaction.objects.filter(ride = order)
    order.status = 0
    for transaction in transactions:
        transaction.delete()
    order.save()
    return HttpResponse()
def edit_order_html(request):
    if not user_has_logged_in(request):
        return redirect("login.html")
    return render(request, "edit_order.html")
def request(request, destination, arrival_time, passenger_num, shared, car_type):
    return request_with_special_info(request, destination, arrival_time, passenger_num, shared, car_type, "")

def aux_get_order_info(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    order_id = request.session['order_to_be_edited']
    order = Ride.objects.get(pk = order_id)
    transaction = Transaction.objects.get(ride = order, user = user)
    order.passenger_num = transaction.passenger_num
    role = ""
    if transaction.role == False:
        role = "0"
    else:
        role = "1"
    json = serializers.serialize('json', [order,])
    json = json[:-3]
    json = json + ', "role": "' + role + '"}}]'
    return HttpResponse(json)

def aux_get_order_info__view(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    order_id = request.session['order_to_be_viewed']
    order = Ride.objects.get(pk = order_id)
    json = serializers.serialize('json', [order,])
    if order.status == 4:
        json = json[:-3]
        json = json + ' , "real_name": "' + order.driver.real_name + '" , "licence_number": "' + order.driver.licence_number + '"}}]'
    return HttpResponse(json)
def change_order_with_special_info(request, order_id, destination, arrival_time, passenger_num, shared, car_type, special_info):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    print(len(arrival_time))
    user = User.objects.get(username = request.session['username'])
    order = Ride.objects.get(pk = order_id)
    transaction = Transaction.objects.get(user = user, ride = order)
    order.destination = destination
    order.arrival_time = string_to_datetime(arrival_time)
    order.passenger_num += passenger_num - transaction.passenger_num
    order.car_type = car_type
    order.is_exclusive = shared == "No"
    order.special_info = special_info
    transaction.passenger_num = passenger_num
    order.save()
    transaction.save()
    return JsonResponse({"status_code":0})

def change_order(request, order_id, destination, arrival_time, passenger_num, shared, car_type):
    return change_order_with_special_info(request, order_id, destination, arrival_time, passenger_num, shared, car_type, "")

def aux_get_driver_info(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    driver = Driver.objects.get(user_id = user.id)
    json = serializers.serialize('json', [driver,])
    return HttpResponse(json)
def change_driver_info_with_special_info(request, real_name, licence_number, car_capacity, car_type, special_info):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    driver = Driver.objects.get(user = user)
    driver.real_name = real_name
    driver.licence_number = licence_number
    driver.car_capacity = car_capacity
    driver.car_type = car_type
    driver.special_info = special_info
    driver.save()
    return HttpResponse()
def change_driver_info(request, real_name, licence_number, car_capacity, car_type):
    return change_driver_info_with_special_info(request, real_name, licence_number, car_capacity, car_type, "")
def change_user_info(request, password, email):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    user.password = password
    user.email = email
    user.save()
    return HttpResponse()
def view(request, order_id):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    request.session['order_to_be_viewed'] = order_id
    return HttpResponse()
def open_order_details_html(request):
    if not user_has_logged_in(request):
        return redirect("login.html")
    return render(request, "open_order_details.html")
def confirmed_order_details_html(request):
    if not user_has_logged_in(request):
        return redirect("login.html")
    return render(request, "confirmed_order_details.html")
def driver_order_details_html(request):
    if not user_has_logged_in(request):
        return JsonResponse({"status_code":1})
    user = User.objects.get(username = request.session['username'])
    if not user.is_driver:
        return JsonResponse({"status_code":2})
    return render(request, "driver_order_details.html")
    '''


"""
def string_to_datetime(string):
    #unsafe
    if len(string) > 16:
        string = string[:-3]
    return datetime.strptime(string, "%Y-%m-%dT%H:%M")
def string_to_date(string):
    return datetime.strptime(string, "%Y-%m-%d")
"""


# Create your views here.
