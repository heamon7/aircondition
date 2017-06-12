import time
import threading
import json

def receiver_thread(rec_socket, queue):
    ip_port = rec_socket.getpeername()
    received = ""
    while True:
        try:
            received = received + rec_socket.recv(1024).decode("UTF-8")
        except:
            break
        index = received.find("}")
        while index != -1:
            message = received[0:index + 1]
            queue.put((ip_port, message))
            received = received[index + 1:-1]
            index = received.find("}")


class Console(object):
    def __init__(self):
        self.show_args = {
            'goal_temp': -1,
            'recurrent_temp': -1,
            'pattern': None,
            'wind_v': 'NONE',
            'fresh_rate': -1,
            'wind_state': [],  # 1代表风速改变了状态，0代表风速没有改变状态
            'temp_state': [],  # 1代表设置温度改变了状态，0代表没有改变状态
            'state': -1,  # 从机是否开机【-1: 关机，0：待机，1：开机】
            'kwh': 0,
            'bill': 0
        }

    def set_args(self, goal_temp, wind_v, recurrent_temp, pattern, fresh_rate, state, kwh, bill):
        """
        set方法
        :param goal_temp: 目标温度
        :param wind_v: 风速
        :param recurrent_temp: 当前温度
        :param pattern: 模式
        :param fresh_rate: 刷新频率
        :param state: 从机状态
        :param kwh: 用电量
        :param bill: 电费
        :return:
        """
        self.show_args['goal_temp'] = goal_temp
        self.show_args['wind_v'] = wind_v
        self.show_args['recurrent_temp'] = recurrent_temp
        self.show_args['pattern'] = pattern
        self.show_args['fresh_rate'] = fresh_rate
        self.show_args['state'] = state
        self.show_args['kwh'] = kwh
        self.show_args['bill'] = bill

    def async_task(func):
        def wrapper(self):
            # time.sleep(1)
            thread = threading.Thread(target=func, args=(self, ))
            thread.start()
        return wrapper

    # @async_task
    def adjust_temp(self, input_1):
        """
        从机设置温度
        :return:
        """
        # print('请输入您的设置温度：')
        # while True:
        try:
            # goal = int(input())
            goal = int(input_1)
            if isinstance(goal, int):
                if self.show_args['pattern'] == 'COLD':
                    if goal < 18 or \
                                    goal > 25 or \
                                    goal >= self.show_args['recurrent_temp']:
                        print('根据中央空调的工作模式，您选择的温度超出界限， 请重新设置温度....\n')
                    else:
                        # return self.show_args['goal_temp']
                        self.show_args['goal_temp'] = goal
                        self.show_args['temp_state'].append(time.time())
                        # print('请输入您的设置温度：')
                elif self.show_args['pattern'] == 'HOT':
                    if goal < 25 or \
                                    goal > 30 or \
                                    goal <= self.show_args['recurrent_temp']:
                        print('根据中央空调的工作模式，您选择的温度超出界限， 请重新设置温度....\n')
                    else:
                        # return self.show_args['goal_temp']
                        self.show_args['goal_temp'] = goal
                        self.show_args['temp_state'].append(time.time())
                        # print('请输入您的设置温度：')
        except ValueError:
            print('请输入正确的数字：')

    # @async_task
    def adjust_wind(self, input_1):
        # print('请选择风速2--HIGH; 1--MEDIUM; 0--LOW: ')
        dict_1 = {'2': 'HIGH', '1': 'MEDIUM', '0': 'LOW'}
        if input_1 in ['0', '1', '2']:
            self.show_args['wind_v'] = dict_1[input_1]
            self.show_args['wind_state'].append(time.time())
        else:
            print('请重新输入风速：')

    def room_temp(self):
        """
        在无风和有风情况下的温度曲线
        :return: 当前温度
        """
        # sub_temp = recurrent_temp - goal_temp
        threading.Timer(self.show_args['fresh_rate'], self.room_temp).start()
        if isinstance(self.show_args['fresh_rate'], int):
            if self.show_args['pattern'] == 'COLD':
                if 18 <= self.show_args['goal_temp'] <= 25 and self.show_args['state'] == 1:
                    if self.show_args['wind_v'] == 'LOW':  # 低速风
                        self.show_args['recurrent_temp'] -= self.show_args['fresh_rate'] * 0.075
                    elif self.show_args['wind_v'] == 'MEDIUM':  # 中速风
                        self.show_args['recurrent_temp'] -= self.show_args['fresh_rate'] * 0.1
                    elif self.show_args['wind_v'] == 'HIGH':  # 高速风
                        self.show_args['recurrent_temp'] -= self.show_args['fresh_rate'] * 0.125

                    if self.show_args['recurrent_temp'] <= self.show_args['goal_temp']:  # 超出设置温度时
                        self.show_args['recurrent_temp'] = self.show_args['goal_temp']
                        # self.show_args['still_temp'] = self.show_args['goal_temp']
                        self.show_args['state'] = 0
                        # return self.show_args['recurrent_temp']
                elif self.show_args['state'] in [0, -1]:
                    # while self.show_args['fresh_rate'] % 0.1 == 0 and self.show_args['recurrent_temp'] <= 35:
                    self.show_args['recurrent_temp'] += self.show_args['fresh_rate'] * 0.1
                    # if (self.show_args['recurrent_temp'] - self.show_args['goal_temp']) > 1:
                    #     self.show_args['state'] = 1
                    if self.show_args['recurrent_temp'] >= 35:  # 超出环境温度
                        self.show_args['recurrent_temp'] = 35
            elif self.show_args['pattern'] == 'HOT':
                if 25 <= self.show_args['goal_temp'] <= 30 and self.show_args['state'] == 1:
                    if self.show_args['wind_v'] == 'LOW':  # 低速风
                        self.show_args['recurrent_temp'] += self.show_args['fresh_rate'] * 0.075
                    elif self.show_args['wind_v'] == 'MEDIUM':  # 中速风
                        self.show_args['recurrent_temp'] += self.show_args['fresh_rate'] * 0.1
                    elif self.show_args['wind_v'] == 'HIGH':  # 高速风
                        self.show_args['recurrent_temp'] += self.show_args['fresh_rate'] * 0.125
                    if self.show_args['recurrent_temp'] >= self.show_args['goal_temp']:  # 超出设置温度时
                        self.show_args['recurrent_temp'] = self.show_args['goal_temp']
                        self.show_args['state'] = 0
                        # return self.show_args['recurrent_temp']
                elif self.show_args['state'] in [0, -1]:
                    # while self.show_args['fresh_rate'] % 0.1 == 0 and self.show_args['recurrent_temp'] >= 15:
                    self.show_args['recurrent_temp'] -= self.show_args['fresh_rate'] * 0.1
                    # if (self.show_args['goal_temp'] - self.show_args['recurrent_temp']) > 1:
                    #     # self.show_args['state'] = 1
                    #     pass
                    if self.show_args['recurrent_temp'] <= 15:  # 超出环境温度
                        self.show_args['recurrent_temp'] = 15
        else:
            print('fresh_rate不是int类型……')
            # return self.show_args['recurrent_temp']

    # @async_task
    def show(self):
        threading.Timer(self.show_args['fresh_rate'], self.show).start()
        print('目标温度是：' + str(self.show_args['goal_temp']) + '\n' +
              '当前室温是：' + str(self.show_args['recurrent_temp']) + '\n' +
              '工作模式是：' + str(self.show_args['pattern']) + '\n' +
              '风速为：' + str(self.show_args['wind_v']) + '\n' +
              '刷新频率为：' + str(self.show_args['fresh_rate']) + '\n' +
              '用电量为：' + str(self.show_args['kwh']) + '\n' +
              '电费为：' + str(self.show_args['bill']) + '\n')
        print('如果您像改变风速或温度的话，[w]代表风速,2--HIGH; 1--MEDIUM，输入[w 1]代表中速,[t 20]代表改为20度：')

    @async_task
    def raw_input(self):
        while True:
            input_2 = input().split(' ')
            if input_2[0] == 'w':
                self.adjust_wind(input_1=input_2[1])
            elif input_2[0] == 't':
                self.adjust_temp(input_1=input_2[1])


class Queue(object):
    def __init__(self):
        self.queue = list()

    def put(self, message):
        self.queue.append(message)

    def async_task(func):
        def wrapper(self):
            # time.sleep(1)
            thread = threading.Thread(target=func, args=(self, ))
            thread.start()
        return wrapper

