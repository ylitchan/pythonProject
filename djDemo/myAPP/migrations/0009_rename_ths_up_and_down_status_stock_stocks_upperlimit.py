# Generated by Django 4.1.3 on 2022-12-17 13:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("myAPP", "0008_stocks_ths_up_and_down_status_stock"),
    ]

    operations = [
        migrations.RenameField(
            model_name="stocks",
            old_name="ths_up_and_down_status_stock",
            new_name="upperLimit",
        ),
    ]
