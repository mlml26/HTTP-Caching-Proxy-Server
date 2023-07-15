#=========Import Packages==============
import socket
from .world_amazon_pb2 import *
from .amazon_ups_pb2 import *
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.encoder import _EncodeVarint
from network_simulator.sim import *
from .my_util import *
from datetime import datetime
import time
from copy import deepcopy
from threading import Thread
#=========Define Global Variables==============
global world_socket
global ups_socket
global world_id
seqnum = AtomicInteger(1)
seqnum_acked = AtomicInteger(0)
w_seqnum_queue = Queue(1024)
w_seqnum_set = set()
ups_request_queue = Queue(1024)
ups_response_queue = Queue(1024)
order_map = AtomicDictionary()  # shipid -> dict
status_map = AtomicDictionary()
command_map = AtomicDictionary()   # seqnum -> ACommand
pending_map = {}   # whnum -> dict list



#==================================================================
#=============== Section 2 World Send Functions ===================
#==================================================================


###====================2.1 World Send IO===========================

def world_send(msg, typ):
    global world_socket, seqnum, w_seqnum_queue, command_map
    msg.seqnum = seqnum.get()
    c = ACommands()
    if typ == "APurchaseMore":
        c.buy.append(msg)
    elif typ == "APack":
        c.topack.append(msg)
    elif typ == "APutOnTruck":
        c.load.append(msg)
    elif typ == "AQuery":
        print("Never send an AQuery")
        return
    elif typ == "AErr":
        print("Never send an AErr")
        return
    else:
        print("Unknown type: " + typ)
        return
    while not w_seqnum_queue.empty():
        c.acks.append(w_seqnum_queue.get())
    c.simspeed = 10900
    print(c)
    command_map.put(seqnum.getAndIncrement(), {"command": c, "time": datetime.now().timestamp(), "status": AtomicStatus("unacked")})
    msg_encoded = c.SerializeToString()
    _EncodeVarint(world_socket.send, len(msg_encoded), None)
    world_socket.send(msg_encoded)

###====================2.2 Django Request Handler===================
def handle_APop(req):
    global pending_map, django_request_queue
    pending_list = pending_map[req["whnum"]][req["productid"]]
    for pending_order in pending_list:
        pending_order["command"] = "APack"
        django_request_queue.put(pending_order)
    pending_map[req["whnum"]][req["productid"]] = []
    

def handle_APending(req):
    global pending_map
    if req["whnum"] not in pending_map:
        pending_map[req["whnum"]] = {}
    if req["productid"] not in pending_map[req["whnum"]]:
        pending_map[req["whnum"]][req["productid"]] = []
    pending_map[req["whnum"]][req["productid"]].append(req)

    ## helper function
def generate_AProduct(req):
    product = AProduct()
    product.id = req["productid"]
    product.description = req["description"]
    product.count = req["count"]
    return product

def handle_APurchaseMore_req(req):
    global order_map
    order_map.put(req["orderid"], req)
    action = APurchaseMore()
    action.whnum = req["whnum"]
    action.things.append(generate_AProduct(req))
    world_send(action, "APurchaseMore")

def handle_APack(req):
    global order_map, ups_request_queue
    order_map.put(req["orderid"], req)
    status_map.put(req["orderid"], AtomicStatus("packing"))
    action = APack()
    action.whnum = req["whnum"]
    action.shipid = req["shipid"]
    action.things.append(generate_AProduct(req))
    ##### notify ups ######
    aux_req = deepcopy(req)
    aux_req["command"] = "AU_pick_truck"
    ups_request_queue.put(aux_req)
    #################################
    world_send(action, "APack")


def handle_APutOnTruck(req):
    global django_response_queue
    action = APutOnTruck()
    action.truckid = req["truckid"]
    action.whnum = req["whnum"]
    action.shipid = req["shipid"]
    django_response_queue.put({"orderid": req["orderid"], "status": "loading"})
    world_send(action, "APutOnTruck")

def handle_AQuery(req):
    print("Never use an AQuery")

###===================2.3 Request Handler Map====================
django_request_handler_map = {"APending": handle_APending, "APurchaseMore": handle_APurchaseMore_req, "APop": handle_APop, "APack": handle_APack, "ALoad": handle_APutOnTruck, "AQuery": handle_AQuery}

###=================2.4 Send Thread Main Function================ 
def world_send_task():
    global django_request_handler_map, django_request_queue
    while True:
        req = django_request_queue.get()
        django_request_handler_map[req["command"]](req)



#==================================================================
#============= Section 3 - World Receive Functions ================
#==================================================================

###===================3.1 World Response Handler===================

def check_if_resp_has_been_handled(resp):
    global w_seqnum_set
    if resp.seqnum in w_seqnum_set:
        return True
    w_seqnum_set.add(resp.seqnum)
    return False
def handle_APurchaseMore_resp(resp):
    global w_seqnum_queue, django_request_queue, django_response_queue
    if check_if_resp_has_been_handled(resp):
        return
    for thing in resp.things:
        django_request_queue.put({"command": "APop", "whnum": resp.whnum, "productid": thing.id})
        django_response_queue.put({"status": "purchased", "whnum": resp.whnum, "count": thing.count, "productid": thing.id})
    w_seqnum_queue.put(resp.seqnum)

def handle_APacked(resp):
    global order_map, status_map, django_request_queue, w_seqnum_queue, django_response_queue
    if check_if_resp_has_been_handled(resp):
        return
    django_response_queue.put({"orderid": resp.shipid, "status": "packed"})
    if status_map.get(resp.shipid).swap("packed") == "arrived":
        #TODO
        req = order_map.get(resp.shipid)
        req["command"] = "ALoad"
        django_request_queue.put(req)
    w_seqnum_queue.put(resp.seqnum)
    

def handle_ALoaded(resp):
    global ups_request_queue, w_seqnum_queue, django_response_queue, order_map
    if check_if_resp_has_been_handled(resp):
        return
    django_response_queue.put({"orderid": resp.shipid, "status": "loaded"})
    req = order_map.get(resp.shipid)
    req["command"] = "AU_deliver_package"
    ups_request_queue.put(req)
    w_seqnum_queue.put(resp.seqnum)

def handle_AErr(resp):
    if check_if_resp_has_been_handled(resp):
        return
    print(resp.err)
    w_seqnum_queue.put(resp.seqnum)

def handle_APackage(resp):
    if check_if_resp_has_been_handled(resp):
        return
    print("Never send an AQuery so never receive an APackage")
    w_seqnum_queue.put(resp.seqnum)


###=====================3.2 World Receive IO========================

def world_recv():
    global world_socket, command_map
    var_int_buff = []
    while True:
        buf = world_socket.recv(1)
        var_int_buff += buf
        msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
        if new_pos != 0:
            break
    whole_message = world_socket.recv(msg_len)
    r = AResponses()
    r.ParseFromString(whole_message)
    print(r)
    return r

###===============3.3 World Receive Top Level Handler==============
def handle_AResponses(r): 
    for arrived in r.arrived:
        handle_APurchaseMore_resp(arrived)
    for ready in r.ready:
        handle_APacked(ready)
    for loaded in r.loaded:
        handle_ALoaded(loaded)
    for error in r.error:
        handle_AErr(error)
    for package in r.packagestatus:
        handle_APackage(package)
    for ack in r.acks:
        ##Not checking safe get
        command_map.get(ack)["status"].swap("acked")

###=================3.4 Receive Thread Main Function================ 
def world_recv_task():
    while True:
        r = world_recv()
        handle_AResponses(r)



#==================================================================
#=========== Section 4 - Timeout Scanning Task Thread =============
#==================================================================

###====================4.1 Mark and Sweep==========================
    #helper function
def update_seqnum_acked(lo, hi):
    global seqnum_acked, command_map
    for i in range(lo, hi):
        if not command_map.contains(i + 1):
            seqnum_acked.getAndIncrement()
        else:
            break

def marked_and_sweep():
    #[lo + 1, hi]
    global command_map, seqnum_acked, seqnum
    lo = seqnum_acked.get()
    hi = seqnum.get()
    print("Range: ", lo, hi)
    for i in range(0, hi + 1):
        if command_map.contains(i) and command_map.get(i)["status"].swap("unacked") == "acked":
            command_map.remove(i)
        elif command_map.contains(i) and datetime.now().timestamp() - command_map.get(i)["time"] > 10:
            print("Resent: \n", command_map.get(i)["command"])
            command = command_map.get(i)["command"]
            command_map.get(i)["time"] = datetime.now().timestamp()
            msg_encoded = command.SerializeToString()
            _EncodeVarint(world_socket.send, len(msg_encoded), None)
            world_socket.send(msg_encoded)
    update_seqnum_acked(lo, hi)



###==============4.2 Periodic Scanning Main Function================
def command_map_scan_task():
    while True:
        time.sleep(10)
        marked_and_sweep()


#========UPS Task Functions===============

#==================================================================
#=============== Section 5 - UPS Send Functions ===================
#==================================================================

###==================5.1 UPS Request Handler=======================

def handle_AU_pick_truck(req):
    action = AU_pick_truck()
    action.shipid = req["shipid"]
    action.whid = req["whnum"]
    action.trackingNumber = req["shipid"]
    if "ups_account_name" in req:
        action.accountName = req["ups_account_name"]
    ups_send(action, "AU_pick_truck")

def handle_AU_deliver_package(req):
    global django_response_queue
    django_response_queue.put({"orderid": req["orderid"], "status": "delivering"})
    action = AU_deliver_package()
    deliver_location = UDeliveryLocation()
    deliver_location.packageid = req["packageid"]
    deliver_location.x = req["address_x"]
    deliver_location.y = req["address_y"]
    action.packages.append(deliver_location)
    action.truckid = req["truckid"]
    ups_send(action, "AU_deliver_package")

def handle_UA_err_req(req):
    print("Never send a UA_Error but found " + req.err)
###==============5.2 UPS Request Handler Map=====================
ups_request_handler_map = {"AU_pick_truck": handle_AU_pick_truck, "AU_deliver_package": handle_AU_deliver_package, "UA_err": handle_UA_err_req}
###====================5.3 UPS Send IO===========================
def ups_send(msg, typ):
    global ups_socket 
    c = AU_commands()
    if typ == "AU_pick_truck":
        c.pick.append(msg)
    elif typ == "AU_deliver_package":
        c.deliver.append(msg)
    elif typ == "UA_err":
        c.errors.append(msg)
    else:
        print("Unknown type: " + typ)
        return
    print(c)
    msg_encoded = c.SerializeToString()
    _EncodeVarint(ups_socket.send, len(msg_encoded), None)
    ups_socket.send(msg_encoded)


###==============5.4 UPS Send Task Main Function=================
def ups_send_task():
    global ups_request_queue
    while True:
        req = ups_request_queue.get()
        ups_request_handler_map[req["command"]](req)


#==================================================================
#=============== Section 6 - UPS Recv Functions ===================
#==================================================================

###==================6.1 UPS Response Handler======================
def handle_UA_truck_picked(resp):
    global django_request_queue, status_map, order_map
    print("Resp shipid: " + str(resp.shipid))
    req = order_map.get(resp.shipid)
    req["truckid"] = resp.truckid
    if status_map.get(resp.shipid).swap("arrived") == "packed":    
        req["command"] = "ALoad"
        django_request_queue.put(req)


def handle_UA_package_delivered(resp):
    global django_response_queue
    django_response_queue.put({"orderid": resp.shipid, "status": "delivered"})
    status_map.remove(resp.shipid)
    order_map.remove(resp.shipid)

def handle_UA_err_resp(resp):
    print("Never receive a UA_Error but got " + resp.err)



###====================6.2 UPS Recv IO==========================
def ups_recv():
    global ups_socket
    var_int_buff = []
    while True:
        buf = ups_socket.recv(1)
        var_int_buff += buf
        msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
        if new_pos != 0:
            break
    whole_message = ups_socket.recv(msg_len)
    r = UA_commands()
    r.ParseFromString(whole_message)
    print(r)
    return r

###============6.3 UPS Response Top Level Handler============
def handle_UA_commands(r):
    for pick in r.pick:
        handle_UA_truck_picked(pick)
    for deliver in r.deliver:
        handle_UA_package_delivered(deliver)
    for error in r.errors:
        handle_UA_err_resp(error)

###============6.4 UPS Recv Task Main Function===============
def ups_recv_task():
    while True:
        r = ups_recv()
        handle_UA_commands(r)


#==================================================================
#================= Section 1 - Init Functions =====================
#==================================================================

def open_world_socket(host, port):
    global world_socket
    address = (host, port)
    world_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    world_socket.connect(address)

def init_warehouse(msg):
    a_init_warehouse = AInitWarehouse()
    a_init_warehouse1 = AInitWarehouse()
    a_init_warehouse2 = AInitWarehouse()
    a_init_warehouse.id = 9
    a_init_warehouse.x = 1
    a_init_warehouse.y = 1
    a_init_warehouse1.id = 10
    a_init_warehouse1.x = 2
    a_init_warehouse1.y = 2
    a_init_warehouse2.id = 11
    a_init_warehouse2.x = 3
    a_init_warehouse2.y = 3
    msg.initwh.append(a_init_warehouse)
    msg.initwh.append(a_init_warehouse1)
    msg.initwh.append(a_init_warehouse2)

def connect_to_world(host, port):
    global world_id, world_socket
    a_connect_msg = AConnect()
    init_warehouse(a_connect_msg)
    a_connect_msg.worldid = world_id
    a_connect_msg.isAmazon = True
    open_world_socket(host, port)
    print(a_connect_msg)
    a_connect_msg_encoded = a_connect_msg.SerializeToString()
    _EncodeVarint(world_socket.send, len(a_connect_msg_encoded), None)
    world_socket.send(a_connect_msg_encoded)
    var_int_buff = []
    while True:
        buf = world_socket.recv(1)
        var_int_buff += buf
        msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
        if new_pos != 0:
            break
    whole_message = world_socket.recv(msg_len)
    a_connected = AConnected()
    a_connected.ParseFromString(whole_message)
    print(a_connected)

def open_ups_socket(port):
    global ups_socket, world_id
    # create an INET, STREAMing socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # bind the socket to a public host, and a well-known port
    serversocket.bind((socket.gethostname(), port))
    # become a server socket
    serversocket.listen(5)
    (ups_socket, address) = serversocket.accept()
    buf = []
    buf += ups_socket.recv(8)
    print(buf)

    world_id = int.from_bytes(buf, "little")
    print("Received world id: " + str(world_id))

    #TODO

def listen_from_ups(port):
    #TODO
    open_ups_socket(port)

def init_threads():
    world_send_thread = Thread(target = world_send_task)
    world_recv_thread = Thread(target = world_recv_task)
    ups_send_thread = Thread(target = ups_send_task)
    ups_recv_thread = Thread(target = ups_recv_task)
    sweeper_thread = Thread(target = command_map_scan_task)

    world_send_thread.start()
    world_recv_thread.start()
    ups_send_thread.start()
    ups_recv_thread.start()
    sweeper_thread.start()


def init_backend():
    listen_from_ups(34567)
    connect_to_world("localhost", 23456)
    init_threads()



#==================================================================
#======= Appendix - Test Functions and Deprecated Stuff ===========
#==================================================================
def test_purchase_more():
    #world_socket = connect(True) 
    pm = APurchaseMore()
    p = AProduct()
    pm.whnum = 0
    p.id = 1
    p.description = "233"
    p.count = 1
    pm.things.append(p)
    print("==========Purchase More==========")
    r = send_and_recv(pm, "APurchaseMore")
    
def test_pack():
    pm = APack()
    p = AProduct()
    pm.whnum = 0
    pm.shipid = 1
    p.id = 1
    p.description = "233"
    p.count = 1
    pm.things.append(p)
    print("==========Purchase Pack==========")
    r = send_and_recv(pm, "APack")

    ## helper function
def init_info_and_put_in_map(info, req):
    info.put("whnum", req["whnum"])
    info.put("description", req["description"])
    info.put("command", req["command"])
    info.put("productid", req["productid"])
    info.put("count", req["count"])
    info.put("status", req["status"])
    order_map.put(req["orderid"], info)



def send_and_recv(msg, typ):
    global seqnum
    while True:
        my_send(msg, typ)
        (r, ack) = my_recv()
        if ack == seqnum:
            seqnum += 1
            return r
