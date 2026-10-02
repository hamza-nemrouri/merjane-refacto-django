from django.db import models


class Product(models.Model):
    name              = models.CharField(max_length=100)
    type              = models.CharField(max_length=20)
    available         = models.IntegerField(default=0)
    lead_time         = models.IntegerField(default=0)
    expiry_date       = models.DateField(null=True, blank=True)
    season_start_date = models.DateField(null=True, blank=True)
    season_end_date   = models.DateField(null=True, blank=True)

    class Meta:
        app_label = 'orders'
