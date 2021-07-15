import logging
import os
from logging_process import MyTimedRotatingFileHandler, MyRotatingFileHandler


# 定义三种日志输出格式
# 其中name为make_logger的参数name
standard_format = '[%(levelname)s][%(asctime)s][%(threadName)s:%(thread)d][task_id:%(name)s]' \
                  '\n[%(filename)s-%(funcName)s:%(lineno)d][%(message)s]'

simple_format = '[%(levelname)s][%(asctime)s][%(filename)s-%(funcName)s:%(lineno)d]%(message)s'

id_simple_format = '[%(levelname)s][%(asctime)s] %(message)s'

# 项目名
project_name = 'example2'
# 日志文件名
logfile_name = '/data/log/' + project_name


log = logging.getLogger()
log.setLevel(logging.INFO)

# 输出到控制台的handler
sys_stream = logging.StreamHandler()
formatter = logging.Formatter(standard_format)
formatter.default_msec_format = '%s.%03d'
sys_stream.setFormatter(formatter)
sys_stream.setLevel(logging.INFO)

# 输出info级别以上的日志到access.log文件，并按天分割日志文件
time_steam = MyTimedRotatingFileHandler(filename='%s/access.log' % logfile_name, when='D', encoding='utf-8', backupCount=60)
# 可以自定义文件中时间的格式，详情参考time.strftime
time_steam.suffix = "%Y-%m-%d"
# 可以修改文件名日期在前还是在后，默认时间在后 access.log.2021-07-15
# time_steam.nameFormat = "{basePath}/{suffix}.{filename}"
formatter = logging.Formatter(simple_format)
time_steam.setFormatter(formatter)
time_steam.setLevel(logging.INFO)

# 输出error级别以上的日志到error.log文件，按文件大小分割日志文件
error_steam = MyRotatingFileHandler(filename='%s/error.log' % logfile_name, maxBytes=1024*1024*50, encoding='utf-8', backupCount=20)
formatter = logging.Formatter(standard_format)
error_steam.setFormatter(formatter)
error_steam.setLevel(logging.ERROR)

log.addHandler(sys_stream)
log.addHandler(time_steam)
log.addHandler(error_steam)

if not os.path.isdir(logfile_name):
    os.mkdir(logfile_name)

log.info("787878")

