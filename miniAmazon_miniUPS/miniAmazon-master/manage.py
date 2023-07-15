#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import backend.test as backend
def main():
    """Run administrative tasks."""
    backend.init_backend()
    #backend.connect()
    #backend.purchase_more()
    #backend.pack()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
     
    #from polls.views import init_django
    #init_django()
    execute_from_command_line(sys.argv)

    print("here")


if __name__ == '__main__':
    main()
