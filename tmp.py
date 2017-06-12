from flask import Flask, request, jsonify
import requests
import time
import threading
import collections

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
            'online_clients': collections.OrderedDict(),
            'waiting_clients': collections.OrderedDict(),
            'energy_cost': {
                'HIGH': 1.3,
                'MEDIUM': 1,
                'LOW': 0.8
            }
        }

        default_mode = 'COLD'  # 默认工作模式
        default_refresh_rate = 3  # 默认刷新频率

        self.start()  # 主控开机
        self.set_mode(default_mode)
        self.set_refresh_rate(default_refresh_rate)

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
        client_addr = 'http://'+str(client_host)+':9999'
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

    # 异步发送主控的工作模式
    @async_task
    def send_mode(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "mode", "workingmode": self.all_data['working_mode'], "defaulttemp": self.all_data['temp']}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    # 异步送风给从控
    @async_task
    def send_wind(self, client_host):
        client_addr = self.get_client_addr(client_host)
        payload = {"type": "wind", "windtemp": 20, "velocity": "HIGH"}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    # 异步发送用量和金额
    @async_task
    def send_bill(self, client_host):
        client_addr = self.get_client_addr(client_host)

        # 计算总用量和总金额
        current_time = time.time.now()
        last_start_time = self.all_data['online_clients'][client_host]['last_start_time']
        last_velocity = self.all_data['online_clients'][client_host]['velocity']
        last_period_energy = round((current_time - last_start_time)/60.0 *
                                   self.all_data['energy_cost'][last_velocity], 2)
        last_period_bill = round(5*last_period_energy, 2)
        kwh = self.all_data['online_clients'][client_host]['total_energy'] + last_period_energy
        bill = self.all_data['online_clients'][client_host]['total_bills'] + last_period_bill

        payload = {"type": "bill", "kwh": kwh, "bill": bill}
        res = requests.post(url=client_addr, data=payload)
        print(res.text)

    # 每次接收到 startwind 的请求都会重新计算一次总用量和总消费（多次调用 update_bill 并不会产生副作用）
    def update_bill(self, client_host):
        # 如果不是第一次计费，那么更新 bill
        if self.all_data['online_clients'][client_host]['last_start_time']:
            last_start_time = self.all_data['online_clients'][client_host]['last_start_time']
            last_velocity = self.all_data['online_clients'][client_host]['velocity']
            # 每次改变风速的时候，都需要重新开始计费
            current_time = time.time.now()
            last_period_energy = round((current_time - last_start_time)/60.0 *
                                       self.all_data['energy_cost'][last_velocity], 2)
            last_period_bill = round(5*last_period_energy, 2)

            # 更新数据
            self.all_data['online_clients'][client_host]['last_start_time'] = current_time
            self.all_data['online_clients'][client_host]['total_energy'] += last_period_energy
            self.all_data['online_clients'][client_host]['total_bills'] += last_period_bill

        # 如果是第一次计费,那么只是初始化相关信息
        else:
            self.all_data['online_clients'][client_host]['last_start_time'] = time.time.now()
            self.all_data['online_clients'][client_host]['total_energy'] = 0
            self.all_data['online_clients'][client_host]['total_bills'] = 0

    # 停止送风
    def stop_wind(self, client_host):
        self.update_bill(client_host)  # 更新 bill
        self.all_data['log_list'].append((client_host, self.all_data['online_clients'][client_host]))
        del self.all_data['online_clients'][client_host]  # 移除从控
        # 如果等待列表中有等待的从控，那么通知从控可以开始工作了,采取先到先服务
        if len(self.all_data['waiting_clients']) > 0:
            new_client_host, new_client_data = self.all_data['waiting_clients'].popitem(last=False)
            self.all_data['online_clients'][new_client_host] = new_client_data
            self.send_freshrate(new_client_host)
        # 如果等待队列中没有从控，且在线队列中也没有从控了，那么设置主控的状态为待机
        elif len(self.all_data['online_clients']) == 0:
            self.standby()

centralAir = CentralAir()
# 还需要一个日志模块，记录每次请求的信息
@app.route("/", methods=['GET', 'POST'])
def server():
    request_type = request.values.get('type', None)
    client_host = request.remote_addr
    # client_addr = 'http://'+str(client_host)+':9998'
    # print(client_addr)
    print(request.values)
    response_text = 1
    if request_type == 'temp':
        client_temp = request.values.get('temp', None)
        # print(client_temp)
        client_pre_status = None
        # 如果是第一次收到该从机的温度信息
        if client_host not in centralAir.all_data['online_clients']:
            client_pre_status = 'stopwind'
            # 如果主控处于待机状态，那么设置其为工作状态
            if centralAir.is_standby():
                centralAir.work()

            client_data = {
                    'temp': client_temp,
                    'room': None,
                    'ID': None,
                    'is_auth': False,
                    'client_pre_status': client_pre_status,
                    'client_status': request_type,
                    'last_start_time': None,   # 上次收到 startwind 的时间
                    'desttemp': None,
                    'velocity': None,
                    'total_energy': None,
                    'total_bills': None}

            # 如果服务队列中的从控数量小于3，那么将从控加入服务队列
            if len(centralAir.all_data['online_clients']) < 3:
                centralAir.all_data['online_clients'][client_host] = client_data
                # 向从控发送温度测量值刷新率
                centralAir.send_freshrate(client_host)
            # 如果开机的从控大于3台了，则加入到等待队列中
            else:
                centralAir.all_data['waiting_clients'][client_host] = client_data
                response_text = 'Seving up to 3 climent, you are in the waiting list'
        # 如果不是第一次收到该从控 temp
        else:
            client_pre_status = centralAir.all_data['online_clients'][client_host]['client_status']
            centralAir.all_data['online_clients'][client_host]['client_pre_status'] = client_pre_status
            centralAir.all_data['online_clients'][client_host]['client_status'] = request_type
            centralAir.all_data['online_clients'][client_host]['temp'] = client_temp

            centralAir.send_bill(client_host)
        audit_log = {
            'client_host': client_host,
            'client_pre_status': client_pre_status,
            'request_type': request_type,
            'client_temp': client_temp,
            'request_time': time.time.now()
        }
        centralAir.all_data['audit_list'].append(audit_log)

    elif request_type == 'auth':
        client_room = request.values.get('room', None)
        client_id = request.values.get('ID', None)
        # print(client_room, client_id)
        # 如果从控在在线从控列表中
        if client_host in centralAir.all_data['online_clients']:
            centralAir.all_data['online_clients'][client_host]['room'] = client_room
            centralAir.all_data['online_clients'][client_host]['client_status'] = request_type
            # 暂时不做实际的认证授权，只是存储起来
            centralAir.all_data['online_clients'][client_host]['ID'] = client_id
            centralAir.send_mode(client_host)

        else:
            pass

    elif request_type == 'startwind':
        dest_temp = request.values.get('desttemp', None)
        velocity = request.values.get('velocity', None)
        print(dest_temp, velocity)

        centralAir.all_data['online_clients'][client_host]['client_status'] = request_type
        # 每次收到客户端的 startwind 请求都要更新一次计费信息
        centralAir.update_bill(client_host)
        centralAir.all_data['online_clients'][client_host]['desttemp'] = dest_temp
        centralAir.all_data['online_clients'][client_host]['velocity'] = velocity
        centralAir.send_wind(client_host)

    elif request_type == 'stopwind':
        # 从在线从控列表中移除
        if client_host in centralAir.all_data['online_clients']:
            centralAir.all_data['online_clients'][client_host]['client_status'] = request_type
            centralAir.stop_wind(client_host)

    return jsonify(response_text)

if __name__ == "__main__":
    # 初始化主控
    app.run(host='10.128.230.43', port=9999)
