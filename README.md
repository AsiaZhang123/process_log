# Example Package

这是一个解决多进程下日志丢失的包。 
继承自python项目库logging。
所以完全兼容原logging，参数，用法都用变，直接改变类名称即可使用。
具体设置方法可以参考example.py

安装方法：pip install logging-process

版本更新历史：

2021-06-25  0.9.2 第一版正式上传 

2021-06-25  0.9.3 完善文件结构，可以直接导入logging类 

2021-06-25  0.9.4 完善example.py示例文件 

2021-07-14  0.9.5 工作需要，将time rotating 日志名字由时间在后，改为时间在前

2021-07-15  0.9.6 增加配置示例2,以时间分割日志文件时，增加参数nameFormat，可自定义文件名拼接方式