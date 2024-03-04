import os
from django.core.management import execute_from_command_line

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alphaDS.settings')  # 替换成您的项目名
execute_from_command_line(['manage.py', 'runserver'])
