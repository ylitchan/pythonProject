from django.db import models


# Create your models here.

class LaunchInfo(models.Model):
    tweet_id = models.TextField(primary_key=True)
    tweet_user = models.TextField(null=True, blank=True)
    tweet_alpha = models.TextField(null=True, blank=True)
    tweet_text = models.TextField(null=True, blank=True)
    tweet_media = models.TextField(null=True, blank=True)
    tweet_ai = models.TextField(null=True, blank=True)
    tweet_tag = models.TextField(null=True, blank=True)
    alpha_datetime = models.DateTimeField(null=True, blank=True)
    user_thumb = models.TextField(null=True, blank=True)
    alpha_thumb = models.TextField(null=True, blank=True)
    tweet_time = models.DateTimeField(null=True, blank=True)
    list_account = models.TextField(null=True, blank=True)


class CallerInfo(models.Model):
    tweet_id = models.TextField(primary_key=True)
    tweet_user = models.TextField(null=True, blank=True)
    tweet_alpha = models.TextField(null=True, blank=True)
    tweet_text = models.TextField(null=True, blank=True)
    tweet_media = models.TextField(null=True, blank=True)
    tweet_ai = models.TextField(null=True, blank=True)
    tweet_tag = models.TextField(null=True, blank=True)
    alpha_datetime = models.DateTimeField(null=True, blank=True)
    user_thumb = models.TextField(null=True, blank=True)
    alpha_thumb = models.TextField(null=True, blank=True)
    tweet_time = models.DateTimeField(null=True, blank=True)
    list_account = models.TextField(null=True, blank=True)


class AlphaInfo(models.Model):
    username = models.TextField(primary_key=True)
    FollowedToday = models.TextField(null=True, blank=True)
    Followers = models.TextField(null=True, blank=True)
    Bio = models.TextField(null=True, blank=True)
    Created = models.DateTimeField(null=True, blank=True)
    DiscoveryTime = models.DateTimeField(null=True, blank=True)
