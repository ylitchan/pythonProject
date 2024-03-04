from django.db import models

# Create your models here.
class Stocks(models.Model):
	# 文章id
	code = models.TextField()  # 自增、主键
	# 文章标题，文本类型
	stock = models.TextField()
	# 文章摘要，文本类型
	changeRatio = models.FloatField()
	upperLimit=models.FloatField()
	# 文章正文，文本类型
	latest = models.FloatField()
	# 文章发布日期，日期类型
	date = models.DateTimeField(auto_now=True)  # 自己填充当前日期

	def __str__(self):
		return self.stock

class Projects(models.Model):
	# 文章id
	degen = models.TextField()  # 自增、主键
	# 文章标题，文本类型
	project = models.TextField()
	# 文章摘要，文本类型
	description = models.TextField()
	created_at=models.TextField()
	# 文章正文，文本类型
	public_metrics = models.TextField()
	profile_image_url=models.TextField()
	degen_followers=models.TextField()
	# 文章发布日期，日期类型
	date = models.DateTimeField(auto_now=True)  # 自己填充当前日期

	def __str__(self):
		return self.project

