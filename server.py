from flask import Flask, request, jsonify
import requests
import time
import collections
from copy import deepcopy
import random, socket, threading
import json
app = Flask(__name__)

all_client = {'A15': {"room": "A15", "ID": "123456789012344567"},
              'A16': {"room": "A16", "ID": "123456789012344567"}}

class CentralAir:
    def __init__(self):
        self.all_data = {
            'log_list': [],
            'audit_list': [],
            'server_status': None,
            'working_mode': None,
            'min_temp': None,
            'max_temp': None,
            'temp': None,
            'refresh_rate': None,
            'clients':{
                'onservice': collections.OrderedDict(),  # 正在服务的
                'offservice': collections.OrderedDict(), # 已经服务过，目前出去 stop 状态的
                'waitingservice': collections.OrderedDict() # 等待服务， startwind 的时候被 waiting
            },
            'online_clients': collections.OrderedDict(),
            'waiting_clients': collections.OrderedDict(),
            'energy_cost': {
                'HIGH': 1.3,
                'MEDIUM': 1,
                'LOW': 0.8,
                'NONE': 0
            }
        }

        default_mode = 'COLD'  # 默认工作模式
        default_refresh_rate = 5  # 默认刷新频率

        self.start()  # 主控开机
        self.set_mode(default_mode)
        self.set_refresh_rate(default_refresh_rate)

        # self.tcp_server()

    def start(self):
        self.standby()

    # 每次回到待机模式的时候都会打印出所有日志
    def standby(self):
        self.all_data['server_status'] = 'standby'
        print('standby... log_list:\n', str(self.all_data['log_list']))

    def work(self):
        self.all_data['server_status'] = 'work'

    # 每次关机的时候都会打印出所有日志
    def shutdown(self):
        self.all_data['server_status'] = 'shutdown'
        print('shutdown... log_list:\n', str(self.all_data['log_list']))

    def is_standby(self):
        return self.all_data['server_status'] == 'standby'

    def is_work(self):
        return self.all_data['server_status'] == 'work'

    def is_shutdown(self):
        return self.all_data['server_status'] == 'shutdown'

    def set_mode(self, mode):
        if mode == 'HOT':
            self.all_data['working_mode'] = mode
            self.all_data['min_temp'] = 25
            self.all_data['max_temp'] = 30
            self.all_data['temp'] = 28
        elif mode == 'COLD':
            self.all_data['working_mode'] = mode
            self.all_data['min_temp'] = 18
            self.all_data['max_temp'] = 25
            self.all_data['temp'] = 22

    def set_refresh_rate(self, refresh_rate=3):
        self.all_data['refresh_rate'] = refresh_rate

    # 设置主控的温度
    def set_temp(self, temp):
        self.all_data['temp'] = temp

    # 构造从控的地址
    def get_client_addr(self, client_host):
        # client_addr = 'http://'+str(client_host)+':9998'
        client_addr = self.all_data['clients']['onservice'][client_host]['client_addr']
        return client_addr

    # 异步发送消息给从控的装饰器
    def async_task(func):
        def wrapper(self, client_host):
            print(func.__name__, ':')
            time.sleep(1)
            thread = threading.Thread(target=func, args=(self, client_host, ))
            thread.start()
        return wrapper

    # 异步发送刷新频率
    @async_task
    def send_freshrate(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "freshrate", "freshperiod": self.all_data['refresh_rate']}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

        # res = requests.post(url=client_addr, data=payload)
        # print(res.text)

    # @async_task
    def tcp_send_freshrate(self, client_addr,  client_status):
        client_socket = self.all_data['clients'][client_status][client_addr]['client_socket']
        payload = {"type": "freshrate", "freshperiod": self.all_data['refresh_rate']}
        client_socket.send(json.dumps(payload).encode('utf-8'))

        server(client_socket,client_addr)

    # 异步发送主控的工作模式
    @async_task
    def send_mode(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "mode", "workingmode": self.all_data['working_mode'], "defaulttemp": self.all_data['temp']}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    def tcp_send_mode(self, client_addr,client_status):
        # client_addr = self.get_client_addr(client_host)
        client_socket = self.all_data['clients'][client_status][client_addr]['client_socket']
        payload = {"type": "mode", "workingmode": self.all_data['working_mode'], "defaulttemp": self.all_data['temp']}
        client_socket.send(json.dumps(payload).encode('utf-8'))
        server(client_socket,client_addr)

    # 异步送风给从控
    @async_task
    def send_wind(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "wind", "windtemp": self.all_data['temp'], "velocity": self.all_data['clients']['onservice'][client_host]['velocity']}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    def tcp_send_wind(self, client_addr,client_status):
        # client_addr = self.get_client_addr(client_host)
        client_socket = self.all_data['clients'][client_status][client_addr]['client_socket']
        payload = {"type": "wind", "windtemp": self.all_data['temp'], "velocity": self.all_data['clients']['onservice'][client_addr]['velocity']}
        client_socket.send(json.dumps(payload).encode('utf-8'))
        server(client_socket,client_addr)

    # 异步发送用量和金额
    @async_task
    def send_bill(self, client_host):
        client_addr = self.get_client_addr(client_host)

        # 计算总用量和总金额
        current_time = time.time()
        # last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        # last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        if not last_start_time:
            last_start_time = current_time
        last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        if not last_velocity:
            last_velocity = 'NONE'
        last_period_energy = round((current_time - last_start_time)/60.0 *
                                   self.all_data['energy_cost'][last_velocity], 2)
        last_period_bill = round(5*last_period_energy, 2)
        # kwh = self.all_data['clients']['onservice'][client_host]['total_energy'] + last_period_energy
        # bill = self.all_data['clients']['onservice'][client_host]['total_bills'] + last_period_bill
        last_kwh = self.all_data['clients']['onservice'][client_host]['total_energy']
        if not last_kwh:
            last_kwh = 0
        last_bill = self.all_data['clients']['onservice'][client_host]['total_bills']
        if not last_bill:
            last_bill = 0
        kwh = last_kwh + last_period_energy
        bill =  last_bill + last_period_bill
        payload = {"type": "bill", "kwh": kwh, "bill": bill}
        print('send_bill payload: ', payload)
        res = requests.post(url=client_addr, data=payload)
        print(res.text)


    def tcp_send_bill(self, client_addr, client_status):

        self.update_bill(client_addr)
        # # client_addr = self.get_client_addr(client_host)
        #
        # # 计算总用量和总金额
        # current_time = time.time()
        # # last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        # # last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        # last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        # if not last_start_time:
        #     last_start_time = current_time
        # last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        # if not last_velocity:
        #     last_velocity = 'NONE'
        # last_period_energy = round((current_time - last_start_time)/60.0 *
        #                            self.all_data['energy_cost'][last_velocity], 2)
        # last_period_bill = round(5*last_period_energy, 2)
        # # kwh = self.all_data['clients']['onservice'][client_host]['total_energy'] + last_period_energy
        # # bill = self.all_data['clients']['onservice'][client_host]['total_bills'] + last_period_bill
        # last_kwh = self.all_data['clients']['onservice'][client_host]['total_energy']
        # if not last_kwh:
        #     last_kwh = 0
        # last_bill = self.all_data['clients']['onservice'][client_host]['total_bills']
        # if not last_bill:
        #     last_bill = 0
        # kwh = last_kwh + last_period_energy
        # bill =  last_bill + last_period_bill

        kwh = self.all_data['clients']['onservice'][client_addr]['total_energy']
        if not kwh:
            kwh = 0
        bill = self.all_data['clients']['onservice'][client_addr]['total_bills']
        if not bill:
            bill = 0
        client_socket = self.all_data['clients'][client_status][client_addr]['client_socket']
        payload = {"type": "bill", "kwh": kwh, "bill": bill}
        print('send_bill payload: ', payload)
        client_socket.send(json.dumps(payload).encode('utf-8'))
        server(client_socket,client_addr)

    @async_task
    def send_none_wind(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "wind", "windtemp": self.all_data['temp'], "velocity": "NONE"}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    def tcp_send_none_wind(self, client_addr,client_status):
        # client_addr = self.get_client_addr(client_host)
        client_socket = self.all_data['clients'][client_status][client_addr]['client_socket']
        payload = {"type": "wind", "windtemp": self.all_data['temp'], "velocity": "NONE"}
        client_socket.send(json.dumps(payload).encode('utf-8'))
        # server(client_socket,client_addr)


    # 每次接收到 startwind 的请求都会重新计算一次总用量和总消费（多次调用 update_bill 并不会产生副作用）
    def update_bill(self, client_host):
        # 如果不是第一次计费，那么更新 bill
        # if self.all_data['clients']['onservice'][client_host]['last_start_time']:
        #     last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        #     last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        # if self.all_data['clients']['onservice'][client_host]['last_start_time']:
        current_time = time.time()
        last_start_time = self.all_data['clients']['onservice'][client_host]['last_start_time']
        if not last_start_time:
            last_start_time = current_time
        last_velocity = self.all_data['clients']['onservice'][client_host]['velocity']
        if not last_velocity:
            last_velocity = 'NONE'
        # 每次改变风速的时候，都需要重新开始计费
        last_kwh = self.all_data['clients']['onservice'][client_host]['total_energy']
        if not last_kwh:
            last_kwh = 0
        last_bill = self.all_data['clients']['onservice'][client_host]['total_bills']
        if not last_bill:
            last_bill = 0


        last_period_energy = round((current_time - last_start_time)/60.0 *
                                   self.all_data['energy_cost'][last_velocity], 2)
        last_period_bill = round(5*last_period_energy, 2)

        # 更新数据
        # self.all_data['clients']['onservice'][client_host]['last_start_time'] = current_time
        # self.all_data['clients']['onservice'][client_host]['total_energy'] += last_period_energy
        # self.all_data['clients']['onservice'][client_host]['total_bills'] += last_period_bill
        self.all_data['clients']['onservice'][client_host]['last_start_time'] = current_time
        self.all_data['clients']['onservice'][client_host]['total_energy'] = last_kwh+last_period_energy
        self.all_data['clients']['onservice'][client_host]['total_bills'] = last_bill+last_period_bill

        # 如果是第一次计费,那么只是初始化相关信息
        # else:
        #     # self.all_data['clients']['onservice'][client_host]['last_start_time'] = time.time()
        #     # self.all_data['clients']['onservice'][client_host]['total_energy'] = 0
        #     # self.all_data['clients']['onservice'][client_host]['total_bills'] = 0
        #     self.all_data['clients']['onservice'][client_host]['last_start_time'] = time.time()
        #     self.all_data['clients']['onservice'][client_host]['total_energy'] = 0
        #     self.all_data['clients']['onservice'][client_host]['total_bills'] = 0

    # 停止送风
    def stop_wind(self, client_host):
        # centralAir.all_data['clients']['onservice'][client_host]['start_wind'] = False
        centralAir.all_data['clients']['onservice'][client_host]['start_wind'] = False
        self.update_bill(client_host)  # 更新 bill

        self.send_none_wind(client_host)
        client_data = self.all_data['clients']['onservice'][client_host]
        self.all_data['log_list'].append((client_host, deepcopy(client_data)))

        client_data['last_start_time'] = None

        self.all_data['clients']['offservice'][client_host] = client_data
        del self.all_data['clients']['onservice'][client_host]  # 移除从控
        # 如果等待列表中有等待的从控，那么通知从控可以开始工作了,采取先到先服务
        if len(self.all_data['clients']['waitingservice']) > 0:
            new_client_host, new_client_data = self.all_data['clients']['waitingservice'].popitem(last=False)
            self.all_data['clients']['onservice'][new_client_host] = new_client_data
            # del self.all_data['clients']['waitingservice'][new_client_host]
            self.send_wind(new_client_host)
        # 如果等待队列中没有从控，且在线队列中也没有从控了，那么设置主控的状态为待机
        elif len(self.all_data['clients']['onservice']) == 0:
            self.standby()

    def tcp_stop_wind(self, client_addr,client_status):
        # centralAir.all_data['clients']['onservice'][client_host]['start_wind'] = False
        centralAir.all_data['clients']['onservice'][client_addr]['start_wind'] = False
        self.update_bill(client_addr)  # 更新 bill

        self.tcp_send_none_wind(client_addr, client_status)

        client_data = self.all_data['clients']['onservice'].pop(client_addr)

        client_socket = client_data.pop('client_socket')

        self.all_data['log_list'].append((client_addr, deepcopy(client_data)))

        client_data['last_start_time'] = None
        client_data['client_socket'] = client_socket

        self.all_data['clients']['offservice'][client_addr] = client_data
        # 异步 receive
        thread = threading.Thread(target=server, args=(client_socket, client_addr, ))
        thread.start()
        # del self.all_data['clients']['onservice'][client_host]  # 移除从控
        # 如果等待列表中有等待的从控，那么通知从控可以开始工作了,采取先到先服务
        if len(self.all_data['clients']['waitingservice']) > 0:
            new_client_host, new_client_data = self.all_data['clients']['waitingservice'].popitem(last=False)
            self.all_data['clients']['onservice'][new_client_host] = new_client_data
            # del self.all_data['clients']['waitingservice'][new_client_host]
            self.tcp_send_wind(new_client_host, client_status='onservice')
        # 如果等待队列中没有从控，且在线队列中也没有从控了，那么设置主控的状态为待机
        elif len(self.all_data['clients']['onservice']) == 0:
            self.standby()
        # server(client_socket, client_addr)

def tcp_server():
    #tcp server
    TCP_IP = '172.20.10.7'
    TCP_PORT = 6666
    BUFFER_SIZE  = 1024

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(5)

    while True:
        print('loop')
        ss, addr = s.accept()
        print('got connected from', addr)

        thread = threading.Thread(target=server, args=(ss, addr, ))
        thread.start()



        #
        # self.generate_new_client(ss, addr)
        # # ss.send(('my addr: '+str(addr)).encode('utf-8'))
        # ra = ss.recv(1024)
        #
        # print(ra)




def server(ss , addr):
    buffer_data = ss.recv(1024)
    try:
        request_values = json.loads(buffer_data.decode('utf-8'))
    except Exception as e:
        print('error in server')
        print(e)
        print('buffer_data', buffer_data)
        server(ss, addr)
    request_type = request_values.get('type', None)
    client_host = str(addr)
    # client_addr = 'http://'+str(client_host)+':9998'
    # print(client_addr)
    print(request_values)
    response_text = 1
    # 只要接收过从控，那么会一直发送 temp
    if request_type == 'temp':
        client_temp = request_values.get('temp', None)
        # print(client_temp)

        # 如果是第一次收到该从机的温度信息
        if client_host not in centralAir.all_data['clients']['onservice'] and client_host not in centralAir.all_data['clients']['offservice'] and client_host not in centralAir.all_data['clients']['waitingservice']:
            client_pre_status = 'stopwind'
            # 如果主控处于待机状态，那么设置其为工作状态
            if centralAir.is_standby():
                centralAir.work()

            client_data = {
                    'client_socket':ss,
                    'client_addr': addr,
                    'temp': client_temp,
                    'room': None,
                    'ID': None,
                    'is_auth': False,
                    'start_wind': False,
                    'client_pre_status': client_pre_status,
                    'client_status': request_type,
                    'last_start_time': None,   # 上次收到 startwind 的时间
                    'desttemp': None,
                    'velocity': None,
                    'total_energy': None,
                    'total_bills': None}

            centralAir.all_data['clients']['offservice'][client_host] = client_data
            # 向从控发送温度测量值刷新率
            centralAir.tcp_send_freshrate(client_host, client_status= 'offservice')
            # 如果服务队列中的从控数量小于3，那么将从控加入服务队列
            # if len(centralAir.all_data['clients']['onservice']) < 3:
            #     centralAir.all_data['clients']['onservice'][client_host] = client_data
            #     # 向从控发送温度测量值刷新率
            #     centralAir.send_freshrate(client_host)
            # # 如果开机的从控大于3台了，则加入到等待队列中
            # else:
            #     centralAir.all_data['clients']['waitingservice'][client_host] = client_data
            #     response_text = 'Serving up to 3 climent, you are in the waiting list'
        # 如果不是第一次接收到温度信息（从控可能已经发送了 stopwind,从控可能处于 onservice 或 offservice 或 waitingservice）
        # 处于 onservice
        elif client_host in centralAir.all_data['clients']['onservice']:
            client_pre_status = centralAir.all_data['clients']['onservice'][client_host]['client_status']
            centralAir.all_data['clients']['onservice'][client_host]['client_pre_status'] = client_pre_status
            centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
            centralAir.all_data['clients']['onservice'][client_host]['temp'] = client_temp
            print('client: ',request_type, 'onservice')
            centralAir.tcp_send_bill(client_host, client_status='onservice')

        # 处于 offservice
        elif client_host in centralAir.all_data['clients']['offservice']:
            client_pre_status = centralAir.all_data['clients']['offservice'][client_host]['client_status']
            centralAir.all_data['clients']['offservice'][client_host]['client_pre_status'] = client_pre_status
            centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
            centralAir.all_data['clients']['offservice'][client_host]['temp'] = client_temp

            server(ss, addr)

        # 处于 waitingservice
        else :
            client_pre_status = centralAir.all_data['clients']['waitingservice'][client_host]['client_status']
            centralAir.all_data['clients']['waitingservice'][client_host]['client_pre_status'] = client_pre_status
            centralAir.all_data['clients']['waitingservice'][client_host]['client_status'] = request_type
            centralAir.all_data['clients']['waitingservice'][client_host]['temp'] = client_temp
            server(ss, addr)

        audit_log = {
            'client_host': client_host,
            'client_pre_status': client_pre_status,
            'request_type': request_type,
            'client_temp': client_temp,
            'request_time': time.time()
        }
        centralAir.all_data['audit_list'].append(audit_log)

    # 出现在 第一次 temp ,然后 refreshrate 之后，此时 client 应该处于 offservice
    elif request_type == 'auth':
        client_room = request_values.get('room', None)
        client_id = request_values.get('ID', None)
        # print(client_room, client_id)
        # 如果从控在 offservice
        if client_host in centralAir.all_data['clients']['offservice']:
            centralAir.all_data['clients']['offservice'][client_host]['room'] = client_room
            centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
            # 暂时不做实际的认证授权，只是存储起来
            centralAir.all_data['clients']['offservice'][client_host]['ID'] = client_id

            client_pre_status = centralAir.all_data['clients']['offservice'][client_host]['client_status']
            centralAir.all_data['clients']['offservice'][client_host]['client_pre_status'] = client_pre_status
            centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
            centralAir.tcp_send_mode(client_host, client_status='offservice')

        # if client_host in centralAir.all_data['clients']['onservice']:
        #     centralAir.all_data['clients']['onservice'][client_host]['room'] = client_room
        #     centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
        #     # 暂时不做实际的认证授权，只是存储起来
        #     centralAir.all_data['clients']['onservice'][client_host]['ID'] = client_id
        #     centralAir.send_mode(client_host)
        #
        #     client_pre_status = centralAir.all_data['clients']['onservice'][client_host]['client_status']
        #     centralAir.all_data['clients']['onservice'][client_host]['client_pre_status'] = client_pre_status
        #     centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type

            audit_log = {
                'client_host': client_host,
                'client_pre_status': client_pre_status,
                'request_type': request_type,
                'client_room': client_room,
                'client_id': client_id,
                'request_time': time.time()
            }
            centralAir.all_data['audit_list'].append(audit_log)

    # 两种情况, 1. offservice  2. onservice
    elif request_type == 'startwind':
        dest_temp = request_values.get('desttemp', None)
        velocity = request_values.get('velocity', None)
        print(dest_temp, velocity)
        print(centralAir.all_data['clients'])
        # 如果从控是 offservice
        if client_host in centralAir.all_data['clients']['offservice'].keys():
            # 服务队列中的从控数量大于3，加入等待
            if len(centralAir.all_data['clients']['onservice']) >= 3:
                client_data = centralAir.all_data['clients']['offservice'].pop(client_host)
                centralAir.all_data['clients']['waitingservice'][client_host] = client_data
                # del centralAir.all_data['clients']['offservice'][client_host]
                response_text = 'client is not onservice and onservice count is 3'
                print(response_text)
            # 加入 onservice
            else:
                client_data = centralAir.all_data['clients']['offservice'].pop(client_host)

                # client_socket = client_data.pop('client_data')

                centralAir.all_data['clients']['onservice'][client_host] = client_data
                # del centralAir.all_data['clients']['offservice'][client_host]
                print('from offservice to onservice')
        #  onservice

        centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
        centralAir.all_data['clients']['onservice'][client_host]['start_wind'] = True
        # 每次收到客户端的 startwind 请求都要更新一次计费信息
        centralAir.update_bill(client_host)
        centralAir.all_data['clients']['onservice'][client_host]['desttemp'] = dest_temp
        centralAir.all_data['clients']['onservice'][client_host]['velocity'] = velocity
        centralAir.all_data['clients']['onservice'][client_host]['last_start_time'] = time.time()
        centralAir.tcp_send_wind(client_host, client_status= 'onservice')

    elif request_type == 'stopwind':
        # 从在线从控列表中移除
        if client_host in centralAir.all_data['clients']['onservice']:
            centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
            centralAir.tcp_stop_wind(client_host, client_status='onservice')




# # 还需要一个日志模块，记录每次请求的信息
# @app.route("/", methods=['GET', 'POST'])
# def server():
#     request_type = request_values.get('type', None)
#     client_host = request.remote_addr
#     # client_addr = 'http://'+str(client_host)+':9998'
#     # print(client_addr)
#     print(request_values)
#     response_text = 1



    # # 只要接收过从控，那么会一直发送 temp
    # if request_type == 'temp':
    #     client_temp = request_values.get('temp', None)
    #     # print(client_temp)
    #
    #     # 如果是第一次收到该从机的温度信息
    #     if client_host not in centralAir.all_data['clients']['onservice'] and client_host not in centralAir.all_data['clients']['offservice'] and client_host not in centralAir.all_data['clients']['waitingservice']:
    #         client_pre_status = 'stopwind'
    #         # 如果主控处于待机状态，那么设置其为工作状态
    #         if centralAir.is_standby():
    #             centralAir.work()
    #
    #         client_data = {
    #                 'temp': client_temp,
    #                 'room': None,
    #                 'ID': None,
    #                 'is_auth': False,
    #                 'start_wind': False,
    #                 'client_pre_status': client_pre_status,
    #                 'client_status': request_type,
    #                 'last_start_time': None,   # 上次收到 startwind 的时间
    #                 'desttemp': None,
    #                 'velocity': None,
    #                 'total_energy': None,
    #                 'total_bills': None}
    #
    #         centralAir.all_data['clients']['offservice'][client_host] = client_data
    #         # 向从控发送温度测量值刷新率
    #         centralAir.send_freshrate(client_host)
    #         # 如果服务队列中的从控数量小于3，那么将从控加入服务队列
    #         # if len(centralAir.all_data['clients']['onservice']) < 3:
    #         #     centralAir.all_data['clients']['onservice'][client_host] = client_data
    #         #     # 向从控发送温度测量值刷新率
    #         #     centralAir.send_freshrate(client_host)
    #         # # 如果开机的从控大于3台了，则加入到等待队列中
    #         # else:
    #         #     centralAir.all_data['clients']['waitingservice'][client_host] = client_data
    #         #     response_text = 'Serving up to 3 climent, you are in the waiting list'
    #     # 如果不是第一次接收到温度信息（从控可能已经发送了 stopwind,从控可能处于 onservice 或 offservice 或 waitingservice）
    #     # 处于 onservice
    #     elif client_host in centralAir.all_data['clients']['onservice']:
    #         client_pre_status = centralAir.all_data['clients']['onservice'][client_host]['client_status']
    #         centralAir.all_data['clients']['onservice'][client_host]['client_pre_status'] = client_pre_status
    #         centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
    #         centralAir.all_data['clients']['onservice'][client_host]['temp'] = client_temp
    #
    #         centralAir.send_bill(client_host)
    #
    #     # 处于 offservice
    #     elif client_host in centralAir.all_data['clients']['offservice']:
    #         client_pre_status = centralAir.all_data['clients']['offservice'][client_host]['client_status']
    #         centralAir.all_data['clients']['offservice'][client_host]['client_pre_status'] = client_pre_status
    #         centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
    #         centralAir.all_data['clients']['offservice'][client_host]['temp'] = client_temp
    #
    #     # 处于 waitingservice
    #     else :
    #         client_pre_status = centralAir.all_data['clients']['waitingservice'][client_host]['client_status']
    #         centralAir.all_data['clients']['waitingservice'][client_host]['client_pre_status'] = client_pre_status
    #         centralAir.all_data['clients']['waitingservice'][client_host]['client_status'] = request_type
    #         centralAir.all_data['clients']['waitingservice'][client_host]['temp'] = client_temp
    #
    #     audit_log = {
    #         'client_host': client_host,
    #         'client_pre_status': client_pre_status,
    #         'request_type': request_type,
    #         'client_temp': client_temp,
    #         'request_time': time.time()
    #     }
    #     centralAir.all_data['audit_list'].append(audit_log)
    #
    # # 出现在 第一次 temp ,然后 refreshrate 之后，此时 client 应该处于 offservice
    # elif request_type == 'auth':
    #     client_room = request_values.get('room', None)
    #     client_id = request_values.get('ID', None)
    #     # print(client_room, client_id)
    #     # 如果从控在 offservice
    #     if client_host in centralAir.all_data['clients']['offservice']:
    #         centralAir.all_data['clients']['offservice'][client_host]['room'] = client_room
    #         centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
    #         # 暂时不做实际的认证授权，只是存储起来
    #         centralAir.all_data['clients']['offservice'][client_host]['ID'] = client_id
    #         centralAir.send_mode(client_host)
    #
    #         client_pre_status = centralAir.all_data['clients']['offservice'][client_host]['client_status']
    #         centralAir.all_data['clients']['offservice'][client_host]['client_pre_status'] = client_pre_status
    #         centralAir.all_data['clients']['offservice'][client_host]['client_status'] = request_type
    #
    #
    #     # if client_host in centralAir.all_data['clients']['onservice']:
    #     #     centralAir.all_data['clients']['onservice'][client_host]['room'] = client_room
    #     #     centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
    #     #     # 暂时不做实际的认证授权，只是存储起来
    #     #     centralAir.all_data['clients']['onservice'][client_host]['ID'] = client_id
    #     #     centralAir.send_mode(client_host)
    #     #
    #     #     client_pre_status = centralAir.all_data['clients']['onservice'][client_host]['client_status']
    #     #     centralAir.all_data['clients']['onservice'][client_host]['client_pre_status'] = client_pre_status
    #     #     centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
    #
    #         audit_log = {
    #             'client_host': client_host,
    #             'client_pre_status': client_pre_status,
    #             'request_type': request_type,
    #             'client_room': client_room,
    #             'client_id': client_id,
    #             'request_time': time.time()
    #         }
    #         centralAir.all_data['audit_list'].append(audit_log)
    #
    # # 两种情况, 1. offservice  2. onservice
    # elif request_type == 'startwind':
    #     dest_temp = request_values.get('desttemp', None)
    #     velocity = request_values.get('velocity', None)
    #     print(dest_temp, velocity)
    #     print(centralAir.all_data['clients'])
    #     # 如果从控是 offservice
    #     if client_host in centralAir.all_data['clients']['offservice'].keys():
    #         # 服务队列中的从控数量大于3，加入等待
    #         if len(centralAir.all_data['clients']['onservice']) >= 3:
    #             client_data = deepcopy(centralAir.all_data['clients']['offservice'][client_host])
    #             centralAir.all_data['clients']['waitingservice'][client_host] = client_data
    #             del centralAir.all_data['clients']['offservice'][client_host]
    #             response_text = 'client is not onservice and onservice count is 3'
    #             print(response_text)
    #         # 加入 onservice
    #         else:
    #             client_data = deepcopy(centralAir.all_data['clients']['offservice'][client_host])
    #             centralAir.all_data['clients']['onservice'][client_host] = client_data
    #             del centralAir.all_data['clients']['offservice'][client_host]
    #             print('from offservice to onservice')
    #     #  onservice
    #
    #     centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
    #     centralAir.all_data['clients']['onservice'][client_host]['start_wind'] = True
    #     # 每次收到客户端的 startwind 请求都要更新一次计费信息
    #     centralAir.update_bill(client_host)
    #     centralAir.all_data['clients']['onservice'][client_host]['desttemp'] = dest_temp
    #     centralAir.all_data['clients']['onservice'][client_host]['velocity'] = velocity
    #     centralAir.all_data['clients']['onservice'][client_host]['last_start_time'] = time.time()
    #     centralAir.send_wind(client_host)
    #
    # elif request_type == 'stopwind':
    #     # 从在线从控列表中移除
    #     if client_host in centralAir.all_data['clients']['onservice']:
    #         centralAir.all_data['clients']['onservice'][client_host]['client_status'] = request_type
    #         centralAir.stop_wind(client_host)



    # return jsonify(response_text)

if __name__ == "__main__":
    # 初始化主控
    centralAir = CentralAir()
    tcp_server()
    # app.run(host='localhost', port=9997)
