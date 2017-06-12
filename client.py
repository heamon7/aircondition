from flask import Flask, request, jsonify
from werkzeug.serving import WSGIRequestHandler
import requests
import threading
import time
from control import Console
import socket
import json
# 创建一个socket:
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 建立连接:
server_addr = '10.128.230.43'
s.connect((server_addr, 6666))


# s = requests.Session()
console = Console()


# @app.route("/", methods=['GET', 'POST'])
def server():
    print("client started")
    print(str(request.values))
    request_type = request.values.get('type', None)

    if request_type == 'freshrate':
        freshperiod = request.values.get('freshperiod', None)
        print(freshperiod)
        # TODO：警告一下频率如果不能被强制转换成int类型
        console.show_args['fresh_rate'] = int(freshperiod)  # 改变刷新频率
        send_auth()
    elif request_type == 'mode':
        workingmode = request.values.get('workingmode', None)
        defaulttemp = request.values.get('defaulttemp', None)
        print(workingmode, defaulttemp)
        console.show_args['pattern'] = workingmode  # 改变工作模式
        if workingmode == 'COLD':  # 改变初始温度
            console.show_args['recurrent_temp'] = 35  # 如果是冬天的话，应该是15度
        elif workingmode == 'HOT':
            console.show_args['recurrent_temp'] = 15

        send_recurrent_temp()  # 每刷新频率发一次实时温度值: 线程，timer
        console.raw_input()  # 等待输入状态变化: 线程，实时
        console.show()  # 控制面板展示各项数据: 线程，timer
        console.room_temp()  # 每刷新频率计算一次房间温度：线程，timer
        judge_wind()  # 判断何时发送风请求和停风请求：线程，实时
        room_temp_change()  # 温度变化引起送风请求：线程，实时
        room_wind_change()  # 风速变化引起送风请求：线程，实时

    elif request_type == 'wind':
        print('接收到送风指令： \n')
        wind_v = request.values.get('velocity', None)
        if wind_v == 'NONE':
            console.show_args['state'] = -1
            # console.show_args['wind_v'] = 'NONE'
        elif wind_v in ['HIGH', 'MEDIUM', 'LOW']:
            console.show_args['state'] = 1
            console.show_args['wind_v'] = wind_v

    elif request_type == 'bill':
        kwh = request.values.get('kwh', None)
        bill = request.values.get('bill', None)
        console.show_args['kwh'] = kwh
        console.show_args['bill'] = bill
    return jsonify(1)


def async_task(func):
    def wrapper():
        time.sleep(1)
        thread = threading.Thread(target=func)
        thread.start()
    return wrapper


def async_no_sleep(func):
    def wrapper():
        thread = threading.Thread(target=func)
        thread.start()
    return wrapper


@async_no_sleep
def judge_wind():
    """
    自然温度变化引起的发送停止送风 和 送风请求
    :return:
    """
    while True:
        if console.show_args['state'] == 0:
            send_stop_wind()
            change_times = len(console.show_args['temp_state'])
            while True:
                if abs(console.show_args['recurrent_temp'] - console.show_args['goal_temp']) >= 1 \
                        and len(console.show_args['temp_state']) == change_times:
                    send_start_wind()
                    break
            while console.show_args['state'] == 1:
                break


def send_start_wind():
    """
    向主机发送开始送风请求
    :return:
    """
    if console.show_args['goal_temp'] != -1 and console.show_args['wind_v'] != 'NONE':
        payload = {"type": "startwind",
                   "desttemp": console.show_args['goal_temp'],
                   "velocity": console.show_args['wind_v']}
        # s.post(url=server_addr, data=payload)
        my_writer_obj = s.makefile(mode='w')
        my_writer_obj.write(json.dumps(payload))
        my_writer_obj.flush()
        print('发送送风请求\n')


def send_stop_wind():
    """
    发送 停止送风请求
    :return:
    """
    payload = {"type": "stopwind"}
    s.post(url=server_addr, data=payload)
    print('发送停止送风请求')


def send_recurrent_temp():
    """
    每刷新频率发送实时测量温度
    :return:
    """
    threading.Timer(console.show_args['fresh_rate'], send_recurrent_temp).start()
    payload = {"type": "temp", "temp": console.show_args['recurrent_temp']}
    s.post(url=server_addr, data=payload)


@async_no_sleep
def room_temp_change():
    """
    判断操作时间小于1秒时，只发送最后一次的温度变化
    :return: send_start_wind
    """
    while True:
        if len(console.show_args['temp_state']) == 1:
            while True:
                time.sleep(1)
                if len(console.show_args['temp_state']) == 1:
                    send_start_wind()
                    del console.show_args['temp_state'][0]
                    break
                elif len(console.show_args['temp_state']) > 1:
                    temp_t_length = len(console.show_args['temp_state'][:-1])
                    for i in range(temp_t_length):
                        del console.show_args['temp_state'][0]


@async_no_sleep
def room_wind_change():
    """
    判断操作时间小于1秒时，只发送最后一次的风速变化
    :return: send_start_wind
    """
    while True:
        if len(console.show_args['wind_state']) == 1:
            while True:
                time.sleep(1)
                if len(console.show_args['wind_state']) == 1:
                    send_start_wind()
                    del console.show_args['wind_state'][0]
                    break
                elif len(console.show_args['wind_state']) > 1:
                    temp_t_length = len(console.show_args['wind_state'][:-1])
                    for i in range(temp_t_length):
                        del console.show_args['wind_state'][0]


@async_task
def send_temp(recurrent_temp=35):
    """
    只用一次不用管它
    :param recurrent_temp:
    :return:
    """
    payload = {"type": "temp", "temp": recurrent_temp}
    # s.post(url=server_addr, data=payload)
    my_writer_obj = s.makefile(mode='w')
    my_writer_obj.write(json.dumps(payload))
    my_writer_obj.flush()
    # s.send((payload))


@async_no_sleep
def send_auth():
    """
    只用一次不用管它
    :return:
    """
    payload = {"type": "auth", "room": "A15", "ID": "123456789012344567"}
    s.post(url=server_addr, data=payload)

if __name__ == "__main__":
    send_temp()
    # 接收数据:
    buffer = []
    d = s.recv(1024).decode('utf-8')
    print(d)
    print(1)
    # while True:
    #     # 每次最多接收1k字节:
    #     d = s.recv(1024).decode('utf-8')
    #     if d:
    #         buffer.append(d)
    #     else:
    #         break
    # print(buffer)
