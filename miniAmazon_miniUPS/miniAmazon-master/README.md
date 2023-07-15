
# test-amazon


```bash
.
├── polls
│   ├── web stuff
|
├── backend
│   ├── communication stuff
│   
├── network_simulator
|   ├── two queues faking the network
|
└── manage.py (top-level main)


=============== Usage ================
Configure postgresql to your own needs(default db: mydb, username: postgres, password:123)
First open manage.py and comment out line #8 backend.initbackend()
~ sudo python3 manage.py makemigrations
~ sudo python3 manage.py migrate
Decomment line 8 of manage.py
Start worldSim docker
~ sudo python3 manage.py runserver 0:80 --noreload
Let another group start UPS service
======================================

Note: the amazon service will be listening on Port 34567 for ups connection.
