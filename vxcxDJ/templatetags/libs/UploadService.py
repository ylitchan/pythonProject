# -*- coding: utf-8 -*-
from werkzeug.utils import secure_filename
import datetime
import  os,stat,uuid
from django.conf import settings
from upload.models import Image
class UploadService():
	@staticmethod
	def uploadByFile( file ):
		config_upload = settings.UPLOAD
		resp = { 'code':200,'msg':'操作成功~~','data':{} }
		filename = secure_filename( file.name )
		ext = filename.rsplit(".",1)[1]
		if ext not in config_upload['ext']:
			resp['code'] = -1
			resp['msg'] = "不允许的扩展类型文件"
			return resp


		root_path = str(settings.BASE_DIR)+config_upload['prefix_path']
		#不使用getCurrentDate创建目录，为了保证其他写的可以用，这里改掉，服务器上好像对时间不兼容
		file_dir = datetime.datetime.now().strftime("%Y%m%d")
		save_dir = root_path + file_dir
		if not os.path.exists( save_dir ):
			os.mkdir( save_dir )
			os.chmod( save_dir,stat.S_IRWXU | stat.S_IRGRP |  stat.S_IRWXO )

		file_name = str( uuid.uuid4() ).replace("-","") + "." + ext
		with open("{0}/{1}".format( save_dir,file_name ), 'wb') as f:
			# chunks 对文件进行的读取   f.read()
			for files in file.chunks():
				# print(file.chunks)
				f.write(files)
		# file.save( "{0}/{1}".format( save_dir,file_name ) )

		model_image = Image()
		model_image.file_key = file_dir + "/" + file_name
		model_image.save()

		resp['data'] = {
			'file_key': model_image.file_key
		}
		return resp

