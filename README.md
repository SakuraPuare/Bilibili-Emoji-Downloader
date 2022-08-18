# 提取B站表情包

## 使用教程

**此程序依赖于Selenium，请根据您使用的浏览器选择驱动安装及调整代码**

安装依赖

`pip install -r requirements.txt`

执行程序

`python main.py`

在跳出的窗口中登录哔哩哔哩账号，登录完成后程序将会自动读取表情包。

最后在`download`文件夹下查看下载的表情包。

## 问题

因为`httpx`异步请求速度太快，可能会出现包括但不限于`OSError`、`ConnectionResetError`、`httpx.ConnectError`等各种错误。

如果出现报错，您需要重新启动程序