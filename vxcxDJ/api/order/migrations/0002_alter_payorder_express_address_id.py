# Generated by Django 4.1.7 on 2023-03-02 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payorder',
            name='express_address_id',
            field=models.IntegerField(default=1),
        ),
    ]
