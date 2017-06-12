# server

import socket
import json

address = ('10.128.230.43', 6666)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # s = socket.socket()
s.bind(address)
s.listen(5)

while True:
    ss, addr = s.accept()
    print('got connected from',addr)
    # ss.send(('my addr: '+str(addr)).encode('utf-8'))
    buffer_data = ss.recv(1024)
    request_values = json.loads(buffer_data.decode('utf-8'))
    request_type = request_values.get('type', None)
    print(buffer_data)
    if request_values['type'] == 'temp':
        print('send_freshrate')
        payload = {'freshperiod': 5, 'type': 'freshrate'}
        ss.send(json.dumps(payload).encode('utf-8'))
        buffer_data = ss.recv(1024)
        request_values = json.loads(buffer_data.decode('utf-8'))
        request_type = request_values.get('type', None)
        print(request_values)

# ss.send('byebye')
# ra = ss.recv(512)
# print ra
#
# ss.close()
# s.close()
