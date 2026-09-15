from django.db import models

class Property(models.Model):
    community = models.CharField(max_length=80)
    region = models.CharField(max_length=40)
    layout = models.CharField(max_length=20)
    area = models.IntegerField()
    rent = models.IntegerField()
    deposit = models.IntegerField()
    payment = models.CharField(max_length=20)
    facilities = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='待出租')
    landlord_phone = models.CharField(max_length=30)
