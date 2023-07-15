from queue import Queue

django_request_queue = Queue(1024)
django_response_queue = Queue(1024)
